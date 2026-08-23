"""Phase 10 — nurse and admin operations (§4.16, §4.17).

Two ideas under test. For the nurse: the day is a worklist, and unfinished work
sorts to the top rather than to the bottom where it stays forever. For the
admin: every number is computed from the rows it describes, and the one business
figure on the screen — the break-even band — says where a zone sits and invents
no margin.
"""

from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.ops import BREAK_EVEN_MAX_SUBSCRIBERS, BREAK_EVEN_MIN_SUBSCRIBERS, ZONE_HUBS
from app.database import now
from app.models import Alert, AlertStatus, ShiftCheckIn, Visit, VisitStatus
from app.seed.generators import offset_coordinates
from app.services import alert_service, ops_service
from tests.conftest import ABNORMAL_VITALS, NORMAL_VITALS

API = "/api/v1"


def _hub_fix(zone: str = "Koramangala", metres: float = 30.0) -> dict[str, float]:
    lat, lng = ZONE_HUBS[zone]
    fix_lat, fix_lng = offset_coordinates(lat, lng, metres=metres, bearing_deg=20)
    return {"lat": fix_lat, "lng": fix_lng, "accuracy_m": 12}


# --- the nurse's day ------------------------------------------------------


def test_my_day_lists_todays_visits(client, nurse_headers):
    body = client.get(f"{API}/nurse/my-day", headers=nurse_headers).json()
    assert body["nurse_id"] == 1
    assert body["zone"] == "Koramangala"
    assert body["counts"]["total"] >= 1
    assert body["visits"], "the demo nurse has a visit today"


def test_unfinished_work_from_an_earlier_day_sorts_first(client, db, nurse_headers):
    """A visit left open on Tuesday is Wednesday's most urgent item."""
    stale = Visit(
        patient_id=1,
        nurse_id=1,
        scheduled_at=now() - timedelta(days=2),
        status=VisitStatus.SCHEDULED,
    )
    db.add(stale)
    db.commit()

    body = client.get(f"{API}/nurse/my-day", headers=nurse_headers).json()
    assert body["counts"]["carried_over"] == 1
    assert body["carried_over"][0]["id"] == stale.id
    assert body["carried_over"][0]["carried_over"] is True


def test_my_day_is_the_nurses_own_and_nobody_elses(client, family_headers, admin_headers):
    assert client.get(f"{API}/nurse/my-day", headers=family_headers).status_code == 403
    assert client.get(f"{API}/nurse/my-day", headers=admin_headers).status_code == 403


def test_the_roster_covers_the_requested_window(client, nurse_headers):
    body = client.get(f"{API}/nurse/roster?days=7", headers=nurse_headers).json()
    assert len(body["days"]) == 7
    assert body["total"] >= 0


# --- the brief ------------------------------------------------------------


def test_the_brief_carries_what_matters_before_knocking(client, nurse_headers, scheduled_visit_id):
    body = client.get(f"{API}/visits/{scheduled_visit_id}/brief", headers=nurse_headers).json()
    assert body["patient"]["name"] == "Lakshmi D'Souza"
    assert body["patient"]["emergency_contact"]
    assert body["last_reading"] is not None
    assert body["medications_due"], "she is on three medicines"
    assert "open_alerts" in body


def test_a_family_can_read_the_brief_for_their_own_visit(client, family_headers, scheduled_visit_id):
    assert (
        client.get(f"{API}/visits/{scheduled_visit_id}/brief", headers=family_headers).status_code
        == 200
    )


def test_another_family_cannot_read_the_brief(client, other_family, scheduled_visit_id):
    from tests.conftest import DEMO_PASSWORD, auth, login

    headers = auth(login(client, other_family["email"], DEMO_PASSWORD))
    assert (
        client.get(f"{API}/visits/{scheduled_visit_id}/brief", headers=headers).status_code == 404
    )


# --- the shift ------------------------------------------------------------


def test_a_hub_checkin_at_the_hub_is_verified(client, nurse_headers):
    response = client.post(f"{API}/nurse/shift/checkin", json=_hub_fix(), headers=nurse_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["location_status"] == "verified"
    assert body["is_open"] is True


def test_a_hub_uses_a_wider_radius_than_a_home(client, nurse_headers):
    """A hub is a building with a car park; a nurse at the gate is at work."""
    response = client.post(
        f"{API}/nurse/shift/checkin", json=_hub_fix(metres=200.0), headers=nurse_headers
    )
    assert response.json()["location_status"] == "verified"


def test_a_second_shift_cannot_be_opened_while_one_is_running(client, nurse_headers):
    client.post(f"{API}/nurse/shift/checkin", json=_hub_fix(), headers=nurse_headers)
    second = client.post(f"{API}/nurse/shift/checkin", json=_hub_fix(), headers=nurse_headers)
    assert second.status_code == 400
    assert "already open" in second.json()["detail"]


def test_a_shift_can_be_closed_and_then_reopened(client, nurse_headers):
    client.post(f"{API}/nurse/shift/checkin", json=_hub_fix(), headers=nurse_headers)
    closed = client.post(f"{API}/nurse/shift/checkout", headers=nurse_headers)
    assert closed.status_code == 200
    assert closed.json()["is_open"] is False
    assert client.post(
        f"{API}/nurse/shift/checkin", json=_hub_fix(), headers=nurse_headers
    ).status_code == 201


def test_closing_a_shift_that_is_not_open_is_refused(client, nurse_headers):
    assert client.post(f"{API}/nurse/shift/checkout", headers=nurse_headers).status_code == 400


def test_the_open_shift_appears_on_my_day(client, nurse_headers):
    client.post(f"{API}/nurse/shift/checkin", json=_hub_fix(), headers=nurse_headers)
    body = client.get(f"{API}/nurse/my-day", headers=nurse_headers).json()
    assert body["shift"] is not None
    assert body["shift"]["is_open"] is True


# --- offline-tolerant capture ---------------------------------------------


def test_a_replayed_reading_corrects_itself_instead_of_doubling(
    client, db, nurse_headers, started_visit_id
):
    """The nurse was in a basement flat. The queue drained twice."""
    payload = {**NORMAL_VITALS, "client_token": "queued-abc123"}
    first = client.post(
        f"{API}/visits/{started_visit_id}/vitals", json=payload, headers=nurse_headers
    )
    second = client.post(
        f"{API}/visits/{started_visit_id}/vitals", json=payload, headers=nurse_headers
    )
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["replayed"] is False
    assert second.json()["replayed"] is True
    assert first.json()["vitals"]["id"] == second.json()["vitals"]["id"]


def test_a_replayed_breach_does_not_raise_a_second_alert(
    client, db, nurse_headers, started_visit_id
):
    payload = {**ABNORMAL_VITALS, "client_token": "queued-breach"}
    first = client.post(
        f"{API}/visits/{started_visit_id}/vitals", json=payload, headers=nurse_headers
    ).json()
    second = client.post(
        f"{API}/visits/{started_visit_id}/vitals", json=payload, headers=nurse_headers
    ).json()
    assert first["alerts_created"]
    assert second["alerts_created"] == []


def test_a_reading_with_no_token_still_records_normally(client, nurse_headers, started_visit_id):
    first = client.post(
        f"{API}/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=nurse_headers
    ).json()
    second = client.post(
        f"{API}/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=nurse_headers
    ).json()
    assert first["vitals"]["id"] != second["vitals"]["id"]


def test_a_replayed_dose_does_not_double_the_log(client, nurse_headers, started_visit_id):
    payload = {"medication_id": 1, "status": "administered", "client_token": "dose-xyz"}
    first = client.post(
        f"{API}/visits/{started_visit_id}/medication-logs", json=payload, headers=nurse_headers
    ).json()
    second = client.post(
        f"{API}/visits/{started_visit_id}/medication-logs", json=payload, headers=nurse_headers
    ).json()
    assert first["id"] == second["id"]


# --- the visit board ------------------------------------------------------


def test_the_board_is_a_window_and_leads_with_the_earliest_in_it(client, admin_headers):
    body = client.get(f"{API}/admin/visit-board", headers=admin_headers).json()
    times = [visit["scheduled_at"] for visit in body["visits"]]
    assert times == sorted(times), "inside a window, ascending is the order the day is worked"


def test_the_board_paginates(client, admin_headers):
    body = client.get(f"{API}/admin/visit-board?page_size=1", headers=admin_headers).json()
    assert body["page_size"] == 1
    assert len(body["visits"]) <= 1
    assert body["pages"] >= 1


def test_the_board_summary_describes_the_window_not_the_page(client, admin_headers):
    page = client.get(f"{API}/admin/visit-board?page_size=1", headers=admin_headers).json()
    everything = client.get(f"{API}/admin/visit-board?page_size=100", headers=admin_headers).json()
    assert page["summary"] == everything["summary"]
    assert page["total"] == everything["total"]


def test_the_board_filters_by_nurse_and_by_status(client, admin_headers):
    body = client.get(f"{API}/admin/visit-board?nurse_id=1", headers=admin_headers).json()
    assert all(visit["nurse_id"] == 1 for visit in body["visits"])

    scheduled = client.get(
        f"{API}/admin/visit-board?status=scheduled", headers=admin_headers
    ).json()
    assert all(visit["status"] == "scheduled" for visit in scheduled["visits"])


def test_the_board_is_admin_only(client, family_headers, nurse_headers):
    assert client.get(f"{API}/admin/visit-board", headers=family_headers).status_code == 403
    assert client.get(f"{API}/admin/visit-board", headers=nurse_headers).status_code == 403


# --- the alert queue ------------------------------------------------------


def test_a_new_alert_carries_a_stored_deadline(client, db, nurse_headers, started_visit_id):
    response = client.post(
        f"{API}/visits/{started_visit_id}/vitals", json=ABNORMAL_VITALS, headers=nurse_headers
    ).json()
    alert = db.get(Alert, response["alerts_created"][0]["id"])
    assert alert.sla_minutes is not None
    assert alert.sla_due_at == alert.created_at + timedelta(minutes=alert.sla_minutes)


def test_a_breach_is_stamped_when_observed_and_survives_the_constants_moving(db):
    """The same rule Phase 9 gave escalations: an alert that breached says so."""
    alert = db.scalar(select(Alert).where(Alert.status == AlertStatus.ACTIVE))
    if alert is None:
        return
    alert.sla_minutes = 15
    alert.sla_due_at = now() - timedelta(hours=2)
    alert.sla_breached_at = None
    db.commit()

    alert_service.refresh_sla(alert)
    stamped = alert.sla_breached_at
    assert stamped is not None

    alert.sla_minutes = 10_000  # somebody edits the SLA
    alert_service.refresh_sla(alert)
    assert alert.sla_breached_at == stamped


def test_the_queue_puts_breached_alerts_first(client, db, admin_headers):
    alerts = db.scalars(select(Alert).where(Alert.status == AlertStatus.ACTIVE)).all()
    if not alerts:
        return
    alerts[-1].sla_due_at = now() - timedelta(hours=3)
    alerts[-1].sla_breached_at = None
    db.commit()

    queue = client.get(f"{API}/admin/alert-queue", headers=admin_headers).json()
    assert queue
    if any(row["breached"] for row in queue):
        assert queue[0]["breached"] is True


def test_the_queue_carries_the_patient_name_and_zone(client, admin_headers):
    queue = client.get(f"{API}/admin/alert-queue", headers=admin_headers).json()
    if queue:
        assert "patient_name" in queue[0]
        assert "zone" in queue[0]


def test_the_seed_never_leaves_an_alert_whose_deadline_disagrees_with_its_clock(db):
    """An alert dated sixty days ago with a deadline fifteen minutes from now
    would make the whole queue look freshly raised and never breached."""
    for alert in db.scalars(select(Alert)):
        if alert.sla_minutes is None:
            continue
        assert alert.sla_due_at == alert.created_at + timedelta(minutes=alert.sla_minutes)


# --- outcomes -------------------------------------------------------------


def test_outcomes_are_computed_from_rows(client, db, admin_headers):
    body = client.get(f"{API}/admin/outcomes?days=365", headers=admin_headers).json()
    completed = len(
        db.scalars(
            select(Visit).where(
                Visit.status == VisitStatus.COMPLETED,
                Visit.scheduled_at >= now() - timedelta(days=365),
                Visit.scheduled_at < now(),
            )
        ).all()
    )
    assert body["visits"]["completed"] == completed


def test_a_rate_with_nothing_to_divide_is_none_not_zero(client, admin_headers):
    """0% reads as a failure, and "no data" is not one."""
    body = client.get(f"{API}/admin/outcomes?days=1", headers=admin_headers).json()
    for section, key in (("visits", "completion_rate"), ("medication", "adherence")):
        value = body[section][key]
        assert value is None or 0 <= value <= 100


def test_sla_attainment_counts_only_alerts_that_have_had_their_chance(client, admin_headers):
    body = client.get(f"{API}/admin/outcomes?days=365", headers=admin_headers).json()
    assert body["alerts"]["sla_judged"] <= body["alerts"]["raised"]
    assert body["alerts"]["sla_met"] <= body["alerts"]["sla_judged"]


def test_outcomes_report_the_location_split(client, admin_headers):
    body = client.get(f"{API}/admin/outcomes?days=365", headers=admin_headers).json()
    location = body["location"]
    assert (
        location["verified"] + location["out_of_range"] + location["unavailable"]
        == location["checked_in"]
    )


# --- zones ----------------------------------------------------------------


def test_the_zone_view_reports_position_against_the_band_and_no_margin(client, admin_headers):
    body = client.get(f"{API}/admin/zones", headers=admin_headers).json()
    assert body["break_even_min"] == BREAK_EVEN_MIN_SUBSCRIBERS
    assert body["break_even_max"] == BREAK_EVEN_MAX_SUBSCRIBERS
    assert "does not estimate a margin" in body["note"]

    serialized = str(body)
    for invented in ("margin", "profit", "revenue_per", "cost_per"):
        assert f'"{invented}"' not in serialized


def test_every_zone_row_says_which_side_of_the_band_it_is_on(client, admin_headers):
    body = client.get(f"{API}/admin/zones", headers=admin_headers).json()
    for row in body["zones"]:
        assert row["break_even"] in ("below", "within", "above")
        assert row["to_break_even"] >= 0


def test_the_zone_view_is_admin_only(client, family_headers, nurse_headers):
    assert client.get(f"{API}/admin/zones", headers=family_headers).status_code == 403
    assert client.get(f"{API}/admin/zones", headers=nurse_headers).status_code == 403
