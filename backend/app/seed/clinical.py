"""The clinical layer of the demo business (§4.2–4.9).

Built into the **`FULL` profile only**. `SMALL` — which `tests/conftest.py`
seeds — gets none of this, so all 608 pre-existing tests are untouched. That is
the same rule Phase 8 applied to leads, and for the same reason: the suite tests
the *application*, and adding a care manager or a device reading to its fixture
would rewrite assertions about the safety score's missing-data behaviour without
making a single test stronger.

The demo family still gets everything, because Lakshmi is in `FULL` too — she is
`core.patient`, and this module reaches her through the population step rather
than through `core.py`.

Three invariants this module must not break, all pinned by `tests/test_seed.py`
-------------------------------------------------------------------------------
1. **Lakshmi carries no open alert.** Phase 9 adds three new alert sources and
   this is exactly how the last one gets broken. Her labs come back normal, her
   device readings sit in range, and her score history is flat — every piece of
   drama below is routed to another patient.
2. **Anitha holds exactly one open visit today.** Nothing here creates a visit.
3. **The threshold engine still accounts for thirty resolved and four open
   alerts.** The alerts added here are a *different* `alert_type`, and the seed
   tests now assert the two populations separately rather than as one total.

Everything is built by **calling the real services**, never by writing rows —
Phase 4's rule, carried forward. If the safety score's rescaling breaks, or the
lab flagging drifts, the demo data is visibly wrong instead of being fabricated
around the bug.
"""

from __future__ import annotations

import random
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from ..core import clinical as constants
from ..core.exceptions import BadRequestError, ConflictError
from ..database import now
from ..models import (
    Alert,
    AlertStatus,
    CareChannel,
    CareDirection,
    CareManagerKind,
    DeviceKind,
    HospitalBookingStatus,
    Patient,
    SafetyScore,
    User,
    UserRole,
)
from ..services import (
    alert_service,
    care_service,
    consult_service,
    device_service,
    escalation_service,
    lab_service,
    safety_score,
    screening_service,
)
from . import demo_data

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.orm import Session

    from .population import PatientRecord

# --------------------------------------------------------------------------
# Rosters — data, no logic
#
# Kept here rather than in `demo_data.py` because nothing else reads them.
# `ZONES` and `EXTRA_NURSES` live there because `population.py` and
# `generators.py` both need them; a table with exactly one consumer is clearer
# beside its consumer.
# --------------------------------------------------------------------------

# Which of the three admins run which kind of caseload. The *ratios* are
# recorded (1:20 shared, 1:10 dedicated) and come from `core/pricing.py`; how
# many managers of each kind DoorDoctor staffs is a demo choice.
MANAGER_KINDS: tuple[CareManagerKind, ...] = (
    CareManagerKind.DEDICATED,
    CareManagerKind.SHARED,
    CareManagerKind.SHARED,
)

MANAGER_LANGUAGES: tuple[str, ...] = (
    "English, Kannada, Hindi",
    "English, Tamil, Telugu",
    "English, Kannada, Malayalam",
)

# Patient slots (0 is Lakshmi) that get each clinical feature. Chosen so the
# drama lands away from slot 0 and spreads across zones rather than clustering.
LAB_SLOTS: tuple[int, ...] = (0, 2, 3, 5, 7, 9, 11, 14, 17, 19, 22, 25)
ABNORMAL_LAB_SLOTS: tuple[int, ...] = (5, 14, 22)  # never slot 0
OPEN_ABNORMAL_LAB_SLOT: int = 22  # the one still sitting in the queue
SCREENING_SLOTS: tuple[int, ...] = (0, 1, 3, 4, 6, 8, 10, 12, 13, 16, 18, 20, 23, 26)
POSITIVE_SCREEN_SLOTS: tuple[int, ...] = (12, 20)  # never slot 0
DEVICE_SLOTS: tuple[int, ...] = (0, 4, 6, 9, 13, 15, 21, 24)
BREACHING_DEVICE_SLOT: int = 15  # never slot 0
CONSULT_SLOTS: tuple[int, ...] = (0, 3, 8, 13, 19, 24)

# Which analyte each abnormal panel comes back high on, and by how much. Chosen
# to stay *outside* the reference range but *inside* the critical one, so the
# demo shows a warning-level finding rather than a fabricated emergency.
ABNORMAL_VALUES: dict[str, float] = {
    "fasting_glucose": 148,
    "hba1c": 6.8,
    "creatinine": 1.7,
}

CARE_SUBJECTS: tuple[tuple[CareChannel, str, str], ...] = (
    (CareChannel.CALL, "Monthly check-in call", "Went through last month's visits with the family."),
    (CareChannel.CALL, "Medicine review call", "Confirmed the evening dose is being taken."),
    (CareChannel.MESSAGE, "Visit schedule confirmed", "Sent next week's visit times."),
    (CareChannel.VIDEO, "Family video call", "Son joined from Dubai; walked through the last report."),
    (CareChannel.VISIT, "In-person review", "Care manager joined the nurse's visit."),
)

HOSPITAL_REQUESTS: tuple[tuple[int, str, str, str, bool], ...] = (
    (
        7,
        "Manipal Hospital, Old Airport Road",
        "Cardiology",
        "Cardiology review requested by the family after two weeks of breathlessness.",
        False,
    ),
    (
        11,
        "Fortis Hospital, Bannerghatta Road",
        "Orthopaedics",
        "Follow-up on a healing hip fracture; family asked us to coordinate the appointment.",
        False,
    ),
    (
        15,
        "Sakra World Hospital, Marathahalli",
        "Emergency",
        "Home monitor reported a low oxygen level; family asked for transport.",
        True,
    ),
)

# How many days back the clinical history reaches, and the fixed stream that
# places it. Same discipline as `demo_data.RANDOM_SEED` — a fixed seed so two
# runs of `python -m app.seed` produce byte-identical data.
CLINICAL_HISTORY_DAYS = 75
CLINICAL_SEED = demo_data.RANDOM_SEED + 9_000

# Where each stored safety score sits, in days back from today. Enough points to
# draw a trend without pretending the score is recalculated hourly.
SCORE_OFFSETS: tuple[int, ...] = (60, 45, 30, 15, 0)


def _rng(salt: int) -> random.Random:
    """A stream per concern, so adding one feature cannot reshuffle another."""
    return random.Random(CLINICAL_SEED + salt)


# --------------------------------------------------------------------------
# Care managers
# --------------------------------------------------------------------------


def _seed_care(db: "Session", records: list["PatientRecord"], admins: list[User]) -> dict[str, int]:
    managers = []
    for index, admin in enumerate(admins[: len(MANAGER_KINDS)]):
        managers.append(
            care_service.create_manager(
                db,
                user=admin,
                kind=MANAGER_KINDS[index],
                languages=MANAGER_LANGUAGES[index],
            )
        )

    assigned = 0
    for record in records:
        # Through `auto_assign`, so the recorded 1:20 / 1:10 capacity is enforced
        # on the seed exactly as it is on an admin clicking the button. A roster
        # that quietly exceeded its own ratio would be a demo of a broken rule.
        if care_service.auto_assign(db, record.patient) is not None:
            assigned += 1

    interactions = 0
    rng = _rng(1)
    for record in records:
        if care_service.current_assignment(db, record.patient.id) is None:
            continue
        for offset in range(rng.randint(1, 3)):
            channel, subject, note = CARE_SUBJECTS[
                (record.slot + offset) % len(CARE_SUBJECTS)
            ]
            care_service.log_interaction(
                db,
                patient=record.patient,
                user=admins[record.slot % len(admins)],
                channel=channel,
                subject=subject,
                note=note,
                direction=CareDirection.OUTBOUND,
                minutes=rng.choice((8, 10, 12, 15, 20)),
                occurred_at=now() - timedelta(days=rng.randint(2, 60), hours=rng.randint(0, 8)),
            )
            interactions += 1

    db.flush()
    return {
        "care_managers": len(managers),
        "care_assignments": assigned,
        "care_interactions": interactions,
    }


# --------------------------------------------------------------------------
# Labs
# --------------------------------------------------------------------------


def _panel_values(panel, rng: random.Random, abnormal_code: str | None) -> dict[str, float]:
    """A believable result set: mid-range, with one analyte pushed out if asked."""
    values: dict[str, float] = {}
    for analyte in panel.analytes:
        if analyte.code == abnormal_code:
            values[analyte.code] = ABNORMAL_VALUES[analyte.code]
            continue
        low = analyte.ref_low if analyte.ref_low is not None else 0.0
        high = analyte.ref_high if analyte.ref_high is not None else low * 1.5 + 10
        span = high - low
        # Comfortably inside, never brushing the boundary — a seed that produces
        # borderline values would make the flagging test flap.
        value = low + span * rng.uniform(0.3, 0.7)
        values[analyte.code] = round(value, 1)
    return values


def _seed_labs(db: "Session", records: list["PatientRecord"], admins: list[User]) -> dict[str, int]:
    by_slot = {record.slot: record for record in records}
    rng = _rng(2)
    ordered = 0
    abnormal = 0

    for index, slot in enumerate(LAB_SLOTS):
        record = by_slot.get(slot)
        if record is None:
            continue

        # A slot that is meant to come back abnormal must be given a panel that
        # *contains* one of the analytes `ABNORMAL_VALUES` knows how to push
        # out. Rotating panels blindly silently produced lipid profiles for two
        # of the three abnormal slots, and they came back entirely normal — the
        # seed reported three abnormal results and the database held one.
        if slot in ABNORMAL_LAB_SLOTS:
            panel = constants.BASIC_PANEL
        else:
            panel = constants.LAB_PANELS[index % len(constants.LAB_PANELS)]
        ordered_at = now() - timedelta(days=rng.randint(10, CLINICAL_HISTORY_DAYS))
        family = db.get(User, record.patient.family_user_id)

        try:
            order = lab_service.order(
                db,
                patient=record.patient,
                user=family or admins[0],
                panel_code=panel.code,
                as_of=ordered_at,
            )
        except (BadRequestError, ConflictError):  # pragma: no cover - defensive
            continue

        lab_service.mark_collected(db, order, as_of=ordered_at + timedelta(hours=3))

        abnormal_code = None
        if slot in ABNORMAL_LAB_SLOTS:
            candidates = [a.code for a in panel.analytes if a.code in ABNORMAL_VALUES]
            assert candidates, f"{panel.code} has no analyte this seed can push out of range"
            abnormal_code = candidates[slot % len(candidates)]

        reported_at = ordered_at + timedelta(hours=panel.turnaround_hours)
        lab_service.record_results(
            db,
            order,
            _panel_values(panel, rng, abnormal_code),
            as_of=reported_at,
            notify=slot == OPEN_ABNORMAL_LAB_SLOT,
        )
        ordered += 1

        if abnormal_code is not None:
            abnormal += 1
            _settle_lab_alert(
                db,
                order.patient_id,
                reported_at,
                admins[0],
                leave_open=slot == OPEN_ABNORMAL_LAB_SLOT,
            )

    db.flush()
    return {"lab_orders": ordered, "lab_abnormal": abnormal}


def _settle_lab_alert(
    db: "Session", patient_id: int, raised_at, admin: User, *, leave_open: bool
) -> None:
    """Backdate the alert, and close it unless it is the one left in the queue.

    `create_alert` stamps the real clock, which is right in production and wrong
    in a seed — the same correction `business.py` applies to `paid_at`. The
    resolution gap stays inside the 5-minute-to-8-hour band
    `test_resolved_alerts_took_a_believable_amount_of_time` enforces.
    """
    alert = db.scalar(
        select(Alert)
        .where(Alert.patient_id == patient_id, Alert.alert_type == "lab_result_abnormal")
        .order_by(Alert.id.desc())
        .limit(1)
    )
    if alert is None:  # pragma: no cover - defensive
        return

    alert_service.backdate(alert, raised_at)
    if leave_open:
        return

    acknowledged = raised_at + timedelta(minutes=42)
    alert.status = AlertStatus.RESOLVED
    alert.acknowledged_by = admin.id
    alert.acknowledged_at = acknowledged
    alert.resolved_at = acknowledged + timedelta(hours=2)
    alert.resolution_note = (
        "Spoke to the family and the treating physician; medication reviewed and a repeat "
        "test booked for next month."
    )


# --------------------------------------------------------------------------
# Telemedicine
# --------------------------------------------------------------------------


def _seed_consults(db: "Session", records: list["PatientRecord"]) -> dict[str, int]:
    by_slot = {record.slot: record for record in records}
    rng = _rng(3)
    booked = 0

    for slot in CONSULT_SLOTS:
        record = by_slot.get(slot)
        if record is None:
            continue
        family = db.get(User, record.patient.family_user_id)
        if family is None:  # pragma: no cover - defensive
            continue

        # The demo patient's consult is deliberately placed in a **previous**
        # month. Care Plus includes one a month, and a consult seeded into the
        # current window spends the only one the demo family has — leaving the
        # founder's own account unable to demonstrate booking. Past-month
        # history shows the feature; the current allowance stays free.
        if slot == 0:
            past = True
            booked_at = now() - timedelta(days=45)
            scheduled_for = booked_at + timedelta(days=2)
        elif (past := rng.choice((True, True, False))):
            booked_at = now() - timedelta(days=rng.randint(20, 60))
            scheduled_for = booked_at + timedelta(days=2)
        else:
            booked_at = now() - timedelta(days=rng.randint(1, 4))
            scheduled_for = now() + timedelta(days=rng.randint(2, 10), hours=rng.randint(1, 8))

        try:
            consult = consult_service.book(
                db,
                patient=record.patient,
                user=family,
                scheduled_for=scheduled_for,
                reason=rng.choice(
                    (
                        "Review of blood pressure medication.",
                        "Family would like a doctor's opinion on recent tiredness.",
                        "Follow-up after the last lab report.",
                    )
                ),
                as_of=booked_at,
            )
        except (BadRequestError, ConflictError):
            # The allowance is spent, or the plan includes none — which is the
            # entitlement working, not a seed failure.
            continue

        if past:
            consult_service.complete(
                db,
                consult,
                family,
                summary="Reviewed the last month of readings. No change to medication advised.",
            )
            consult.completed_at = scheduled_for + timedelta(minutes=consult.duration_minutes)
        booked += 1

    db.flush()
    return {"consults": booked}


# --------------------------------------------------------------------------
# PHQ-2
# --------------------------------------------------------------------------


def _seed_screenings(db: "Session", records: list["PatientRecord"], nurses) -> dict[str, int]:
    by_slot = {record.slot: record for record in records}
    rng = _rng(4)
    recorded = 0
    positive = 0

    for slot in SCREENING_SLOTS:
        record = by_slot.get(slot)
        if record is None:
            continue

        nurse_user = nurses[slot % len(nurses)]
        # Two screens each, a cadence apart, so the mood component has a history
        # rather than a single point.
        #
        # The demo patient's pair is pushed further back on purpose: with a
        # screen three days old, `is_due` is False and the nurse's visit screen
        # correctly hides the questionnaire — which is right behaviour and a
        # dead demo, because slot 0 is the visit a founder opens. Her last
        # screen sits just outside the cadence so the form is there to fill in.
        if slot == 0:
            offsets = (constants.PHQ2_CADENCE_DAYS * 3, constants.PHQ2_CADENCE_DAYS + 6)
        else:
            offsets = (constants.PHQ2_CADENCE_DAYS + 4, 3)

        for step, days_back in enumerate(offsets):
            if slot in POSITIVE_SCREEN_SLOTS and step == 1:
                answers = [2, rng.choice((1, 2))]
                positive += 1
            else:
                answers = [rng.choice((0, 0, 1)), rng.choice((0, 1))]

            screening_service.record(
                db,
                patient=record.patient,
                user=nurse_user,
                answers=answers,
                as_of=now() - timedelta(days=days_back, hours=rng.randint(0, 6)),
            )
            recorded += 1

    db.flush()
    return {"screenings": recorded, "screenings_positive": positive}


# --------------------------------------------------------------------------
# Devices
# --------------------------------------------------------------------------


def _seed_devices(db: "Session", records: list["PatientRecord"]) -> dict[str, int]:
    by_slot = {record.slot: record for record in records}
    rng = _rng(5)
    devices = 0
    readings = 0
    breaches = 0

    for slot in DEVICE_SLOTS:
        record = by_slot.get(slot)
        if record is None:
            continue

        device, _key = device_service.register(
            db,
            patient=record.patient,
            kind=DeviceKind.PULSE_OXIMETER if slot % 2 == 0 else DeviceKind.SMARTWATCH,
            label="Bedside oximeter" if slot % 2 == 0 else "Wrist monitor",
            serial=f"DD-{record.patient.id:03d}-{slot:02d}",
        )
        device.registered_at = now() - timedelta(days=rng.randint(30, CLINICAL_HISTORY_DAYS))
        devices += 1

        # Three days of quiet readings, four a day. Ingested through the real
        # path so `triggered` is decided by the recorded rule, not asserted here.
        batch: list[dict[str, Any]] = []
        for day in range(3, 0, -1):
            for hour in (7, 12, 18, 22):
                stamp = now() - timedelta(days=day, hours=now().hour - hour)
                batch.append(
                    {"metric": _metric("spo2"), "value": rng.randint(95, 99), "recorded_at": stamp}
                )
                batch.append(
                    {
                        "metric": _metric("heart_rate"),
                        "value": rng.randint(62, 88),
                        "recorded_at": stamp + timedelta(seconds=1),
                    }
                )

        result = device_service.ingest(db, device, batch, notify=False)
        readings += result["accepted"]

        if slot == BREACHING_DEVICE_SLOT:
            # One low oxygen reading, through the real ingest path, so all three
            # recorded actions fire exactly as they would from real hardware.
            breach = device_service.ingest(
                db,
                device,
                [{"metric": _metric("spo2"), "value": 87, "recorded_at": now() - timedelta(hours=5)}],
                notify=True,
            )
            readings += breach["accepted"]
            breaches += breach["triggered"]

    db.flush()
    return {"devices": devices, "device_readings": readings, "device_breaches": breaches}


def _metric(name: str):
    from ..models import VitalMetric

    return VitalMetric(name)


# --------------------------------------------------------------------------
# Hospital coordination
# --------------------------------------------------------------------------


def _seed_hospital(db: "Session", records: list["PatientRecord"], admins: list[User]) -> dict[str, int]:
    by_slot = {record.slot: record for record in records}
    created = 0

    for index, (slot, hospital, department, reason, ambulance) in enumerate(HOSPITAL_REQUESTS):
        record = by_slot.get(slot)
        if record is None:
            continue
        family = db.get(User, record.patient.family_user_id) or admins[0]
        requested_at = now() - timedelta(hours=(index + 1) * 6)

        booking = escalation_service.request_hospital(
            db,
            patient=record.patient,
            user=family,
            hospital_name=hospital,
            reason=reason,
            department=department,
            ambulance_required=ambulance,
            as_of=requested_at,
            notify=False,
        )
        created += 1

        # The first is done, the second is being worked, the third is live —
        # a queue with something in every state is a queue worth showing.
        if index == 0:
            escalation_service.update_hospital(
                db,
                booking,
                admins[0],
                status=HospitalBookingStatus.CONFIRMED,
                confirmation_detail="Appointment confirmed for Thursday 11:00, Dr Ramesh.",
            )
            booking.confirmed_at = requested_at + timedelta(minutes=38)
        elif index == 1:
            escalation_service.update_hospital(
                db,
                booking,
                admins[0],
                status=HospitalBookingStatus.COORDINATING,
                notes="Waiting on the orthopaedics desk to call back.",
            )

    db.flush()
    return {"hospital_bookings": created}


# --------------------------------------------------------------------------
# Safety scores
# --------------------------------------------------------------------------


def _seed_scores(db: "Session", records: list["PatientRecord"]) -> dict[str, int]:
    """Record a trend for every patient, oldest first.

    Written by calling `safety_score.record`, so the number on every screen is
    one the live calculator would produce from this same data. A seeded score
    typed by hand would look right and be unexplainable — the exact failure the
    component breakdown exists to prevent.

    `notify=False`: a backdated drop must not fill today's notification bell.
    The alert row is still raised, which is what a demo of the recorded rule
    needs.
    """
    stored = 0
    for record in records:
        for offset in SCORE_OFFSETS:
            row = safety_score.record(
                db, record.patient, as_of=now() - timedelta(days=offset), notify=False
            )
            if row is not None:
                stored += 1

    db.flush()
    drops = _settle_drop_alerts(db)
    return {"safety_scores": stored, "safety_drop_alerts": drops}


def _settle_drop_alerts(db: "Session") -> int:
    """Backdate the drop alerts and close all but the newest.

    Two corrections, both the same class of bug `business.py` fixes for
    `paid_at`:

    * `create_alert` stamps the **real clock**, so a drop detected against a
      score dated sixty days ago arrived in the queue this morning. Every one is
      moved back to the calculation that produced it.
    * Nine open drop alerts is not a queue anybody works. They are genuine
      output of the recorded rule and are **not** suppressed — they are resolved,
      which is what a care team that has been running for two months would have
      done. The newest stays open so the rule is visible in the demo.
    """
    alerts = list(
        db.scalars(
            select(Alert)
            .where(Alert.alert_type == "safety_score_drop")
            .order_by(Alert.patient_id, Alert.id)
        )
    )
    if not alerts:
        return 0

    admin = db.scalar(
        select(User).where(User.role == UserRole.ADMIN).order_by(User.id).limit(1)
    )
    for alert in alerts:
        score = db.scalar(
            select(SafetyScore)
            .where(SafetyScore.patient_id == alert.patient_id)
            .order_by(SafetyScore.calculated_at.desc(), SafetyScore.id.desc())
            .limit(1)
        )
        if score is not None:
            alert_service.backdate(alert, score.calculated_at)

    # Newest first, so the one left open is the most recent drop.
    alerts.sort(key=lambda a: a.created_at, reverse=True)
    for alert in alerts[1:]:
        acknowledged = alert.created_at + timedelta(minutes=55)
        alert.status = AlertStatus.RESOLVED
        alert.acknowledged_by = admin.id if admin else None
        alert.acknowledged_at = acknowledged
        alert.resolved_at = acknowledged + timedelta(hours=3)
        alert.resolution_note = (
            "Reviewed the score breakdown with the care manager; the fall was driven by "
            "missed doses, and a daily reminder call has been arranged."
        )

    db.flush()
    return len(alerts)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def build(db: "Session", records: list["PatientRecord"]) -> dict[str, int]:
    """Layer the clinical business over an already-populated database.

    Ordered by dependency: care managers before interactions, screenings and
    device readings before safety scores, because the score reads both and a
    score computed first would be missing two of its six components.
    """
    admins = list(db.scalars(select(User).where(User.role == UserRole.ADMIN).order_by(User.id)))
    nurses = list(db.scalars(select(User).where(User.role == UserRole.NURSE).order_by(User.id)))

    summary: dict[str, int] = {}
    summary.update(_seed_care(db, records, admins))
    summary.update(_seed_labs(db, records, admins))
    summary.update(_seed_consults(db, records))
    summary.update(_seed_screenings(db, records, nurses))
    summary.update(_seed_devices(db, records))
    summary.update(_seed_hospital(db, records, admins))
    summary.update(_seed_scores(db, records))
    return summary
