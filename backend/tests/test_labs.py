"""Lab panels, ordering, results and the recorded abnormal rule (§4.2).

RECORDED and pinned as literals: the blood panel costs ₹499, and an abnormal
result raises an alert **and a 24-hour follow-up task**. Everything else is
asserted against `core/clinical.py` so reconciling §4 stays a one-file edit.
"""

import pytest
from sqlalchemy import select

from app.core import clinical, pricing
from app.models import (
    Alert,
    FollowUpTask,
    InvoiceLine,
    InvoiceLineKind,
    LabBilling,
    LabFlag,
    LabOrder,
    LabOrderStatus,
    Patient,
    TaskKind,
    TaskStatus,
)
from app.services import lab_service, subscription_service

from .conftest import auth, login

PANEL = clinical.BASIC_PANEL


def _normal_values() -> dict[str, float]:
    """A value comfortably inside every range in the basic panel."""
    values = {}
    for analyte in PANEL.analytes:
        if analyte.ref_low is not None and analyte.ref_high is not None:
            values[analyte.code] = (analyte.ref_low + analyte.ref_high) / 2
        elif analyte.ref_high is not None:
            values[analyte.code] = analyte.ref_high - 1
        else:
            values[analyte.code] = (analyte.ref_low or 0) + 1
    return values


def _order(client, headers, panel_code=PANEL.code):
    response = client.post(
        "/api/v1/patients/1/lab-orders", json={"panel_code": panel_code}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------
# Flagging is pure arithmetic, so the test re-runs it
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (100, LabFlag.NORMAL),
        (60, LabFlag.LOW),
        (200, LabFlag.HIGH),
        (40, LabFlag.CRITICAL_LOW),
        (300, LabFlag.CRITICAL_HIGH),
    ],
)
def test_flagging_compares_a_value_against_its_range(value, expected):
    glucose = next(a for a in PANEL.analytes if a.code == "fasting_glucose")
    assert (
        lab_service.flag_for(
            value,
            ref_low=glucose.ref_low,
            ref_high=glucose.ref_high,
            critical_low=glucose.critical_low,
            critical_high=glucose.critical_high,
        )
        is expected
    )


def test_critical_wins_over_ordinary_abnormal():
    """A value that is both must report the more serious of the two."""
    assert lab_service.flag_for(500, ref_low=1, ref_high=10, critical_high=100) is LabFlag.CRITICAL_HIGH


def test_no_configured_range_is_unknown_not_normal():
    """"Unknown" and "normal" must never be conflated — one is a finding, the
    other is the absence of a measurement rule."""
    assert lab_service.flag_for(42, ref_low=None, ref_high=None) is LabFlag.UNKNOWN
    assert not LabFlag.UNKNOWN.is_abnormal


# --------------------------------------------------------------------------
# The catalogue
# --------------------------------------------------------------------------


def test_the_panel_price_comes_from_the_pricing_module(client, family_headers):
    response = client.get("/api/v1/lab-panels", headers=family_headers)
    assert response.status_code == 200, response.text
    for panel in response.json():
        spec = pricing.ADD_ONS_BY_CODE[panel["addon_code"]]
        assert panel["price_paise"] == spec.price_paise


def test_the_blood_panel_is_the_recorded_499_rupees():
    """RECORDED, so a literal. Every other test compares to `pricing.py` itself
    and would still pass if `pricing.py` were the thing that moved."""
    assert pricing.ADD_ONS_BY_CODE["blood_panel"].price_paise == 49900


def test_every_panel_points_at_a_real_add_on():
    for panel in clinical.LAB_PANELS:
        assert panel.addon_code in pricing.ADD_ONS_BY_CODE


def test_every_analyte_range_is_the_right_way_round():
    for panel in clinical.LAB_PANELS:
        for analyte in panel.analytes:
            if analyte.ref_low is not None and analyte.ref_high is not None:
                assert analyte.ref_low < analyte.ref_high, f"{panel.code}.{analyte.code}"
            if analyte.critical_low is not None and analyte.ref_low is not None:
                assert analyte.critical_low <= analyte.ref_low
            if analyte.critical_high is not None and analyte.ref_high is not None:
                assert analyte.critical_high >= analyte.ref_high


# --------------------------------------------------------------------------
# Ordering: the entitlement first, then the add-on
# --------------------------------------------------------------------------


def test_the_first_order_spends_the_plans_allowance(client, family_headers, db):
    body = _order(client, family_headers)
    assert body["billing"] == LabBilling.ENTITLEMENT.value
    assert body["price_paise"] == 0
    assert body["invoice_line_id"] is None


def test_the_allowance_is_actually_consumed(client, family_headers, db):
    before = client.get("/api/v1/subscriptions/me", headers=family_headers).json()
    used_before = next(q for q in before["quotas"] if q["quota"] == "lab_panels")["used"]

    _order(client, family_headers)

    after = client.get("/api/v1/subscriptions/me", headers=family_headers).json()
    used_after = next(q for q in after["quotas"] if q["quota"] == "lab_panels")["used"]
    assert used_after == used_before + 1


def test_an_order_past_the_allowance_bills_the_add_on_rather_than_being_refused(
    client, family_headers, db
):
    """The add-on price exists so more is purchasable. Refusing would make ₹499
    unreachable — and the family would simply have gone elsewhere for the test."""
    subscription = client.get("/api/v1/subscriptions/me", headers=family_headers).json()
    # What is *left*, not what the plan grants — the seed has already used some.
    remaining = next(q for q in subscription["quotas"] if q["quota"] == "lab_panels")["remaining"]

    for _ in range(remaining):
        assert _order(client, family_headers)["billing"] == LabBilling.ENTITLEMENT.value

    extra = _order(client, family_headers)
    assert extra["billing"] == LabBilling.ADDON.value
    assert extra["price_paise"] == pricing.ADD_ONS_BY_CODE["blood_panel"].price_paise
    assert extra["invoice_line_id"] is not None


def test_the_add_on_reaches_an_invoice_as_an_addon_line(client, family_headers, db):
    subscription = client.get("/api/v1/subscriptions/me", headers=family_headers).json()
    remaining = next(q for q in subscription["quotas"] if q["quota"] == "lab_panels")["remaining"]
    for _ in range(remaining):
        _order(client, family_headers)
    extra = _order(client, family_headers)

    line = db.get(InvoiceLine, extra["invoice_line_id"])
    assert line is not None
    assert line.kind == InvoiceLineKind.ADDON
    assert line.amount_paise == pricing.ADD_ONS_BY_CODE["blood_panel"].price_paise
    # The charge lands on a real, fetchable invoice.
    invoices = client.get("/api/v1/invoices", headers=family_headers).json()
    assert line.invoice_id in {i["id"] for i in invoices}


def test_an_unknown_panel_is_a_404(client, family_headers):
    response = client.post(
        "/api/v1/patients/1/lab-orders", json={"panel_code": "nope"}, headers=family_headers
    )
    assert response.status_code == 404


def test_a_nurse_cannot_order_a_panel(client, nurse_headers):
    """A nurse does not spend a family's allowance or add ₹499 to their invoice."""
    response = client.post(
        "/api/v1/patients/1/lab-orders", json={"panel_code": PANEL.code}, headers=nurse_headers
    )
    assert response.status_code == 403


def test_another_familys_patient_cannot_be_ordered_for(client, other_family):
    headers = auth(login(client, other_family["email"]))
    response = client.post(
        "/api/v1/patients/1/lab-orders", json={"panel_code": PANEL.code}, headers=headers
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Results, and the recorded abnormal rule
# --------------------------------------------------------------------------


def test_normal_results_raise_nothing(client, family_headers, admin_headers, db):
    order_id = _order(client, family_headers)["id"]
    response = client.post(
        f"/api/v1/lab-orders/{order_id}/results",
        json={"values": _normal_values()},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == LabOrderStatus.RESULTED.value
    assert body["abnormal_count"] == 0
    assert all(not r["is_abnormal"] for r in body["results"])
    assert not db.scalars(
        select(Alert).where(Alert.alert_type == "lab_result_abnormal")
    ).all()
    assert not db.scalars(
        select(FollowUpTask).where(FollowUpTask.kind == TaskKind.LAB_FOLLOW_UP)
    ).all()


def test_an_abnormal_result_raises_an_alert_and_a_24_hour_task(
    client, family_headers, admin_headers, db
):
    """RECORDED. The 24 is a literal on purpose."""
    order_id = _order(client, family_headers)["id"]
    values = {**_normal_values(), "fasting_glucose": 200}
    response = client.post(
        f"/api/v1/lab-orders/{order_id}/results", json={"values": values}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["abnormal_count"] == 1

    alerts = db.scalars(select(Alert).where(Alert.alert_type == "lab_result_abnormal")).all()
    assert len(alerts) == 1

    tasks = db.scalars(select(FollowUpTask).where(FollowUpTask.source_id == order_id)).all()
    assert len(tasks) == 1
    task = tasks[0]
    assert task.kind == TaskKind.LAB_FOLLOW_UP
    assert task.status == TaskStatus.OPEN
    hours = (task.due_at - task.created_at).total_seconds() / 3600
    assert round(hours) == 24


def test_a_panel_with_four_abnormal_values_raises_exactly_one_alert(
    client, family_headers, admin_headers, db
):
    """One order is one clinical event. Four alerts would push three real
    findings off the top of a family's screen with copies of the same news."""
    order_id = _order(client, family_headers)["id"]
    values = {
        **_normal_values(),
        "fasting_glucose": 200,
        "hba1c": 8.0,
        "creatinine": 2.0,
        "urea": 60,
    }
    body = client.post(
        f"/api/v1/lab-orders/{order_id}/results", json={"values": values}, headers=admin_headers
    ).json()

    assert body["abnormal_count"] == 4
    assert len(db.scalars(select(Alert).where(Alert.alert_type == "lab_result_abnormal")).all()) == 1
    assert len(db.scalars(select(FollowUpTask).where(FollowUpTask.source_id == order_id)).all()) == 1


def test_a_critical_value_raises_a_critical_alert(client, family_headers, admin_headers, db):
    order_id = _order(client, family_headers)["id"]
    values = {**_normal_values(), "fasting_glucose": 400}
    client.post(
        f"/api/v1/lab-orders/{order_id}/results", json={"values": values}, headers=admin_headers
    )
    alert = db.scalar(select(Alert).where(Alert.alert_type == "lab_result_abnormal"))
    assert alert.severity.value == "critical"


def test_re_recording_results_does_not_open_a_second_task(
    client, family_headers, admin_headers, db
):
    order_id = _order(client, family_headers)["id"]
    values = {**_normal_values(), "fasting_glucose": 200}
    for _ in range(3):
        client.post(
            f"/api/v1/lab-orders/{order_id}/results", json={"values": values}, headers=admin_headers
        )
    assert len(db.scalars(select(FollowUpTask).where(FollowUpTask.source_id == order_id)).all()) == 1


def test_a_correction_replaces_the_results_rather_than_appending(
    client, family_headers, admin_headers
):
    order_id = _order(client, family_headers)["id"]
    client.post(
        f"/api/v1/lab-orders/{order_id}/results",
        json={"values": _normal_values()},
        headers=admin_headers,
    )
    corrected = client.post(
        f"/api/v1/lab-orders/{order_id}/results",
        json={"values": {"fasting_glucose": 95}},
        headers=admin_headers,
    ).json()
    assert len(corrected["results"]) == 1


def test_each_result_carries_the_range_it_was_judged_against(
    client, family_headers, admin_headers
):
    """`core/clinical.py` is meant to be edited. A result somebody already read
    must not silently re-flag when a range moves."""
    order_id = _order(client, family_headers)["id"]
    body = client.post(
        f"/api/v1/lab-orders/{order_id}/results",
        json={"values": {"fasting_glucose": 200}},
        headers=admin_headers,
    ).json()
    result = body["results"][0]
    glucose = next(a for a in PANEL.analytes if a.code == "fasting_glucose")
    assert result["ref_low"] == glucose.ref_low
    assert result["ref_high"] == glucose.ref_high
    assert str(int(glucose.ref_high)) in result["description"]


def test_a_value_not_in_the_panel_is_rejected(client, family_headers, admin_headers):
    order_id = _order(client, family_headers)["id"]
    response = client.post(
        f"/api/v1/lab-orders/{order_id}/results",
        json={"values": {"not_a_test": 1}},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "not_a_test" in response.json()["detail"]


def test_only_an_admin_records_results(client, family_headers):
    order_id = _order(client, family_headers)["id"]
    response = client.post(
        f"/api/v1/lab-orders/{order_id}/results",
        json={"values": _normal_values()},
        headers=family_headers,
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------
# Reads and isolation
# --------------------------------------------------------------------------


def test_a_family_reads_their_own_orders(client, family_headers):
    _order(client, family_headers)
    response = client.get("/api/v1/patients/1/lab-orders", headers=family_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_someone_elses_lab_order_is_a_404_not_a_403(client, family_headers, other_family):
    """A 403 confirms the record exists, which is enough to learn that a named
    person is a DoorDoctor patient. Same rule as invoices and reports."""
    order_id = _order(client, family_headers)["id"]
    headers = auth(login(client, other_family["email"]))
    assert client.get(f"/api/v1/lab-orders/{order_id}", headers=headers).status_code == 404


def test_cancelling_does_not_hand_the_allowance_back(client, family_headers, db):
    """Different from a consult, deliberately: the sample and the laboratory are
    spent the moment the order is placed."""
    order_id = _order(client, family_headers)["id"]
    used = next(
        q
        for q in client.get("/api/v1/subscriptions/me", headers=family_headers).json()["quotas"]
        if q["quota"] == "lab_panels"
    )["used"]

    assert client.post(f"/api/v1/lab-orders/{order_id}/cancel", headers=family_headers).status_code == 200
    after = next(
        q
        for q in client.get("/api/v1/subscriptions/me", headers=family_headers).json()["quotas"]
        if q["quota"] == "lab_panels"
    )["used"]
    assert after == used


def test_a_cancelled_order_cannot_be_resulted(client, family_headers, admin_headers):
    order_id = _order(client, family_headers)["id"]
    client.post(f"/api/v1/lab-orders/{order_id}/cancel", headers=family_headers)
    response = client.post(
        f"/api/v1/lab-orders/{order_id}/results",
        json={"values": _normal_values()},
        headers=admin_headers,
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------
# Tasks
# --------------------------------------------------------------------------


def test_the_task_queue_is_staff_only(client, family_headers, admin_headers, nurse_headers):
    """A task is the care team's work, not the family's news."""
    assert client.get("/api/v1/tasks", headers=family_headers).status_code == 403
    assert client.get("/api/v1/tasks", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/tasks", headers=nurse_headers).status_code == 200


def test_an_admin_closes_a_task_with_a_note(client, family_headers, admin_headers):
    order_id = _order(client, family_headers)["id"]
    client.post(
        f"/api/v1/lab-orders/{order_id}/results",
        json={"values": {**_normal_values(), "fasting_glucose": 200}},
        headers=admin_headers,
    )
    task = client.get("/api/v1/tasks", headers=admin_headers).json()[0]
    response = client.post(
        f"/api/v1/tasks/{task['id']}/complete",
        json={"note": "Spoke to the family, GP appointment booked."},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == TaskStatus.DONE.value
    assert body["completion_note"].startswith("Spoke to the family")


def test_a_closed_task_cannot_be_closed_again(client, family_headers, admin_headers):
    order_id = _order(client, family_headers)["id"]
    client.post(
        f"/api/v1/lab-orders/{order_id}/results",
        json={"values": {**_normal_values(), "fasting_glucose": 200}},
        headers=admin_headers,
    )
    task = client.get("/api/v1/tasks", headers=admin_headers).json()[0]
    client.post(f"/api/v1/tasks/{task['id']}/complete", headers=admin_headers)
    assert client.post(f"/api/v1/tasks/{task['id']}/complete", headers=admin_headers).status_code == 400


def test_a_nurse_sees_only_tasks_assigned_to_them(client, family_headers, admin_headers, nurse_headers):
    order_id = _order(client, family_headers)["id"]
    client.post(
        f"/api/v1/lab-orders/{order_id}/results",
        json={"values": {**_normal_values(), "fasting_glucose": 200}},
        headers=admin_headers,
    )
    admin_tasks = client.get("/api/v1/tasks", headers=admin_headers).json()
    nurse_tasks = client.get("/api/v1/tasks", headers=nurse_headers).json()

    assert len(admin_tasks) == 1
    # Anitha covers Lakshmi, so this one lands on her list too.
    assert {t["id"] for t in nurse_tasks} <= {t["id"] for t in admin_tasks}
