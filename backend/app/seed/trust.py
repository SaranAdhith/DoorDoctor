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

from sqlalchemy.orm import Session

from ..models import (
    CredentialKind,
    Nurse,
    NurseCredential,
    User,
    VerificationStatus,
    Visit,
)
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
