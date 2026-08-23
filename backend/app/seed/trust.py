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
    CareCircleRole,
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


# --------------------------------------------------------------------------
# Care circles (§4.13)
# --------------------------------------------------------------------------

# ASSUMED. Chosen so the demo contains the case the feature exists for: a person
# with no DoorDoctor login who is nonetheless the one who can be at the house in
# ten minutes. Lakshmi's circle is the one an evaluator will open.
LAKSHMI_CIRCLE: tuple[dict[str, object], ...] = (
    {
        "name": "Rohan D'Souza",
        "relationship_label": "Grandson",
        "phone": "+91 90000 10021",
        "email": "rohan.dsouza@example.in",
        "role": CareCircleRole.CONTRIBUTOR,
        "receives_alerts": True,
        "receives_reports": True,
    },
    {
        "name": "Vasanthi Rao",
        "relationship_label": "Neighbour",
        "phone": "+91 90000 10022",
        "role": CareCircleRole.EMERGENCY_CONTACT,
        "receives_alerts": True,
        "note": "Two doors down and has the spare key. Call her first if nobody answers.",
    },
    {
        "name": "Dr Suresh Iyer",
        "relationship_label": "Family physician",
        "phone": "+91 90000 10023",
        "role": CareCircleRole.VIEWER,
        "receives_reports": True,
    },
)

OTHER_CIRCLE: tuple[dict[str, object], ...] = (
    {
        "name": "Sandeep Nair",
        "relationship_label": "Son",
        "phone": "+91 90000 10031",
        "role": CareCircleRole.CONTRIBUTOR,
        "receives_alerts": True,
    },
    {
        "name": "Latha Menon",
        "relationship_label": "Neighbour",
        "phone": "+91 90000 10032",
        "role": CareCircleRole.EMERGENCY_CONTACT,
        "receives_alerts": True,
    },
)


def _care_circles(db: Session, records, actor: User) -> int:
    """A primary member for everyone, and a real circle for a few.

    Every patient gets their family user mirrored as the primary member, because
    Phase 11 migrates authorization onto this table and a patient with no row
    here would be a patient nobody could reach.
    """
    from ..services import care_circle_service

    added = 0
    for record in records:
        care_circle_service.ensure_primary(db, record.patient)
        added += 1

        if record.slot == 0:
            entries = LAKSHMI_CIRCLE
        elif record.slot % 6 == 0:
            entries = OTHER_CIRCLE
        else:
            continue

        for entry in entries:
            care_circle_service.add_member(db, record.patient, actor=actor, **entry)
            added += 1
    return added


# --------------------------------------------------------------------------
# Consent and the erasure queue (§4.14)
# --------------------------------------------------------------------------


def _consents(db: Session, records) -> int:
    """Every family has agreed to the care they are paying for.

    The optional consents are deliberately mixed: a demo where everybody agreed
    to everything shows a consent screen that never did anything. Two families
    have declined the assistant, and one has declined outside-the-app messages —
    and the notification routing has to honour that.
    """
    from ..core.ops import CONSENT_KINDS
    from ..services import consent_service

    written = 0
    for record in records:
        family = db.get(User, record.patient.family_user_id)
        if family is None:  # pragma: no cover - defensive
            continue
        for spec in CONSENT_KINDS:
            granted = True
            if spec.key == "assistant" and record.slot % 9 == 4:
                granted = False
            if spec.key == "notifications" and record.slot % 11 == 7:
                granted = False
            consent_service.record_decision(
                db,
                user=family,
                kind=spec.key,
                granted=granted,
                patient=record.patient,
                source="seed",
                commit=False,
            )
            written += 1
    return written


def _erasure_request(db: Session, records) -> int:
    """One request waiting, so an admin can carry one out live.

    Deliberately not Lakshmi's: executing it during a demo would destroy the
    dataset every other screen is built on. It belongs to a patient far enough
    down the roster that nothing else in the demo depends on them.
    """
    from ..services import privacy_service

    target = next((record for record in records if record.slot == 23), None)
    if target is None:  # pragma: no cover - the roster is 28 patients
        return 0

    family = db.get(User, target.patient.family_user_id)
    privacy_service.request_erasure(
        db,
        patient=target.patient,
        actor=family,
        reason="Moving my mother's care to a provider closer to my brother in Chennai.",
    )
    return 1


# --------------------------------------------------------------------------
# Notification preferences (§4.18)
# --------------------------------------------------------------------------


def _preferences(db: Session, records) -> int:
    """Defaults for everyone, and two families who have changed them.

    A demo where every account is on defaults shows a preferences screen that
    has never done anything. One family is on quiet hours; another has switched
    SMS off and kept WhatsApp — and the routing has to obey both without ever
    holding back a critical alert.
    """
    from ..models import DeliveryChannelName
    from ..services import notification_service

    seen: set[int] = set()
    written = 0
    for record in records:
        family = db.get(User, record.patient.family_user_id)
        if family is None or family.id in seen:
            continue
        seen.add(family.id)

        preference = notification_service.preferences_for(db, family)
        written += 1

        if record.slot == 4:
            preference.quiet_hours_enabled = True
        elif record.slot == 8:
            channels = preference.channels
            channels[DeliveryChannelName.SMS.value] = False
            preference.channels = channels
    db.flush()
    return written


def build(db: Session, records) -> dict[str, int]:
    """Layer Phase 10's trust and operations data over a populated database."""
    admins = list(db.scalars(select(User).where(User.role == UserRole.ADMIN).order_by(User.id)))
    nurse_users = list(db.scalars(select(User).where(User.role == UserRole.NURSE).order_by(User.id)))

    return {
        "medication_changes": _medication_history(db, records, admins),
        "organiser_fills": _pill_organiser(db, records, nurse_users),
        "circle_members": _care_circles(db, records, admins[0]),
        "consents": _consents(db, records),
        "erasure_requests": _erasure_request(db, records),
        "preferences": _preferences(db, records),
    }
