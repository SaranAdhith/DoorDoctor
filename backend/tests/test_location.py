"""Phase 10 — where a check-in happened, and how sure we are (§4.11).

The classification is the whole feature. `verified` has to be earned by
arithmetic against a stored distance, and `unavailable` has to be reachable,
because "we do not know where the nurse was" is a sentence this platform must be
able to say out loud.
"""

from sqlalchemy import select

from app.core.ops import GEOFENCE_ACCURACY_CEILING_M, GEOFENCE_RADIUS_M
from app.models import FollowUpTask, LocationStatus, Patient, TaskKind, Visit
from app.seed.core import LAKSHMI_HOME
from app.seed.generators import offset_coordinates
from app.services import location_service

HOME_LAT, HOME_LNG = LAKSHMI_HOME


def _near(metres: float, bearing: float = 45.0) -> dict[str, float]:
    lat, lng = offset_coordinates(HOME_LAT, HOME_LNG, metres=metres, bearing_deg=bearing)
    return {"lat": lat, "lng": lng, "accuracy_m": 12}


# --- the classifier itself -------------------------------------------------


def test_distance_is_symmetric_and_zero_at_the_same_point():
    assert location_service.distance_m(HOME_LAT, HOME_LNG, HOME_LAT, HOME_LNG) == 0
    there = location_service.distance_m(12.93, 77.62, 12.98, 77.64)
    back = location_service.distance_m(12.98, 77.64, 12.93, 77.62)
    assert abs(there - back) < 1e-6


def test_a_fix_inside_the_fence_is_verified():
    lat, lng = offset_coordinates(HOME_LAT, HOME_LNG, metres=GEOFENCE_RADIUS_M - 40, bearing_deg=10)
    verdict = location_service.classify(
        fix_lat=lat, fix_lng=lng, home_lat=HOME_LAT, home_lng=HOME_LNG, accuracy_m=10
    )
    assert verdict.status == LocationStatus.VERIFIED
    assert verdict.distance_m is not None and verdict.distance_m < GEOFENCE_RADIUS_M


def test_a_fix_outside_the_fence_is_out_of_range_and_says_how_far():
    lat, lng = offset_coordinates(HOME_LAT, HOME_LNG, metres=900, bearing_deg=200)
    verdict = location_service.classify(
        fix_lat=lat, fix_lng=lng, home_lat=HOME_LAT, home_lng=HOME_LNG, accuracy_m=10
    )
    assert verdict.status == LocationStatus.OUT_OF_RANGE
    assert "900 m" in verdict.detail or "899 m" in verdict.detail or "901 m" in verdict.detail


def test_no_fix_is_unavailable():
    verdict = location_service.classify(
        fix_lat=None, fix_lng=None, home_lat=HOME_LAT, home_lng=HOME_LNG
    )
    assert verdict.status == LocationStatus.UNAVAILABLE
    assert verdict.distance_m is None
    assert verdict.source == "none"


def test_a_patient_with_no_home_coordinates_is_unavailable_not_out_of_range():
    """The fix is real; the reference point is missing. Those are different failures."""
    verdict = location_service.classify(
        fix_lat=HOME_LAT, fix_lng=HOME_LNG, home_lat=None, home_lng=None, accuracy_m=8
    )
    assert verdict.status == LocationStatus.UNAVAILABLE
    assert "no recorded location" in verdict.detail


def test_a_fix_too_vague_to_test_the_fence_is_unavailable_even_when_it_is_close():
    """Standing on the doorstep with a +/-500 m fix is not evidence of anything.

    This is the case that would silently turn the feature into decoration: the
    coordinates *are* inside the circle, and reporting `verified` would be the
    platform lying about the one thing it exists to prove.
    """
    lat, lng = offset_coordinates(HOME_LAT, HOME_LNG, metres=20, bearing_deg=0)
    verdict = location_service.classify(
        fix_lat=lat,
        fix_lng=lng,
        home_lat=HOME_LAT,
        home_lng=HOME_LNG,
        accuracy_m=GEOFENCE_ACCURACY_CEILING_M + 1,
    )
    assert verdict.status == LocationStatus.UNAVAILABLE
    assert verdict.distance_m is not None  # measured, and still not enough


def test_a_missing_accuracy_is_treated_as_usable():
    lat, lng = offset_coordinates(HOME_LAT, HOME_LNG, metres=20, bearing_deg=0)
    verdict = location_service.classify(
        fix_lat=lat, fix_lng=lng, home_lat=HOME_LAT, home_lng=HOME_LNG, accuracy_m=None
    )
    assert verdict.status == LocationStatus.VERIFIED


# --- through the API -------------------------------------------------------


def test_checkin_at_the_door_is_verified_and_stores_the_distance(
    client, nurse_headers, scheduled_visit_id
):
    response = client.post(
        f"/api/v1/visits/{scheduled_visit_id}/checkin", json=_near(30), headers=nurse_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["location_status"] == "verified"
    assert 20 < body["location_distance_m"] < 45
    assert body["location_accuracy_m"] == 12
    assert "from the recorded home address" in body["location_detail"]


def test_an_out_of_range_checkin_still_starts_the_visit(client, nurse_headers, scheduled_visit_id):
    """The nurse must be able to work. The irregularity is recorded, not enforced."""
    response = client.post(
        f"/api/v1/visits/{scheduled_visit_id}/checkin", json=_near(1200), headers=nurse_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["location_status"] == "out_of_range"


def test_an_out_of_range_checkin_opens_one_task_for_the_admin(
    client, db, nurse_headers, scheduled_visit_id
):
    client.post(
        f"/api/v1/visits/{scheduled_visit_id}/checkin", json=_near(1200), headers=nurse_headers
    )
    tasks = db.scalars(
        select(FollowUpTask).where(
            FollowUpTask.source_type == "visit_location",
            FollowUpTask.source_id == scheduled_visit_id,
        )
    ).all()
    assert len(tasks) == 1
    assert tasks[0].kind == TaskKind.LOCATION_REVIEW


def test_a_verified_checkin_opens_no_task(client, db, nurse_headers, scheduled_visit_id):
    client.post(
        f"/api/v1/visits/{scheduled_visit_id}/checkin", json=_near(30), headers=nurse_headers
    )
    assert (
        db.scalar(
            select(FollowUpTask).where(
                FollowUpTask.source_type == "visit_location",
                FollowUpTask.source_id == scheduled_visit_id,
            )
        )
        is None
    )


def test_an_out_of_range_checkin_is_audited(client, db, nurse_headers, scheduled_visit_id):
    from app.models import AuditAction, AuditEvent

    client.post(
        f"/api/v1/visits/{scheduled_visit_id}/checkin", json=_near(1200), headers=nurse_headers
    )
    entry = db.scalar(
        select(AuditEvent).where(AuditEvent.action == AuditAction.LOCATION_OUT_OF_RANGE)
    )
    assert entry is not None
    assert entry.subject_id == scheduled_visit_id


def test_the_seeded_demo_patient_has_a_located_home(db):
    lakshmi = db.get(Patient, 1)
    assert lakshmi.home_lat is not None and lakshmi.home_lng is not None
    assert lakshmi.zone == "Koramangala"


def test_the_seed_contains_an_unavailable_checkin(db):
    """A demo where every check-in is verified teaches the badge is decoration."""
    statuses = {
        visit.location_status
        for visit in db.scalars(select(Visit).where(Visit.checkin_at.is_not(None)))
    }
    assert LocationStatus.VERIFIED in statuses
    assert LocationStatus.UNAVAILABLE in statuses


def test_nothing_in_the_codebase_still_says_demo_unverified(db):
    visits = db.scalars(select(Visit)).all()
    assert all(visit.location_source in ("browser", "none") for visit in visits)
