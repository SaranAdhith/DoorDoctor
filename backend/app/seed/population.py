"""The wider operating business: staff, families, ninety days of care, alerts.

Built *around* `core.py`, never instead of it. Everything the test suite asserts
by hand stays exactly where it was; this module adds the twenty-seven other
patients, the thirteen other nurses, the two other admins, the sixteen other
families and the ninety days of visits, readings, doses and alerts that make
every screen look like an operating business rather than a fixture.

Three properties are worth knowing before changing anything here:

1. **Alerts are raised by the real threshold engine.** Nothing writes an `Alert`
   row. Readings are generated safely inside each patient's configured range and
   then `demo_data.EXCURSIONS` deliberately pushes exactly thirty-four of them
   out, so "a breaching reading always has an alert" is true of the seed for the
   same reason it is true in production.
2. **Today is built explicitly**, because §2.4 specifies its shape — six
   scheduled, one unassigned, one in progress. The cadence generator covers
   yesterday and earlier, and tomorrow and later.
3. **Anitha keeps exactly one open visit today**, Lakshmi's 10:30. Every other
   visit today is routed to another nurse. `tests/conftest.py::scheduled_visit_id`
   takes the first open visit on her board; a second one would silently point the
   alert tests at a different patient.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import now
from ..models import (
    Alert,
    AlertStatus,
    Lead,
    LeadKind,
    LeadStatus,
    Medication,
    MedicationLog,
    MedicationLogStatus,
    Notification,
    Nurse,
    NurseStatus,
    Patient,
    PatientStatus,
    User,
    UserRole,
    VerificationStatus,
    Visit,
    VisitStatus,
    Vital,
)
from ..services import alert_service, vitals_service
from . import business, clinical, demo_data, generators, trust
from .core import CORE_HISTORY_DAYS, HISTORY as CORE_HISTORY, CoreResult, at, demo_password_hash

# Thresholds are identical for every patient in this demo, so the clamp table
# the generator needs is built once rather than per reading.
_THRESHOLD_RANGE: dict[str, tuple[float, float]] = dict(vitals_service.DEFAULT_THRESHOLDS)

_VISIT_MINUTES = 45


@dataclass
class PatientRecord:
    """One patient and everything the generators need to know about them."""

    slot: int
    patient: Patient
    conditions: tuple[str, ...]
    zone: int
    plan_code: str
    tenure_months: int
    medications: list[Medication] = field(default_factory=list)
    completed_visits: list[Visit] = field(default_factory=list)

    @property
    def rng(self) -> random.Random:
        """This patient's own stream, so adding a patient cannot reshuffle the others."""
        return random.Random(demo_data.RANDOM_SEED + self.slot)

    @property
    def history_days(self) -> int:
        """Nobody has more history than they have been a customer."""
        return min(90, max(14, self.tenure_months * 30))


# --------------------------------------------------------------------------
# Staff
# --------------------------------------------------------------------------


def _build_staff(db: Session, core: CoreResult) -> dict[int, list[Nurse]]:
    """The other two admins and the other thirteen nurses, rostered by zone."""
    rng = random.Random(demo_data.RANDOM_SEED + 500)
    today = now().date()
    for name, email, phone in demo_data.EXTRA_ADMINS:
        db.add(
            User(
                name=name,
                email=email,
                phone=phone,
                password_hash=demo_password_hash(),
                role=UserRole.ADMIN,
                is_active=True,
            )
        )

    by_zone: dict[int, list[Nurse]] = {index: [] for index in range(len(demo_data.ZONES))}
    by_zone[demo_data.KORAMANGALA].append(core.nurse)

    for spec in demo_data.EXTRA_NURSES:
        user = User(
            name=spec.name,
            email=spec.email,
            phone=spec.phone,
            password_hash=demo_password_hash(),
            role=UserRole.NURSE,
            is_active=True,
        )
        db.add(user)
        db.flush()
        nurse = Nurse(
            user_id=user.id,
            credential=spec.credential,
            verification_status=(
                VerificationStatus.VERIFIED if spec.verified else VerificationStatus.PENDING
            ),
            status=NurseStatus.ACTIVE if spec.active else NurseStatus.INACTIVE,
            # --- Phase 10 (§4.10) -----------------------------------------
            zone=demo_data.ZONES[spec.zone][0],
            joined_on=(now() - timedelta(days=rng.randint(90, 2200))).date(),
            languages=demo_data.LANGUAGES_BY_ZONE[spec.zone],
            years_experience=rng.randint(2, 18),
        )
        db.add(nurse)
        db.flush()
        # Every nurse has their credentials on file. Shalini's are pending, which
        # is what gives the admin verification queue something real to work — a
        # roster where unverified meant "nothing recorded" would leave nothing to
        # verify and no way to demonstrate the feature.
        trust.seed_credentials(
            db,
            nurse,
            verifier=core.admin_user,
            verified=spec.verified,
            today=today,
            rng=rng,
        )
        if spec.active:
            by_zone[spec.zone].append(nurse)

    db.flush()
    return by_zone


# --------------------------------------------------------------------------
# Families and patients
# --------------------------------------------------------------------------


def _medications_for(db: Session, patient: Patient, conditions: tuple[str, ...]) -> list[Medication]:
    """Prescribe by condition, so the schedule matches the diagnosis."""
    specs: list[tuple[str, str, str, str]] = []
    for condition in conditions:
        specs.extend(demo_data.MEDICATIONS_BY_CONDITION.get(condition, ()))
    specs.append(demo_data.BASELINE_MEDICATION)

    created: list[Medication] = []
    for name, dosage, frequency, scheduled_time in specs:
        medication = Medication(
            patient_id=patient.id,
            name=name,
            dosage=dosage,
            frequency=frequency,
            scheduled_time=scheduled_time,
            active=True,
        )
        db.add(medication)
        created.append(medication)
    return created


def _add_patient(
    db: Session,
    *,
    spec: demo_data.PatientSpec,
    family: User,
    zone: int,
    tenure_months: int,
    rng: random.Random,
) -> Patient:
    zone_name, pincode = demo_data.ZONES[zone]
    home = generators.home_coordinates(rng, zone)
    patient = Patient(
        name=spec.name,
        age=spec.age,
        gender=spec.gender,
        address=f"{spec.street}, Bengaluru {pincode}",
        emergency_contact=f"{family.name} - {family.phone}",
        family_user_id=family.id,
        status=PatientStatus.ACTIVE,
        # Enrolled when the family subscribed, not when the seed ran.
        created_at=at(tenure_months * 30),
        # --- Phase 10 (§4.11, §4.17) ---------------------------------------
        # The zone is now a column because the admin zone view queries it, and
        # every home carries a coordinate because without one a check-in can
        # only ever be classified `unavailable`.
        zone=zone_name,
        home_lat=home[0],
        home_lng=home[1],
    )
    db.add(patient)
    return patient


def _build_patients(db: Session, core: CoreResult) -> list[PatientRecord]:
    """Every patient in slot order. Slot 0 is Lakshmi and slot 1 is Meera's father."""
    records: list[PatientRecord] = [
        PatientRecord(
            slot=0,
            patient=core.patient,
            # Read off her medication schedule rather than restated: she is on
            # amlodipine and metformin, so this is what she is being treated for.
            conditions=("Hypertension", "Type 2 diabetes"),
            zone=demo_data.KORAMANGALA,
            plan_code="care_plus",
            tenure_months=business.SUBSCRIPTION_HISTORY_MONTHS,
        )
    ]

    # Meera already exists — `business.seed_business` created her to carry the
    # referral story. Phase 5 gives her the parent she is subscribed for.
    meera = db.scalar(select(User).where(User.email == "meera@doordoctor.in"))
    assert meera is not None, "business.seed_business must run before the population"
    meera_patient = _add_patient(
        db,
        spec=demo_data.MEERA_PATIENT,
        family=meera,
        zone=2,
        tenure_months=3,
        rng=random.Random(demo_data.RANDOM_SEED + 1),
    )
    db.flush()
    records.append(
        PatientRecord(
            slot=1,
            patient=meera_patient,
            conditions=demo_data.MEERA_PATIENT.conditions,
            zone=2,
            plan_code="essential",
            tenure_months=3,
        )
    )

    slot = 2
    for spec in demo_data.EXTRA_FAMILIES:
        family = User(
            name=spec.name,
            email=spec.email,
            phone=spec.phone,
            password_hash=demo_password_hash(),
            role=UserRole.FAMILY,
            is_active=True,
        )
        db.add(family)
        db.flush()
        business.subscribe_family(db, family, spec)

        for patient_spec in spec.patients:
            patient = _add_patient(
                db,
                spec=patient_spec,
                family=family,
                zone=spec.zone,
                tenure_months=spec.tenure_months,
                rng=random.Random(demo_data.RANDOM_SEED + slot),
            )
            db.flush()
            records.append(
                PatientRecord(
                    slot=slot,
                    patient=patient,
                    conditions=patient_spec.conditions,
                    zone=spec.zone,
                    plan_code=spec.plan_code,
                    tenure_months=spec.tenure_months,
                )
            )
            slot += 1

    db.flush()

    # Lakshmi's thresholds are written by `core.py`; everyone else gets the demo
    # defaults through the service, so there is one definition of "normal".
    for record in records[1:]:
        vitals_service.create_default_thresholds(db, record.patient)
        record.medications = _medications_for(db, record.patient, record.conditions)
    records[0].medications = list(
        db.scalars(select(Medication).where(Medication.patient_id == core.patient.id))
    )
    db.flush()
    return records


# --------------------------------------------------------------------------
# Visits, readings and doses
# --------------------------------------------------------------------------


def _excursions_by_patient() -> dict[int, list[demo_data.Excursion]]:
    grouped: dict[int, list[demo_data.Excursion]] = {}
    for excursion in demo_data.EXCURSIONS:
        grouped.setdefault(excursion.patient_slot, []).append(excursion)
    return grouped


# --------------------------------------------------------------------------
# Check-in locations (§4.11)
#
# ASSUMED, and chosen to make the demo honest rather than flattering: roughly
# one visit in twelve has no location at all and one in forty is recorded from
# outside the geofence. A dataset where every check-in is `verified` would teach
# an evaluator that the badge is decoration.
#
# Nothing here writes a classification. The coordinates are placed and
# `location_service` decides, so the seeded verdict is the live arithmetic.
# --------------------------------------------------------------------------

_UNLOCATED_EVERY = 12
_OUT_OF_RANGE_EVERY = 40


def _locate(record: PatientRecord, visit: Visit, index: int, rng: random.Random) -> None:
    key = record.slot * 7 + index
    if key % _OUT_OF_RANGE_EVERY == 0:
        metres = rng.uniform(240.0, 1400.0)
    elif key % _UNLOCATED_EVERY == 0:
        metres = None
    else:
        metres = rng.uniform(4.0, 90.0)

    trust.locate_checkin(
        visit,
        home_lat=record.patient.home_lat,
        home_lng=record.patient.home_lng,
        metres=metres,
        bearing_deg=(key * 31) % 360,
    )


def _build_visits(
    db: Session,
    records: list[PatientRecord],
    nurses_by_zone: dict[int, list[Nurse]],
    core: CoreResult,
    profile: demo_data.SeedProfile,
) -> list[tuple[PatientRecord, Vital, demo_data.Excursion]]:
    """Ninety days of visits, readings and doses for every patient.

    Returns the readings an excursion pushed out of range, so the caller can run
    them through the alert engine once every row exists.
    """
    excursions = _excursions_by_patient()
    breaches: list[tuple[PatientRecord, Vital, demo_data.Excursion]] = []

    for record in records:
        rng = record.rng
        per_week = demo_data.VISITS_PER_WEEK[record.plan_code]
        # Lakshmi's last eight days are the hand-written history the suite
        # asserts against, so the generator fills in behind them and stops.
        skip_recent = CORE_HISTORY_DAYS if record.slot == 0 else 0
        rotation = nurses_by_zone[record.zone] or [core.nurse]
        if record.slot != 0:
            # Continuity of care: a patient sees two familiar nurses, not
            # whoever the scheduler happened to have free.
            rotation = [rotation[record.slot % len(rotation)], rotation[(record.slot + 1) % len(rotation)]]

        schedule = generators.visit_schedule(
            slot=record.slot,
            per_week=per_week,
            history_days=record.history_days,
            forward_days=profile.forward_days,
            skip_recent_days=skip_recent,
            rng=rng,
        )

        visits: list[tuple[Visit, generators.ScheduledVisit]] = []
        for index, planned in enumerate(schedule):
            scheduled_at = at(planned.days_ago, hour=planned.hour, minute=planned.minute)
            status = VisitStatus(planned.status)
            completed = status == VisitStatus.COMPLETED
            visit = Visit(
                patient_id=record.patient.id,
                nurse_id=rotation[index % len(rotation)].id,
                scheduled_at=scheduled_at,
                status=status,
                checkin_at=scheduled_at if completed else None,
                checkout_at=scheduled_at + timedelta(minutes=_VISIT_MINUTES) if completed else None,
                notes=_visit_note(planned.status, index),
            )
            if completed:
                _locate(record, visit, index, rng)
            db.add(visit)
            visits.append((visit, planned))
        db.flush()

        completed_visits = [visit for visit, planned in visits if planned.status == "completed"]
        # Lakshmi's four core visits are newer than anything generated here, so
        # they belong at the end of her timeline for excursion indexing.
        if record.slot == 0:
            completed_visits += list(
                db.scalars(
                    select(Visit)
                    .where(
                        Visit.patient_id == record.patient.id,
                        Visit.status == VisitStatus.COMPLETED,
                        Visit.id.notin_([v.id for v in completed_visits]),
                    )
                    .order_by(Visit.scheduled_at)
                )
            )
        record.completed_visits = completed_visits

        # `visits_back` counts from the most recent completed visit.
        planned_excursions: dict[int, demo_data.Excursion] = {}
        for excursion in excursions.get(record.slot, []):
            index = len(completed_visits) - 1 - excursion.visits_back
            if index < 0:  # pragma: no cover - guarded by test_seed
                raise ValueError(
                    f"Excursion {excursion} is further back than patient slot "
                    f"{record.slot} has visits ({len(completed_visits)})."
                )
            planned_excursions[index] = excursion

        # Lakshmi's newest visits already carry hand-written readings and the
        # 13-of-15 dose log the suite asserts; the generator must not overwrite
        # either, so it stops short of them.
        hand_written = len(CORE_HISTORY) if record.slot == 0 else 0
        breaches.extend(
            _record_readings(db, record, completed_visits, planned_excursions, rng, hand_written)
        )
        _record_doses(db, record, completed_visits, core, hand_written)

    db.flush()
    return breaches


def _visit_note(status: str, index: int) -> str | None:
    if status == "missed":
        return demo_data.MISSED_REASON
    if status == "cancelled":
        return demo_data.CANCELLED_REASON
    return generators.cycle(demo_data.VISIT_NOTES, index)


def _record_readings(
    db: Session,
    record: PatientRecord,
    completed_visits: list[Visit],
    planned_excursions: dict[int, demo_data.Excursion],
    rng: random.Random,
    hand_written: int,
) -> list[tuple[PatientRecord, Vital, demo_data.Excursion]]:
    """One reading per completed visit, following the patient's arc."""
    baseline = generators.baseline_for(record.conditions, record.patient.age, rng)
    arc = generators.arc_for(record.conditions, rng)
    phase = rng.uniform(0, 6.28)
    total = len(completed_visits)
    breaches: list[tuple[PatientRecord, Vital, demo_data.Excursion]] = []

    for index, visit in enumerate(completed_visits):
        if index >= total - hand_written:
            break  # the newest visits already carry hand-written readings
        values = generators.clamp_inside(
            generators.reading(baseline, arc, index, total, phase, rng), _THRESHOLD_RANGE
        )
        excursion = planned_excursions.get(index)
        if excursion is not None:
            values = generators.apply_excursion(values, excursion.kind)

        vital = Vital(
            patient_id=record.patient.id,
            visit_id=visit.id,
            recorded_at=visit.scheduled_at + timedelta(minutes=12),
            threshold_breached=excursion is not None,
            **values,
        )
        db.add(vital)
        if excursion is not None:
            breaches.append((record, vital, excursion))
    db.flush()
    return breaches


def _record_doses(
    db: Session,
    record: PatientRecord,
    completed_visits: list[Visit],
    core: CoreResult,
    hand_written: int,
) -> None:
    """Supervised doses across the window, landing on this patient's adherence target."""
    medications = record.medications
    if not medications:
        return

    visits = completed_visits[: len(completed_visits) - hand_written] if hand_written else completed_visits
    doses = len(visits) * len(medications)
    plan = generators.adherence_plan(doses, generators.adherence_target(record.slot))

    position = 0
    for visit in visits:
        for medication in medications:
            status_value = plan[position]
            position += 1
            db.add(
                MedicationLog(
                    medication_id=medication.id,
                    visit_id=visit.id,
                    status=MedicationLogStatus(status_value),
                    reason=demo_data.SKIP_REASONS.get(status_value),
                    recorded_at=visit.scheduled_at + timedelta(minutes=20),
                    recorded_by=core.nurse_user.id,
                )
            )


# --------------------------------------------------------------------------
# Alerts
# --------------------------------------------------------------------------


def _raise_alerts(
    db: Session,
    breaches: list[tuple[PatientRecord, Vital, demo_data.Excursion]],
    admins: list[User],
) -> tuple[int, int]:
    """Run every excursion through the real alert engine, then work the queue.

    Thirty are worked through acknowledgement and resolution with believable
    handling times; four are left open. An alert queue where everything resolved
    within seconds is not a demonstration of an SLA.
    """
    resolved_count = 0
    active_count = 0

    ordered = sorted(breaches, key=lambda item: item[1].recorded_at)
    for index, (record, vital, excursion) in enumerate(ordered):
        thresholds = vitals_service.load_thresholds(db, record.patient.id)
        found = vitals_service.evaluate_thresholds(vital, thresholds)
        if not found:  # pragma: no cover - guarded by test_seed
            raise ValueError(
                f"Excursion '{excursion.kind}' is inside the configured range and would "
                "raise no alert. Every excursion must breach something."
            )

        alert = alert_service.create_threshold_alert(
            db, patient=record.patient, vital=vital, breaches=found
        )
        # `create_threshold_alert` stamps the real clock, which is right in
        # production and wrong here — the whole queue would be raised today.
        alert_service.backdate(alert, vital.recorded_at)

        if excursion.resolved:
            ack = generators.cycle(demo_data.ACK_MINUTES, index)
            close = generators.cycle(demo_data.RESOLVE_MINUTES, index)
            alert.status = AlertStatus.RESOLVED
            alert.acknowledged_by = generators.cycle(admins, index).id
            alert.acknowledged_at = alert.created_at + timedelta(minutes=ack)
            alert.resolved_at = alert.created_at + timedelta(minutes=ack + close)
            resolved_count += 1
        else:
            active_count += 1

        db.flush()
        _settle_notifications(db, alert, read=excursion.resolved)

    db.flush()
    return resolved_count, active_count


def _settle_notifications(db: Session, alert: Alert, *, read: bool) -> None:
    """Backdate the notifications an alert produced, and read the closed ones.

    Without this the bell shows 136 unread items dated today. Only the four open
    alerts should still be asking for attention.
    """
    for notification in db.scalars(select(Notification).where(Notification.alert_id == alert.id)):
        notification.created_at = alert.created_at
        notification.read = read


# --------------------------------------------------------------------------
# Today's board — 6 scheduled / 1 unassigned / 1 in-progress (§2.4)
# --------------------------------------------------------------------------

# Slots chosen across zones so the board is not one nurse's day. Lakshmi's 10:30
# is created by `core.py` and is the sixth scheduled visit.
_TODAY_COMPLETED_PATIENTS = (2, 5, 9, 12, 16, 20, 24)
_TODAY_IN_PROGRESS_PATIENT = 7
_TODAY_UNASSIGNED_PATIENT = 11
_TODAY_SCHEDULED_PATIENTS = (14, 17, 21, 25, 3)


def _today_nurse(record: PatientRecord, nurses_by_zone: dict[int, list[Nurse]], core: CoreResult) -> Nurse:
    """Any nurse in the patient's zone except Anitha — today's board is hers alone
    for Lakshmi, and a second open visit would break `scheduled_visit_id`."""
    candidates = [n for n in nurses_by_zone[record.zone] if n.id != core.nurse.id]
    if not candidates:  # pragma: no cover - every zone is staffed by at least two
        candidates = [n for zone in nurses_by_zone.values() for n in zone if n.id != core.nurse.id]
    return generators.cycle(candidates, record.slot)


def _build_today(
    db: Session,
    records: list[PatientRecord],
    nurses_by_zone: dict[int, list[Nurse]],
    core: CoreResult,
) -> None:
    by_slot = {record.slot: record for record in records}

    def _visit(slot: int, hour: int, minute: int, status: VisitStatus, assign: bool = True) -> Visit:
        record = by_slot[slot]
        scheduled_at = at(0, hour=hour, minute=minute)
        completed = status == VisitStatus.COMPLETED
        started = status in (VisitStatus.COMPLETED, VisitStatus.IN_PROGRESS)
        visit = Visit(
            patient_id=record.patient.id,
            nurse_id=_today_nurse(record, nurses_by_zone, core).id if assign else None,
            scheduled_at=scheduled_at,
            status=status,
            checkin_at=scheduled_at if started else None,
            checkout_at=scheduled_at + timedelta(minutes=_VISIT_MINUTES) if completed else None,
            notes=generators.cycle(demo_data.VISIT_NOTES, slot) if started else None,
        )
        if started:
            _locate(record, visit, slot, record.rng)
        db.add(visit)
        db.flush()
        if completed:
            _today_reading(db, record, visit)
        return visit

    for index, slot in enumerate(_TODAY_COMPLETED_PATIENTS):
        hour, minute = demo_data.TODAY_COMPLETED_TIMES[index]
        _visit(slot, hour, minute, VisitStatus.COMPLETED)

    hour, minute = demo_data.TODAY_IN_PROGRESS_TIME
    _visit(_TODAY_IN_PROGRESS_PATIENT, hour, minute, VisitStatus.IN_PROGRESS)

    hour, minute = demo_data.TODAY_UNASSIGNED_TIME
    _visit(_TODAY_UNASSIGNED_PATIENT, hour, minute, VisitStatus.SCHEDULED, assign=False)

    for index, slot in enumerate(_TODAY_SCHEDULED_PATIENTS):
        hour, minute = demo_data.TODAY_SCHEDULED_TIMES[index]
        _visit(slot, hour, minute, VisitStatus.SCHEDULED)

    db.flush()


def _today_reading(db: Session, record: PatientRecord, visit: Visit) -> None:
    """A reading for a visit finished this morning, continuing the patient's arc."""
    rng = random.Random(demo_data.RANDOM_SEED + 1000 + record.slot)
    baseline = generators.baseline_for(record.conditions, record.patient.age, rng)
    arc = generators.arc_for(record.conditions, rng)
    # The far end of the arc, expressed without reference to how many visits the
    # patient has had, so `--demo-reset` reproduces this reading exactly.
    values = generators.clamp_inside(
        generators.reading(baseline, arc, 1, 2, 0.0, rng), _THRESHOLD_RANGE
    )
    db.add(
        Vital(
            patient_id=record.patient.id,
            visit_id=visit.id,
            recorded_at=visit.scheduled_at + timedelta(minutes=12),
            threshold_breached=False,
            **values,
        )
    )


# --------------------------------------------------------------------------
# Public enquiries (Phase 8)
# --------------------------------------------------------------------------


def _build_leads(db: Session, admins: list[User]) -> int:
    """Fill Admin -> Leads so the marketing site has somewhere to have landed.

    Rows are written directly rather than through `lead_service.create`, because
    that path is the *public* one: it commits per lead and it cannot backdate
    `created_at`, and a queue where every enquiry arrived in the same second is
    not a queue. This is the same reason `business.py` backdates `paid_at`
    instead of letting `mark_paid` stamp the real clock.
    """
    worker = admins[0] if admins else None
    for spec in demo_data.LEADS:
        arrived = now() - timedelta(hours=spec.hours_ago)
        status = LeadStatus(spec.status)
        handled = status != LeadStatus.NEW and worker is not None
        db.add(
            Lead(
                name=spec.name,
                email=spec.email,
                phone=spec.phone,
                city=spec.city,
                kind=LeadKind(spec.kind),
                message=spec.message,
                source_page=spec.source_page,
                status=status,
                admin_note=spec.admin_note,
                handled_by_user_id=worker.id if handled else None,
                # Worked a couple of hours after it arrived, never before it.
                handled_at=arrived + timedelta(hours=2) if handled else None,
                created_at=arrived,
            )
        )
    return len(demo_data.LEADS)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def build(db: Session, core: CoreResult, profile: demo_data.SeedProfile) -> dict[str, int]:
    """Build the wider population around the demo core."""
    nurses_by_zone = _build_staff(db, core)
    records = _build_patients(db, core)
    breaches = _build_visits(db, records, nurses_by_zone, core, profile)

    admins = list(db.scalars(select(User).where(User.role == UserRole.ADMIN).order_by(User.id)))
    resolved, active = _raise_alerts(db, breaches, admins)

    _build_today(db, records, nurses_by_zone, core)
    leads = _build_leads(db, admins)
    # Last, and deliberately: the safety score reads visits, doses, alerts,
    # screenings and device readings, so everything above has to exist first or
    # every score is computed with two of its six components missing.
    clinical_summary = clinical.build(db, records)
    # Phase 10 last: the medication history and the organiser fills are written
    # over medications and subscriptions that everything above created.
    trust_summary = trust.build(db, records, core)
    db.flush()

    return {
        "patients": len(records),
        "nurses": len(demo_data.EXTRA_NURSES) + 1,
        "families": len(demo_data.EXTRA_FAMILIES) + 2,
        "visits": int(db.scalar(select(func.count(Visit.id))) or 0),
        "readings": int(db.scalar(select(func.count(Vital.id))) or 0),
        "doses": int(db.scalar(select(func.count(MedicationLog.id))) or 0),
        "alerts_resolved": resolved,
        "alerts_active": active,
        "leads": leads,
        **clinical_summary,
        **trust_summary,
    }
