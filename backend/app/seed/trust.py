"""The Phase 10 trust layer of the seed: credentials, and located check-ins.

Two rules this module exists to keep:

1. **A seeded classification is the classifier's own output.** Nothing here
   types `"verified"` into a column. Coordinates are placed at a chosen distance
   and `location_service.classify` decides what they mean, so a demo showing
   `verified` is showing the same arithmetic a live check-in runs. If the
   geofence in `core/ops.py` changes, the seed changes with it.
2. **A verified credential carries its verifier.** `nurse_service` refuses to
   produce one without a name and a date, and so does this.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    CredentialKind,
    Nurse,
    NurseCredential,
    User,
    UserRole,
    VerificationStatus,
    Visit,
)
from ..database import now
from ..services import location_service
from . import demo_data, generators


def seed_credentials(
    db: Session,
    nurse: Nurse,
    *,
    verifier: User,
    verified: bool,
    today: date,
    rng: random.Random,
) -> list[NurseCredential]:
    """A registration and a background check for one nurse.

    An unverified nurse still *has* the rows — the claim was recorded, it has
    simply not been checked yet. That is what an onboarding queue looks like,
    and a roster where unverified means "no credential on file" would give an
    admin nothing to verify.
    """
    title = demo_data.CREDENTIAL_TITLES.get(nurse.credential, nurse.credential)
    body = demo_data.CREDENTIAL_BODIES.get(nurse.credential, "Karnataka State Nursing Council")
    issued = today - timedelta(days=rng.randint(400, 3600))

    registration = NurseCredential(
        nurse_id=nurse.id,
        kind=CredentialKind.NURSING_REGISTRATION,
        title=title,
        issuing_body=body,
        registration_number=f"KSNC/{issued.year}/{rng.randint(10000, 99999)}",
        issued_on=issued,
        expires_on=issued + timedelta(days=365 * 10),
        verification_status=VerificationStatus.PENDING,
    )
    background = NurseCredential(
        nurse_id=nurse.id,
        kind=CredentialKind.BACKGROUND_CHECK,
        title="Police verification",
        issuing_body=demo_data.BACKGROUND_CHECK_BODY,
        issued_on=today - timedelta(days=rng.randint(30, 900)),
        verification_status=VerificationStatus.PENDING,
    )

    if verified:
        for credential in (registration, background):
            credential.verification_status = VerificationStatus.VERIFIED
            credential.verified_by = verifier.id
            credential.verified_by_name = verifier.name
            # A verification happened on a day somebody was at work, not at the
            # instant the seed ran. `verified_at` reads as history everywhere it
            # is rendered, so it has to *be* history.
            credential.verified_at = _at_noon(today - timedelta(days=rng.randint(5, 200)))

    db.add_all([registration, background])
    db.flush()
    return [registration, background]


def _at_noon(day: date):
    from datetime import datetime, time

    return datetime.combine(day, time(hour=12))


def locate_checkin(
    visit: Visit,
    *,
    home_lat: float | None,
    home_lng: float | None,
    metres: float | None,
    bearing_deg: float = 45.0,
    accuracy_m: float | None = 14.0,
) -> None:
    """Place a completed visit's check-in and let the classifier judge it.

    `metres=None` means the device reported nothing — the honest `unavailable`
    case, which the demo needs at least one of. It is not a bug being seeded; it
    is the outcome a nurse in a basement flat produces every week.
    """
    if metres is None or home_lat is None or home_lng is None:
        fix_lat = fix_lng = None
        accuracy = None
    else:
        fix_lat, fix_lng = generators.offset_coordinates(
            home_lat, home_lng, metres=metres, bearing_deg=bearing_deg
        )
        accuracy = accuracy_m

    verdict = location_service.classify(
        fix_lat=fix_lat,
        fix_lng=fix_lng,
        home_lat=home_lat,
        home_lng=home_lng,
        accuracy_m=accuracy,
    )
    visit.checkin_lat = fix_lat
    visit.checkin_lng = fix_lng
    visit.location_source = verdict.source
    visit.location_status = verdict.status
    visit.location_distance_m = verdict.distance_m
    visit.location_accuracy_m = verdict.accuracy_m
    visit.location_detail = verdict.detail


# --------------------------------------------------------------------------
# The Phase 10 layer of the seed
#
# `FULL` only. `SMALL` — which `tests/conftest.py` seeds — stays exactly as it
# was, the same rule Phase 9's clinical layer follows, so no existing test
# changes because a demo grew a feature.
# --------------------------------------------------------------------------


def _medication_history(db: Session, records, actors: list[User]) -> int:
    """A believable prescription history for the patients a demo will open.

    Every medication gets its `started` row, and a handful of patients get a
    real change on top: a dose halved after a reading pattern, a time moved
    because the family asked, one drug stopped. Backdated, because history that
    all happened at the instant the seed ran is not history.
    """
    from ..models import Medication, MedicationChangeKind
    from ..services import medication_service

    admin = actors[0]
    written = 0
    for record in records:
        medications = list(
            db.scalars(
                select(Medication)
                .where(Medication.patient_id == record.patient.id)
                .order_by(Medication.id)
            )
        )
        if not medications:
            continue

        started_at = record.patient.created_at
        for medication in medications:
            medication_service.record_change(
                db,
                medication,
                kind=MedicationChangeKind.STARTED,
                new_value=(
                    f"{medication.dosage}, {medication.frequency} at {medication.scheduled_time}"
                ),
                actor=admin,
                at=started_at,
            )
            written += 1

        if record.slot % 4 != 0:
            continue

        first = medications[0]
        medication_service.record_change(
            db,
            first,
            kind=MedicationChangeKind.DOSAGE_CHANGED,
            previous_value=first.dosage,
            new_value=f"{first.dosage} (reviewed)",
            reason="Dose reviewed with the family after a run of higher readings.",
            actor=admin,
            at=started_at + timedelta(days=40),
        )
        written += 1
        if len(medications) > 1:
            second = medications[1]
            medication_service.record_change(
                db,
                second,
                kind=MedicationChangeKind.SCHEDULE_CHANGED,
                previous_value=f"{second.frequency} at {second.scheduled_time}",
                new_value=f"{second.frequency} at 09:00",
                reason="Moved later so it is taken after breakfast.",
                actor=admin,
                at=started_at + timedelta(days=61),
            )
            written += 1
    return written


def _pill_organiser(db: Session, records, nurse_users: list[User]) -> int:
    """Fills for the patients whose families bought the ₹199 add-on.

    Only a handful, and only recent ones. Every fill runs through
    `medication_service.record_fill`, so the "billed once a month, not once a
    fill" rule is re-proved on every seed run rather than asserted once.
    """
    from ..services import medication_service

    nurse = nurse_users[0]
    filled = 0
    for record in records:
        if record.slot % 5 != 0:
            continue
        for weeks_ago in (3, 2, 1):
            medication_service.record_fill(
                db,
                patient=record.patient,
                filled_by=nurse,
                compartments_filled=28 if weeks_ago != 2 else 24,
                note=None if weeks_ago != 2 else "Sunday evening doses left out for the family.",
                as_of=now() - timedelta(weeks=weeks_ago),
            )
            filled += 1
    return filled


def build(db: Session, records) -> dict[str, int]:
    """Layer Phase 10's trust and operations data over a populated database."""
    admins = list(db.scalars(select(User).where(User.role == UserRole.ADMIN).order_by(User.id)))
    nurse_users = list(db.scalars(select(User).where(User.role == UserRole.NURSE).order_by(User.id)))

    return {
        "medication_changes": _medication_history(db, records, admins),
        "organiser_fills": _pill_organiser(db, records, nurse_users),
    }
