"""Escalation events, the parallel-notification timeline, and hospital
coordination (§4.3, §4.9).

RECORDED: the escalation ladder is **108 → nurse → admin**. Phase 7 pinned that
order in the assistant's emergency intent; `core/clinical.ESCALATION_LADDER`
states it once so the assistant, the on-screen emergency block and this timeline
cannot drift apart. Every SLA duration is `ASSUMED`.

**The timeline is data, not prose.** "We notified everyone" is a promise; one
`EscalationStep` per recipient per channel with its own timestamp is a record a
family can audit. Steps written at the same moment share a `sequence`, so the UI
draws a fan-out rather than implying a queue that was worked one at a time —
which is the difference between "we contacted four people at once" and "we
eventually got to the fourth".

**The SLA clock is stored, not computed at render time.** A booking that
breached last week must still say so after somebody edits `SLA_DURATIONS_MINUTES`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core import clinical
from ..core.exceptions import BadRequestError, NotFoundError
from ..database import now
from ..models import (
    Alert,
    AlertSeverity,
    DeliveryChannelName,
    EscalationEvent,
    EscalationStatus,
    EscalationStep,
    EscalationStepStatus,
    EscalationTrigger,
    HospitalBooking,
    HospitalBookingStatus,
    Nurse,
    Patient,
    TaskKind,
    User,
    UserRole,
    Visit,
)
from . import notification_delivery, notification_service, task_service

logger = logging.getLogger("doordoctor.escalations")

# Critical contact goes out on two channels at once. A single channel means one
# silent phone is the whole notification strategy.
#
# SMS and email, deliberately, because both have a **real address** in this
# build. `PushChannel.address_for` returns None until a mobile client ships, so
# a "dual-channel" promise made of SMS + push would be one channel wearing two
# names. Push joins this tuple the day there is a device token to send to;
# Phase 10 owns channel routing and per-user preferences and is where that
# belongs.
CRITICAL_CHANNELS: tuple[DeliveryChannelName, ...] = (
    DeliveryChannelName.SMS,
    DeliveryChannelName.EMAIL,
)
STANDARD_CHANNELS: tuple[DeliveryChannelName, ...] = (DeliveryChannelName.EMAIL,)


# --------------------------------------------------------------------------
# Opening an escalation
# --------------------------------------------------------------------------


def open_event(
    db: Session,
    *,
    patient: Patient,
    trigger: EscalationTrigger,
    severity: AlertSeverity,
    summary: str,
    detail: str = "",
    trigger_id: int | None = None,
    alert: Alert | None = None,
    as_of: datetime | None = None,
    notify: bool = True,
) -> EscalationEvent:
    """Open an escalation and run the ladder.

    The SLA is stamped on the row at open time from `core/clinical.py`. Both the
    budget and the deadline are stored: the deadline is what the queue sorts on,
    and the budget is what lets a screen say "15 minutes" months later without
    re-deriving it from constants that may since have changed.
    """
    moment = as_of or now()
    minutes = clinical.sla_minutes_for(severity.value)

    event = EscalationEvent(
        patient_id=patient.id,
        trigger=trigger,
        trigger_id=trigger_id,
        alert_id=alert.id if alert is not None else None,
        severity=severity,
        status=EscalationStatus.OPEN,
        summary=summary,
        detail=detail,
        opened_at=moment,
        sla_minutes=minutes,
        sla_due_at=moment + timedelta(minutes=minutes),
    )
    db.add(event)
    db.flush()

    _record_ladder(db, event, patient, as_of=moment, notify=notify)
    logger.info(
        "Escalation %s opened for patient %s (trigger=%s, sla=%smin)",
        event.id,
        patient.id,
        trigger.value,
        minutes,
    )
    return event


def _record_ladder(
    db: Session, event: EscalationEvent, patient: Patient, as_of: datetime, notify: bool
) -> list[EscalationStep]:
    """Write the recorded 108 → nurse → admin ladder as timeline steps.

    Step 0 is the emergency number and is **advisory, not an action** — DoorDoctor
    does not dial 108 on anyone's behalf, and a timeline that implied it had
    would be the most consequential lie this product could tell. Its status is
    `skipped` and its detail says so in words.

    Steps 1 and 2 go out **at the same sequence**, because the nurse and the
    admin are contacted in parallel. Contacting a family's nurse first and the
    on-call team only if that fails is a design nobody chose.
    """
    steps: list[EscalationStep] = []
    channels = (
        CRITICAL_CHANNELS if event.severity == AlertSeverity.CRITICAL else STANDARD_CHANNELS
    )

    steps.append(
        _step(
            db,
            event,
            sequence=0,
            actor="Family",
            channel="phone",
            target=clinical.EMERGENCY_NUMBER,
            status=EscalationStepStatus.SKIPPED,
            detail=(
                f"If this is an emergency, {clinical.EMERGENCY_LADDER_ADVICE}"
            ),
            occurred_at=as_of,
        )
    )

    recipients = _recipients(db, patient)
    for user, role_label in recipients:
        for channel in channels:
            record = None
            if notify:
                record = notification_delivery.deliver(
                    db,
                    channel=channel,
                    subject=event.summary,
                    body=_message_for(event, patient),
                    user=user,
                )
                if record is not None:
                    # `deliver` only adds; without this the step would store a
                    # null id and the timeline could not link back to what was
                    # actually sent.
                    db.flush()
            steps.append(
                _step(
                    db,
                    event,
                    sequence=1,  # one sequence for everyone: this is a fan-out
                    actor=role_label,
                    channel=channel.value,
                    target=user.name,
                    recipient_user_id=user.id,
                    status=(
                        EscalationStepStatus.SIMULATED
                        if record is not None
                        else EscalationStepStatus.PENDING
                    ),
                    # An unreachable channel is recorded as an attempt that
                    # could not be made, not omitted. A timeline that silently
                    # drops the channels it could not use overstates the
                    # contact that actually happened.
                    detail=(
                        f"{role_label} contacted on {channel.value}."
                        if record is not None
                        else f"{role_label} has no {channel.value} address on file."
                    ),
                    delivery_log_id=record.id if record is not None else None,
                    occurred_at=as_of,
                )
            )

    if notify:
        for user, _ in recipients:
            notification_service.create_notification(
                db,
                user_id=user.id,
                title=event.summary,
                message=_message_for(event, patient),
                patient_id=patient.id,
                alert_id=event.alert_id,
            )

    db.flush()
    return steps


def _recipients(db: Session, patient: Patient) -> list[tuple[User, str]]:
    """The family, the covering nurse and every active admin, de-duplicated."""
    people: list[tuple[User, str]] = []
    seen: set[int] = set()

    family = db.get(User, patient.family_user_id)
    if family is not None:
        people.append((family, "Family"))
        seen.add(family.id)

    nurse_user_id = db.scalar(
        select(Nurse.user_id)
        .join(Visit, Visit.nurse_id == Nurse.id)
        .where(Visit.patient_id == patient.id, Visit.nurse_id.is_not(None))
        .order_by(Visit.scheduled_at.desc())
        .limit(1)
    )
    if nurse_user_id is not None and int(nurse_user_id) not in seen:
        nurse_user = db.get(User, int(nurse_user_id))
        if nurse_user is not None:
            people.append((nurse_user, "Nurse"))
            seen.add(nurse_user.id)

    admins = db.scalars(
        select(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
    ).all()
    for admin in admins:
        if admin.id not in seen:
            people.append((admin, "Admin"))
            seen.add(admin.id)

    return people


def _message_for(event: EscalationEvent, patient: Patient) -> str:
    return (
        f"{patient.name}: {event.summary}. {event.detail} "
        f"{clinical.EMERGENCY_BLOCK_TITLE}."
    ).strip()


def _step(
    db: Session,
    event: EscalationEvent,
    *,
    sequence: int,
    actor: str,
    channel: str,
    target: str,
    status: EscalationStepStatus,
    detail: str,
    recipient_user_id: int | None = None,
    delivery_log_id: int | None = None,
    occurred_at: datetime | None = None,
) -> EscalationStep:
    step = EscalationStep(
        event_id=event.id,
        sequence=sequence,
        actor=actor,
        channel=channel,
        target=target,
        recipient_user_id=recipient_user_id,
        status=status,
        detail=detail,
        delivery_log_id=delivery_log_id,
        occurred_at=occurred_at or now(),
    )
    db.add(step)
    return step


def add_step(
    db: Session,
    event: EscalationEvent,
    *,
    actor: str,
    channel: str,
    target: str,
    detail: str,
    status: EscalationStepStatus = EscalationStepStatus.DELIVERED,
) -> EscalationStep:
    """Append a manual step — a phone call an admin actually made."""
    highest = max((s.sequence for s in event.steps), default=0)
    step = _step(
        db,
        event,
        sequence=highest + 1,
        actor=actor,
        channel=channel,
        target=target,
        status=status,
        detail=detail,
    )
    db.flush()
    return step


# --------------------------------------------------------------------------
# Working the queue
# --------------------------------------------------------------------------


def _refresh_sla(event: EscalationEvent, as_of: datetime | None = None) -> EscalationEvent:
    """Stamp the breach once it happens, so it survives the constants changing."""
    if event.status != EscalationStatus.RESOLVED and not event.breached_sla:
        if (as_of or now()) > event.sla_due_at:
            event.breached_sla = True
    return event


def acknowledge(db: Session, event: EscalationEvent, user: User) -> EscalationEvent:
    if event.status != EscalationStatus.OPEN:
        raise BadRequestError("This escalation has already been picked up.")
    _refresh_sla(event)
    event.status = EscalationStatus.ACKNOWLEDGED
    event.acknowledged_by = user.id
    event.acknowledged_at = now()
    add_step(
        db,
        event,
        actor="Admin",
        channel="in_app",
        target=user.name,
        detail=f"{user.name} picked this up.",
    )
    db.flush()
    return event


def resolve(
    db: Session, event: EscalationEvent, user: User, note: str | None = None
) -> EscalationEvent:
    if event.status == EscalationStatus.RESOLVED:
        raise BadRequestError("This escalation is already resolved.")
    _refresh_sla(event)
    if event.acknowledged_by is None:
        event.acknowledged_by = user.id
        event.acknowledged_at = now()
    event.status = EscalationStatus.RESOLVED
    event.resolved_by = user.id
    event.resolved_at = now()
    event.resolution_note = (note or "").strip() or None
    add_step(
        db,
        event,
        actor="Admin",
        channel="in_app",
        target=user.name,
        detail=(note or "").strip() or "Closed.",
    )
    db.flush()
    return event


def _loaded(query):
    return query.options(
        selectinload(EscalationEvent.steps), selectinload(EscalationEvent.patient)
    )


def list_events(
    db: Session,
    *,
    status: EscalationStatus | None = None,
    patient_id: int | None = None,
    limit: int = 100,
) -> list[EscalationEvent]:
    """Open first, soonest deadline first — the order an operator works them in."""
    query = _loaded(select(EscalationEvent))
    if status is not None:
        query = query.where(EscalationEvent.status == status)
    if patient_id is not None:
        query = query.where(EscalationEvent.patient_id == patient_id)

    events = list(
        db.scalars(
            query.order_by(EscalationEvent.sla_due_at, EscalationEvent.id.desc()).limit(limit)
        )
    )
    for event in events:
        _refresh_sla(event)
    db.flush()
    events.sort(key=lambda e: (e.status == EscalationStatus.RESOLVED, e.sla_due_at))
    return events


def get_for_user(db: Session, user: User, event_id: int) -> EscalationEvent:
    """Someone else's escalation is a 404, exactly as their patient is."""
    from ..core.dependencies import authorize_patient

    event = db.scalar(_loaded(select(EscalationEvent)).where(EscalationEvent.id == event_id))
    if event is None:
        raise NotFoundError("Escalation not found.")
    try:
        authorize_patient(db, user, event.patient_id)
    except NotFoundError:
        raise NotFoundError("Escalation not found.") from None
    _refresh_sla(event)
    return event


# --------------------------------------------------------------------------
# Hospital coordination
# --------------------------------------------------------------------------


def request_hospital(
    db: Session,
    *,
    patient: Patient,
    user: User,
    hospital_name: str,
    reason: str,
    department: str | None = None,
    ambulance_required: bool = False,
    preferred_at: datetime | None = None,
    as_of: datetime | None = None,
    notify: bool = True,
) -> HospitalBooking:
    """Ask the team to coordinate a hospital visit.

    An ambulance request runs on the **critical** clock and opens an escalation
    alongside the booking; a routine referral does not. Both durations are
    `ASSUMED` and both come from `core/clinical.py`.

    No hospital partnerships are modelled — DoorDoctor is pre-launch, and a
    partner list would be invented traction. The row records the hospital the
    family or the admin *named*; the coordination is a human doing it, and this
    is how the family can see that it is being done.
    """
    moment = as_of or now()
    minutes = (
        clinical.AMBULANCE_SLA_MINUTES
        if ambulance_required
        else clinical.HOSPITAL_BOOKING_SLA_MINUTES
    )

    booking = HospitalBooking(
        patient_id=patient.id,
        hospital_name=hospital_name.strip(),
        department=(department or "").strip() or None,
        reason=reason.strip(),
        ambulance_required=ambulance_required,
        preferred_at=preferred_at,
        status=HospitalBookingStatus.REQUESTED,
        requested_by=user.id,
        requested_at=moment,
        sla_minutes=minutes,
        sla_due_at=moment + timedelta(minutes=minutes),
    )
    db.add(booking)
    db.flush()

    if ambulance_required:
        event = open_event(
            db,
            patient=patient,
            trigger=EscalationTrigger.HOSPITAL_BOOKING,
            severity=AlertSeverity.CRITICAL,
            summary=f"Ambulance requested for {patient.name}",
            detail=f"{hospital_name.strip()} — {reason.strip()}",
            trigger_id=booking.id,
            as_of=moment,
            notify=notify,
        )
        booking.escalation_event_id = event.id
        db.flush()

    return booking


def update_hospital(
    db: Session,
    booking: HospitalBooking,
    user: User,
    *,
    status: HospitalBookingStatus | None = None,
    confirmation_detail: str | None = None,
    notes: str | None = None,
) -> HospitalBooking:
    _refresh_booking_sla(booking)
    if status is not None:
        if booking.status == HospitalBookingStatus.CANCELLED:
            raise BadRequestError("This request was cancelled.")
        booking.status = status
        if status == HospitalBookingStatus.CONFIRMED and booking.confirmed_at is None:
            booking.confirmed_at = now()
    if confirmation_detail is not None:
        booking.confirmation_detail = confirmation_detail.strip() or None
    if notes is not None:
        booking.notes = notes.strip() or None
    booking.handled_by = user.id
    db.flush()
    return booking


def _refresh_booking_sla(booking: HospitalBooking, as_of: datetime | None = None) -> HospitalBooking:
    settled = (HospitalBookingStatus.CONFIRMED, HospitalBookingStatus.ADMITTED)
    if booking.status not in settled and not booking.breached_sla:
        if (as_of or now()) > booking.sla_due_at:
            booking.breached_sla = True
    return booking


def list_hospital_bookings(
    db: Session, *, status: HospitalBookingStatus | None = None, patient_id: int | None = None
) -> list[HospitalBooking]:
    query = select(HospitalBooking).options(selectinload(HospitalBooking.patient))
    if status is not None:
        query = query.where(HospitalBooking.status == status)
    if patient_id is not None:
        query = query.where(HospitalBooking.patient_id == patient_id)
    bookings = list(db.scalars(query.order_by(HospitalBooking.sla_due_at).limit(100)))
    for booking in bookings:
        _refresh_booking_sla(booking)
    db.flush()
    return bookings


def get_booking_for_user(db: Session, user: User, booking_id: int) -> HospitalBooking:
    from ..core.dependencies import authorize_patient

    booking = db.scalar(
        select(HospitalBooking)
        .options(selectinload(HospitalBooking.patient))
        .where(HospitalBooking.id == booking_id)
    )
    if booking is None:
        raise NotFoundError("Hospital request not found.")
    try:
        authorize_patient(db, user, booking.patient_id)
    except NotFoundError:
        raise NotFoundError("Hospital request not found.") from None
    _refresh_booking_sla(booking)
    return booking


# --------------------------------------------------------------------------
# Serialization
# --------------------------------------------------------------------------


def serialize(event: EscalationEvent, *, include_steps: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": event.id,
        "patient_id": event.patient_id,
        "patient_name": event.patient.name if event.patient else None,
        "trigger": event.trigger.value,
        "trigger_id": event.trigger_id,
        "alert_id": event.alert_id,
        "severity": event.severity.value,
        "status": event.status.value,
        "summary": event.summary,
        "detail": event.detail,
        "opened_at": event.opened_at,
        "sla_minutes": event.sla_minutes,
        "sla_due_at": event.sla_due_at,
        "breached_sla": event.breached_sla,
        "acknowledged_by": event.acknowledged_by,
        "acknowledged_at": event.acknowledged_at,
        "resolved_by": event.resolved_by,
        "resolved_at": event.resolved_at,
        "resolution_note": event.resolution_note,
        "ladder": list(clinical.ESCALATION_LADDER),
    }
    if include_steps:
        payload["steps"] = [serialize_step(s) for s in event.steps]
    return payload


def serialize_step(step: EscalationStep) -> dict[str, Any]:
    return {
        "id": step.id,
        "sequence": step.sequence,
        "actor": step.actor,
        "channel": step.channel,
        "target": step.target,
        "recipient_user_id": step.recipient_user_id,
        "status": step.status.value,
        "detail": step.detail,
        "occurred_at": step.occurred_at,
    }


def serialize_booking(booking: HospitalBooking) -> dict[str, Any]:
    return {
        "id": booking.id,
        "patient_id": booking.patient_id,
        "patient_name": booking.patient.name if booking.patient else None,
        "hospital_name": booking.hospital_name,
        "department": booking.department,
        "reason": booking.reason,
        "ambulance_required": booking.ambulance_required,
        "preferred_at": booking.preferred_at,
        "status": booking.status.value,
        "requested_by": booking.requested_by,
        "requested_at": booking.requested_at,
        "sla_minutes": booking.sla_minutes,
        "sla_due_at": booking.sla_due_at,
        "breached_sla": booking.breached_sla,
        "confirmed_at": booking.confirmed_at,
        "confirmation_detail": booking.confirmation_detail,
        "handled_by": booking.handled_by,
        "escalation_event_id": booking.escalation_event_id,
        "notes": booking.notes,
    }
