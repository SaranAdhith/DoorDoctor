"""Connected devices and wearable ingest (§4.8).

RECORDED: **SpO2 below 90% or a heart rate outside range** triggers "the
documented three actions". §4.8 was never supplied and never lists those three
actions anywhere, so they are derived and marked `ASSUMED` in
`core/clinical.WEARABLE_ACTIONS` — all three in one place, so the founder
corrects them with one edit.

The three actions, run in order by `_run_actions`:

1. **Raise a critical alert** (`alert_service.create_alert`).
2. **Open an escalation** and contact family and admin **in parallel** on two
   channels through the Phase 3 delivery seam.
3. **Task the covering nurse** to check on the patient, due inside the critical
   SLA.

Security posture
----------------
`POST /ingest/device-readings` is the second least-trusted caller in this
codebase after the public lead form, and everything unusual here follows from
that:

* The device's API key is stored as a **sha256 only**. Phase 3's rule for
  password-reset tokens, for the same reason: a leaked table must not be a list
  of working credentials. The plaintext is returned once, at registration.
* Batch size and backdating are capped in `core/clinical.py`.
* Readings are rate limited **per device**, through the existing
  `core/ratelimit` — not a second limiter, because `clean_process_state` resets
  exactly one.
* **No device-supplied string ever reaches a log.** Only the device id and a
  count. A device is a thing on someone's wrist, and its serial, its label and
  its payload are all attacker-controlled text.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core import clinical
from ..core.exceptions import BadRequestError, NotFoundError, UnauthorizedError
from ..database import now
from ..models import (
    AlertSeverity,
    Device,
    DeviceKind,
    DeviceReading,
    DeviceStatus,
    EscalationTrigger,
    Patient,
    TaskKind,
    User,
    VitalMetric,
)
from . import alert_service, escalation_service, summary_service, task_service

logger = logging.getLogger("doordoctor.devices")

SOURCE_TYPE = "device_reading"

# Which metrics a device is allowed to report at all. A wearable pushing a
# "weight" of 4,000 into the clinical record is not a reading, it is an input.
INGESTIBLE_METRICS: frozenset[VitalMetric] = frozenset(
    {
        VitalMetric.SPO2,
        VitalMetric.HEART_RATE,
        VitalMetric.SYSTOLIC_BP,
        VitalMetric.DIASTOLIC_BP,
        VitalMetric.BLOOD_GLUCOSE,
        VitalMetric.TEMPERATURE,
        VitalMetric.WEIGHT,
    }
)


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def register(
    db: Session, *, patient: Patient, kind: DeviceKind, label: str, serial: str
) -> tuple[Device, str]:
    """Register a device. Returns the row **and the plaintext key, once.**

    The key cannot be recovered afterwards — only rotated. That is the point:
    `devices` is a table of hashes, so reading it grants nothing.
    """
    serial = serial.strip()
    if not serial:
        raise BadRequestError("A device serial is required.")

    existing = db.scalar(select(Device).where(Device.serial == serial))
    if existing is not None:
        # Says nothing about *whose* device it is — a serial is guessable, and
        # "already registered to another patient" would be a lookup oracle.
        raise BadRequestError("This device serial is already registered.")

    raw_key = f"dd_dev_{secrets.token_urlsafe(32)}"
    device = Device(
        patient_id=patient.id,
        kind=kind,
        label=label.strip(),
        serial=serial,
        api_key_hash=hash_key(raw_key),
        status=DeviceStatus.ACTIVE,
    )
    db.add(device)
    db.flush()
    logger.info("Device %s registered for patient %s", device.id, patient.id)
    return device, raw_key


def rotate_key(db: Session, device: Device) -> str:
    raw_key = f"dd_dev_{secrets.token_urlsafe(32)}"
    device.api_key_hash = hash_key(raw_key)
    db.flush()
    logger.info("Device %s key rotated", device.id)
    return raw_key


def authenticate(db: Session, raw_key: str | None) -> Device:
    """Resolve a device from its key. Indexed hash lookup, never a scan."""
    if not raw_key:
        raise UnauthorizedError("A device key is required.")
    device = db.scalar(
        select(Device)
        .options(selectinload(Device.patient))
        .where(Device.api_key_hash == hash_key(raw_key))
    )
    if device is None or device.status != DeviceStatus.ACTIVE:
        # One message for an unknown key and a deactivated device alike.
        raise UnauthorizedError("This device is not recognised.")
    return device


def deactivate(db: Session, device: Device) -> Device:
    device.status = DeviceStatus.INACTIVE
    db.flush()
    return device


def list_for_patient(db: Session, patient_id: int) -> list[Device]:
    return list(
        db.scalars(select(Device).where(Device.patient_id == patient_id).order_by(Device.id))
    )


def get_for_user(db: Session, user: User, device_id: int) -> Device:
    from ..core.dependencies import authorize_patient

    device = db.get(Device, device_id)
    if device is None:
        raise NotFoundError("Device not found.")
    try:
        authorize_patient(db, user, device.patient_id)
    except NotFoundError:
        raise NotFoundError("Device not found.") from None
    return device


# --------------------------------------------------------------------------
# The recorded triggers
# --------------------------------------------------------------------------


def breaches_trigger(metric: VitalMetric, value: float) -> str | None:
    """RECORDED: SpO2 below 90%, or heart rate outside range.

    Returns a plain-language reason, or None. Pure: no database, no clock, so a
    test re-runs the rule rather than trusting an ingest round trip.
    """
    if metric == VitalMetric.SPO2 and value < clinical.WEARABLE_SPO2_FLOOR:
        return f"oxygen level {_number(value)}%, below {_number(clinical.WEARABLE_SPO2_FLOOR)}%"
    if metric == VitalMetric.HEART_RATE:
        if value < clinical.WEARABLE_HR_LOW:
            return f"heart rate {_number(value)} bpm, below {_number(clinical.WEARABLE_HR_LOW)}"
        if value > clinical.WEARABLE_HR_HIGH:
            return f"heart rate {_number(value)} bpm, above {_number(clinical.WEARABLE_HR_HIGH)}"
    return None


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


# --------------------------------------------------------------------------
# Ingest
# --------------------------------------------------------------------------


def ingest(
    db: Session,
    device: Device,
    readings: list[dict[str, Any]],
    *,
    as_of: datetime | None = None,
    notify: bool = True,
) -> dict[str, Any]:
    """Store a batch and run the three actions on anything that breaches.

    Returns counts only. The response tells a device what happened to its batch
    and **nothing about the patient** — a device key is a credential on a wrist,
    and a stolen one must not become a health-record reader.
    """
    moment = as_of or now()
    if len(readings) > clinical.WEARABLE_MAX_BATCH:
        raise BadRequestError(
            f"At most {clinical.WEARABLE_MAX_BATCH} readings may be sent at once."
        )

    earliest = moment - timedelta(hours=clinical.WEARABLE_MAX_BACKDATE_HOURS)
    stored: list[DeviceReading] = []
    triggered: list[tuple[DeviceReading, str]] = []
    skipped = 0
    # De-duplication has to cover the batch as well as the database. Nothing is
    # flushed until the loop ends, so a device sending two untimestamped
    # readings of the same metric in one call would otherwise pass the database
    # check twice and then violate `uq_device_reading` on flush — turning a
    # sloppy payload into a 500 for the whole batch.
    seen: set[tuple[VitalMetric, datetime]] = set()

    for entry in readings:
        metric = entry["metric"]
        value = float(entry["value"])
        recorded_at = entry.get("recorded_at") or moment

        if metric not in INGESTIBLE_METRICS:
            skipped += 1
            continue
        if recorded_at < earliest or recorded_at > moment + timedelta(minutes=5):
            # Clock skew forwards is tolerated a little; a device claiming to
            # report from next week is not.
            skipped += 1
            continue

        key = (metric, recorded_at)
        if key in seen:
            skipped += 1
            continue
        duplicate = db.scalar(
            select(DeviceReading.id).where(
                DeviceReading.device_id == device.id,
                DeviceReading.metric == metric,
                DeviceReading.recorded_at == recorded_at,
            )
        )
        if duplicate is not None:
            skipped += 1
            continue
        seen.add(key)

        reason = breaches_trigger(metric, value)
        reading = DeviceReading(
            device_id=device.id,
            patient_id=device.patient_id,
            metric=metric,
            value=value,
            recorded_at=recorded_at,
            received_at=moment,
            triggered=reason is not None,
        )
        db.add(reading)
        stored.append(reading)
        if reason is not None:
            triggered.append((reading, reason))

    device.last_seen_at = moment
    db.flush()

    actions: list[str] = []
    if triggered:
        actions = _run_actions(db, device, triggered, as_of=moment, notify=notify)

    # Device id and counts only. Never a serial, a label, or a value.
    logger.info(
        "Device %s ingest: stored=%s skipped=%s triggered=%s",
        device.id,
        len(stored),
        skipped,
        len(triggered),
    )
    return {
        "accepted": len(stored),
        "skipped": skipped,
        "triggered": len(triggered),
        "actions": actions,
    }


def _run_actions(
    db: Session,
    device: Device,
    triggered: list[tuple[DeviceReading, str]],
    *,
    as_of: datetime,
    notify: bool,
) -> list[str]:
    """The three `ASSUMED` actions, executed in the order `clinical` lists them.

    One pass for the whole batch, not one per reading: a wearable reporting
    eight low SpO2 values in a minute is one clinical event, and eight
    escalations would bury it. Same rule as one alert per lab order.
    """
    patient = device.patient
    reasons = "; ".join(reason for _, reason in triggered)
    plain = summary_service.plain_metric_label(triggered[0][0].metric.value)

    # 1 — a critical alert
    alert = alert_service.create_alert(
        db,
        patient=patient,
        alert_type="wearable_breach",
        severity=AlertSeverity.CRITICAL,
        title=f"Home monitor reading needs attention ({plain})",
        message=(
            f"{patient.name}'s home monitor reported {reasons}. The care team has been "
            f"contacted. {clinical.EMERGENCY_BLOCK_TITLE}. This is a monitoring alert, "
            "not a medical diagnosis."
        ),
        breaches=[
            {
                "metric": reading.metric.value,
                "value": reading.value,
                "reason": reason,
                "source": "device",
            }
            for reading, reason in triggered
        ],
        notify=notify,
    )

    # 2 — an escalation, with family and admin contacted in parallel
    event = escalation_service.open_event(
        db,
        patient=patient,
        trigger=EscalationTrigger.WEARABLE_BREACH,
        severity=AlertSeverity.CRITICAL,
        summary=f"Home monitor alert for {patient.name}",
        detail=reasons,
        trigger_id=triggered[0][0].id,
        alert=alert,
        as_of=as_of,
        notify=notify,
    )

    # 3 — a task for the covering nurse, inside the critical SLA
    task_service.create(
        db,
        patient=patient,
        kind=TaskKind.WEARABLE_CHECK,
        title=f"Check on {patient.name} after a home monitor alert",
        detail=reasons,
        due_in_hours=max(1, clinical.SLA_DURATIONS_MINUTES["critical"] // 60 or 1),
        source_type=SOURCE_TYPE,
        source_id=triggered[0][0].id,
        assigned_user_id=task_service.assign_to_patients_nurse(db, patient),
        as_of=as_of,
    )

    db.flush()
    return [action.key for action in clinical.WEARABLE_ACTIONS]


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def readings_for_patient(
    db: Session, patient_id: int, *, since: datetime | None = None, limit: int = 200
) -> list[DeviceReading]:
    query = select(DeviceReading).where(DeviceReading.patient_id == patient_id)
    if since is not None:
        query = query.where(DeviceReading.recorded_at >= since)
    rows = list(
        db.scalars(query.order_by(DeviceReading.recorded_at.desc(), DeviceReading.id.desc()).limit(limit))
    )
    return list(reversed(rows))  # oldest first, for charting


def is_online(device: Device, as_of: datetime | None = None) -> bool:
    if device.last_seen_at is None:
        return False
    cutoff = (as_of or now()) - timedelta(minutes=clinical.WEARABLE_OFFLINE_AFTER_MINUTES)
    return device.last_seen_at >= cutoff


def serialize(device: Device) -> dict[str, Any]:
    return {
        "id": device.id,
        "patient_id": device.patient_id,
        "kind": device.kind.value,
        "label": device.label,
        "serial": device.serial,
        "status": device.status.value,
        "online": is_online(device),
        "last_seen_at": device.last_seen_at,
        "registered_at": device.registered_at,
    }


def serialize_reading(reading: DeviceReading) -> dict[str, Any]:
    return {
        "id": reading.id,
        "device_id": reading.device_id,
        "metric": reading.metric.value,
        # Said the way a family says it. This is a family-facing surface.
        "label": summary_service.plain_metric_label(reading.metric.value),
        "value": reading.value,
        "recorded_at": reading.recorded_at,
        "triggered": reading.triggered,
    }
