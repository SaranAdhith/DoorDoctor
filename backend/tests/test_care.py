"""Care managers, caseloads and interactions (§4.4).

RECORDED and pinned as literals: **1:20 shared, 1:10 dedicated**. Which tier
gets which is `ASSUMED` (Phase 4) and is asserted against `pricing.py`.
"""

import pytest
from sqlalchemy import select

from app.core import pricing
from app.core.exceptions import ConflictError
from app.models import (
    CareChannel,
    CareManagerKind,
    Patient,
    User,
    UserRole,
)
from app.services import care_service

from .conftest import DEMO_PASSWORD, auth, login


@pytest.fixture
def admin_user(db) -> User:
    return db.scalar(select(User).where(User.role == UserRole.ADMIN))


@pytest.fixture
def manager(db, admin_user):
    m = care_service.create_manager(
        db, user=admin_user, kind=CareManagerKind.SHARED, languages="English, Kannada"
    )
    db.commit()
    return m


def _extra_patient(db, name: str) -> Patient:
    patient = Patient(
        name=name, age=70, gender="Female", address="Jayanagar, Bengaluru", family_user_id=1
    )
    db.add(patient)
    db.flush()
    return patient


# --------------------------------------------------------------------------
# The recorded ratios
# --------------------------------------------------------------------------


def test_the_recorded_ratios_are_one_to_twenty_and_one_to_ten():
    """RECORDED, so literals."""
    assert pricing.RATIO_SHARED == 20
    assert pricing.RATIO_DEDICATED == 10


def test_capacity_defaults_to_the_recorded_ratio(db, admin_user):
    manager = care_service.create_manager(db, user=admin_user, kind=CareManagerKind.SHARED)
    assert manager.capacity == pricing.RATIO_SHARED


def test_a_dedicated_manager_carries_the_smaller_caseload(db, admin_user):
    manager = care_service.create_manager(db, user=admin_user, kind=CareManagerKind.DEDICATED)
    assert manager.capacity == pricing.RATIO_DEDICATED
    assert manager.capacity < pricing.RATIO_SHARED


def test_capacity_may_be_reduced_for_one_manager_without_changing_the_plan(db, admin_user):
    """One manager on a lighter load must not change what the plan promises
    everybody else, which is why capacity is stored rather than derived."""
    manager = care_service.create_manager(
        db, user=admin_user, kind=CareManagerKind.SHARED, capacity=5
    )
    assert manager.capacity == 5
    assert pricing.RATIO_SHARED == 20


def test_every_plan_grants_a_care_manager_kind_the_model_understands():
    """Phase 4's entitlement strings and Phase 9's enum must not drift apart."""
    for plan in pricing.PLANS:
        value = plan.entitlements[pricing.CARE_MANAGER]
        assert CareManagerKind(str(value))


# --------------------------------------------------------------------------
# A profile on an admin, not a fourth role
# --------------------------------------------------------------------------


def test_a_care_manager_is_an_admin_account(db):
    """The whole reason this is a profile rather than a role is that a care
    manager *is* an admin. Letting a nurse hold one creates the fourth role the
    design avoids."""
    nurse = db.scalar(select(User).where(User.role == UserRole.NURSE))
    with pytest.raises(Exception) as excinfo:
        care_service.create_manager(db, user=nurse, kind=CareManagerKind.SHARED)
    assert "admin" in str(excinfo.value).lower()


def test_the_role_enum_still_has_exactly_three_roles():
    assert {r.value for r in UserRole} == {"family", "nurse", "admin"}


def test_one_admin_cannot_hold_two_manager_profiles(db, admin_user, manager):
    with pytest.raises(ConflictError):
        care_service.create_manager(db, user=admin_user, kind=CareManagerKind.DEDICATED)


# --------------------------------------------------------------------------
# Assignment and capacity
# --------------------------------------------------------------------------


def test_a_patient_is_assigned_and_the_caseload_counts_them(db, manager):
    patient = db.get(Patient, 1)
    care_service.assign(db, patient=patient, manager=manager)
    assert care_service.caseload(db, manager.id) == 1


def test_assigning_past_capacity_is_refused_with_the_count(db, admin_user):
    manager = care_service.create_manager(
        db, user=admin_user, kind=CareManagerKind.SHARED, capacity=2
    )
    for index in range(2):
        care_service.assign(db, patient=_extra_patient(db, f"Patient {index}"), manager=manager)

    with pytest.raises(ConflictError) as excinfo:
        care_service.assign(db, patient=_extra_patient(db, "One too many"), manager=manager)
    assert "2 of 2" in str(excinfo.value)


def test_reassigning_ends_the_previous_assignment_rather_than_adding_one(db, admin_user):
    first = care_service.create_manager(db, user=admin_user, kind=CareManagerKind.SHARED)
    other_admin = User(
        name="Second Admin",
        email="admin2@doordoctor.in",
        phone="+91 90000 00021",
        password_hash="x",
        role=UserRole.ADMIN,
    )
    db.add(other_admin)
    db.flush()
    second = care_service.create_manager(db, user=other_admin, kind=CareManagerKind.SHARED)

    patient = db.get(Patient, 1)
    care_service.assign(db, patient=patient, manager=first)
    care_service.assign(db, patient=patient, manager=second)

    assert care_service.caseload(db, first.id) == 0
    assert care_service.caseload(db, second.id) == 1
    current = care_service.current_assignment(db, patient.id)
    assert current.care_manager_id == second.id


def test_a_handover_is_kept_as_history_not_deleted(db, admin_user, manager):
    from app.models import CareAssignment

    patient = db.get(Patient, 1)
    assignment = care_service.assign(db, patient=patient, manager=manager)
    care_service.end(db, assignment, reason="Manager left")

    rows = db.scalars(
        select(CareAssignment).where(CareAssignment.patient_id == patient.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].ended_at is not None
    assert rows[0].ended_reason == "Manager left"
    assert care_service.current_assignment(db, patient.id) is None


def test_reassigning_to_the_same_manager_is_a_no_op(db, manager):
    patient = db.get(Patient, 1)
    first = care_service.assign(db, patient=patient, manager=manager)
    second = care_service.assign(db, patient=patient, manager=manager)
    assert first.id == second.id
    assert care_service.caseload(db, manager.id) == 1


# --------------------------------------------------------------------------
# The entitlement decides the kind — never a plan code
# --------------------------------------------------------------------------


def test_the_entitled_kind_is_read_from_the_plan_as_data(db):
    patient = db.get(Patient, 1)
    kind = care_service.entitled_kind(db, patient)
    assert kind is not None
    assert kind.value == pricing.CARE_PLUS.entitlements[pricing.CARE_MANAGER]


def test_changing_the_entitlement_changes_the_kind_without_touching_the_name(db):
    patient = db.get(Patient, 1)
    subscription = care_service._subscription_for(db, patient)
    name_before = subscription.plan.name

    entitlements = dict(subscription.plan.entitlements)
    entitlements[pricing.CARE_MANAGER] = CareManagerKind.DEDICATED.value
    subscription.plan.entitlements = entitlements
    db.flush()

    assert care_service.entitled_kind(db, patient) is CareManagerKind.DEDICATED
    assert subscription.plan.name == name_before


def test_a_patient_with_no_plan_is_entitled_to_none(db, other_family):
    patient = db.get(Patient, other_family["patient_id"])
    assert care_service.entitled_kind(db, patient) is None


def test_auto_assign_picks_the_least_loaded_manager_of_the_right_kind(db, admin_user):
    busy = care_service.create_manager(db, user=admin_user, kind=CareManagerKind.SHARED)
    quiet_admin = User(
        name="Quiet Admin",
        email="quiet@doordoctor.in",
        phone="+91 90000 00022",
        password_hash="x",
        role=UserRole.ADMIN,
    )
    db.add(quiet_admin)
    db.flush()
    quiet = care_service.create_manager(db, user=quiet_admin, kind=CareManagerKind.SHARED)

    for index in range(3):
        care_service.assign(db, patient=_extra_patient(db, f"Busy {index}"), manager=busy)

    assignment = care_service.auto_assign(db, db.get(Patient, 1))
    assert assignment.care_manager_id == quiet.id


def test_auto_assign_returns_none_rather_than_failing_when_the_roster_is_full(db, admin_user):
    """Onboarding must not fail because the roster is stretched. An unassigned
    patient is visible on the admin screen; a patient who could not be created
    is not."""
    manager = care_service.create_manager(
        db, user=admin_user, kind=CareManagerKind.SHARED, capacity=1
    )
    care_service.assign(db, patient=_extra_patient(db, "Filler"), manager=manager)
    assert care_service.auto_assign(db, db.get(Patient, 1)) is None


# --------------------------------------------------------------------------
# Interactions
# --------------------------------------------------------------------------


def test_an_interaction_is_logged_against_the_current_manager(db, admin_user, manager):
    patient = db.get(Patient, 1)
    care_service.assign(db, patient=patient, manager=manager)
    interaction = care_service.log_interaction(
        db,
        patient=patient,
        user=admin_user,
        channel=CareChannel.CALL,
        subject="Weekly check-in call",
        note="Spoke to the daughter, all well.",
        minutes=12,
    )
    assert interaction.care_manager_id == manager.id


def test_a_family_does_not_see_internal_handover_notes(db, admin_user, manager):
    patient = db.get(Patient, 1)
    care_service.assign(db, patient=patient, manager=manager)
    care_service.log_interaction(
        db, patient=patient, user=admin_user, channel=CareChannel.CALL, subject="Visible"
    )
    care_service.log_interaction(
        db,
        patient=patient,
        user=admin_user,
        channel=CareChannel.NOTE,
        subject="Internal handover",
        visible_to_family=False,
    )

    family_view = care_service.list_interactions(db, patient.id, for_family=True)
    admin_view = care_service.list_interactions(db, patient.id, for_family=False)
    assert [i.subject for i in family_view] == ["Visible"]
    assert len(admin_view) == 2


# --------------------------------------------------------------------------
# API surface
# --------------------------------------------------------------------------


def test_the_roster_is_admin_only(client, family_headers, nurse_headers, admin_headers):
    assert client.get("/api/v1/care-managers", headers=family_headers).status_code == 403
    assert client.get("/api/v1/care-managers", headers=nurse_headers).status_code == 403
    assert client.get("/api/v1/care-managers", headers=admin_headers).status_code == 200


def test_an_admin_creates_a_manager_and_assigns_a_patient(client, admin_headers, db):
    admin = db.scalar(select(User).where(User.role == UserRole.ADMIN))
    created = client.post(
        "/api/v1/care-managers",
        json={"user_id": admin.id, "kind": "shared", "languages": "English"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["capacity"] == pricing.RATIO_SHARED
    assert created.json()["caseload"] == 0

    assigned = client.post("/api/v1/patients/1/care-team", json={}, headers=admin_headers)
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["care_manager_id"] == created.json()["id"]


def test_a_family_reads_their_own_care_team(client, admin_headers, family_headers, db):
    admin = db.scalar(select(User).where(User.role == UserRole.ADMIN))
    client.post(
        "/api/v1/care-managers", json={"user_id": admin.id, "kind": "shared"}, headers=admin_headers
    )
    client.post("/api/v1/patients/1/care-team", json={}, headers=admin_headers)
    client.post(
        "/api/v1/patients/1/care-interactions",
        json={"channel": "call", "subject": "Introduction call", "minutes": 10},
        headers=admin_headers,
    )

    body = client.get("/api/v1/patients/1/care-team", headers=family_headers).json()
    assert body["assignment"]["care_manager_name"] == admin.name
    assert body["entitled_kind"] == "shared"
    assert [i["subject"] for i in body["interactions"]] == ["Introduction call"]


def test_a_family_cannot_assign_a_care_manager(client, family_headers):
    assert (
        client.post("/api/v1/patients/1/care-team", json={}, headers=family_headers).status_code
        == 403
    )


def test_another_familys_care_team_is_a_404(client, other_family):
    headers = auth(login(client, other_family["email"]))
    assert client.get("/api/v1/patients/1/care-team", headers=headers).status_code == 404


def test_assigning_when_nobody_has_room_is_a_400_with_an_explanation(client, admin_headers, db):
    admin = db.scalar(select(User).where(User.role == UserRole.ADMIN))
    client.post(
        "/api/v1/care-managers",
        json={"user_id": admin.id, "kind": "shared", "capacity": 1},
        headers=admin_headers,
    )
    other = _extra_patient(db, "Filler")
    db.commit()
    client.post(f"/api/v1/patients/{other.id}/care-team", json={}, headers=admin_headers)

    response = client.post("/api/v1/patients/1/care-team", json={}, headers=admin_headers)
    assert response.status_code == 400
    assert "capacity" in response.json()["detail"].lower()
