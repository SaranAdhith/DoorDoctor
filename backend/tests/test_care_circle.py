"""Phase 10 — the care circle (§4.13).

The circle exists for the person who is not on the account: the neighbour with
the spare key, the uncle ten minutes away. So the tests care most about two
things — that a member with no login is a full member, and that nobody is told
they will be contacted through a channel that does not exist.
"""

from sqlalchemy import select

from app.core.ops import CARE_CIRCLE_MAX_MEMBERS
from app.models import CareCircleMember, CareCircleRole

API = "/api/v1"


def _add(client, headers, **overrides):
    payload = {
        "name": "Vasanthi Rao",
        "relationship_label": "Neighbour",
        "phone": "+91 90000 20001",
        "role": "emergency_contact",
        "receives_alerts": True,
    }
    payload.update(overrides)
    return client.post(f"{API}/patients/1/care-circle", json=payload, headers=headers)


def test_the_family_user_is_the_primary_member(client, family_headers):
    response = client.get(f"{API}/patients/1/care-circle", headers=family_headers)
    assert response.status_code == 200
    primary = response.json()[0]
    assert primary["is_primary"] is True
    assert primary["name"] == "Darren D'Souza"
    assert primary["has_login"] is True
    assert primary["receives_alerts"] is True


def test_a_member_with_no_login_is_a_full_member(client, family_headers):
    """The neighbour with the spare key has no account and never will."""
    body = _add(client, family_headers).json()
    assert body["has_login"] is False
    assert body["user_id"] is None
    assert body["receives_alerts"] is True
    assert body["role"] == "emergency_contact"


def test_somebody_with_no_contact_details_cannot_be_told_they_will_be_contacted(
    client, family_headers
):
    """A promise the platform cannot keep is refused at the boundary, not at 2am."""
    response = _add(client, family_headers, phone=None, email=None, receives_alerts=True)
    assert response.status_code == 400
    assert "phone number or an email" in response.json()["detail"]


def test_somebody_with_no_contact_details_can_still_be_recorded(client, family_headers):
    response = _add(
        client, family_headers, phone=None, email=None, receives_alerts=False, name="Old friend"
    )
    assert response.status_code == 201
    assert response.json()["receives_alerts"] is False


def test_the_same_email_cannot_be_added_twice(client, family_headers):
    _add(client, family_headers, email="rohan@example.in", name="Rohan")
    duplicate = _add(client, family_headers, email="ROHAN@example.in", name="Rohan again")
    assert duplicate.status_code == 409


def test_the_circle_has_a_cap(client, family_headers):
    for index in range(CARE_CIRCLE_MAX_MEMBERS + 2):
        response = _add(client, family_headers, name=f"Person {index}", email=f"p{index}@example.in")
        if response.status_code == 409:
            break
    else:  # pragma: no cover - the cap must be reachable
        raise AssertionError("the care circle cap was never reached")
    assert "at most" in response.json()["detail"]


def test_the_primary_contact_cannot_be_removed(client, family_headers, db):
    primary = db.scalar(
        select(CareCircleMember).where(
            CareCircleMember.patient_id == 1, CareCircleMember.is_primary.is_(True)
        )
    )
    if primary is None:
        client.get(f"{API}/patients/1/care-circle", headers=family_headers)
        primary = db.scalar(
            select(CareCircleMember).where(
                CareCircleMember.patient_id == 1, CareCircleMember.is_primary.is_(True)
            )
        )
    response = client.delete(f"{API}/care-circle/{primary.id}", headers=family_headers)
    assert response.status_code == 400
    assert "primary contact" in response.json()["detail"]


def test_the_primary_contact_cannot_opt_out_of_alerts(client, family_headers, db):
    client.get(f"{API}/patients/1/care-circle", headers=family_headers)
    primary = db.scalar(
        select(CareCircleMember).where(
            CareCircleMember.patient_id == 1, CareCircleMember.is_primary.is_(True)
        )
    )
    response = client.patch(
        f"{API}/care-circle/{primary.id}", json={"receives_alerts": False}, headers=family_headers
    )
    assert response.status_code == 400


def test_a_member_can_be_removed_and_updated(client, family_headers):
    member = _add(client, family_headers).json()
    updated = client.patch(
        f"{API}/care-circle/{member['id']}",
        json={"relationship_label": "Neighbour and keyholder"},
        headers=family_headers,
    )
    assert updated.json()["relationship_label"] == "Neighbour and keyholder"
    assert client.delete(f"{API}/care-circle/{member['id']}", headers=family_headers).status_code == 204


def test_a_nurse_reads_the_circle_but_cannot_change_it(client, nurse_headers, family_headers):
    _add(client, family_headers)
    assert client.get(f"{API}/patients/1/care-circle", headers=nurse_headers).status_code == 200
    assert _add(client, nurse_headers, name="Someone else").status_code == 403


def test_a_nurse_sees_contact_details_only_for_the_people_an_emergency_needs(
    client, nurse_headers, family_headers
):
    _add(client, family_headers, name="Rohan", role="contributor", email="rohan@example.in")
    _add(client, family_headers, name="Vasanthi", role="emergency_contact")

    members = {m["name"]: m for m in client.get(
        f"{API}/patients/1/care-circle", headers=nurse_headers
    ).json()}
    assert members["Darren D'Souza"]["phone"] is not None  # primary contact
    assert members["Vasanthi"]["phone"] is not None  # emergency contact
    assert members["Rohan"]["phone"] is None and members["Rohan"]["email"] is None


def test_another_family_cannot_see_or_touch_this_circle(client, family_headers, other_family):
    from tests.conftest import DEMO_PASSWORD, auth, login

    member = _add(client, family_headers).json()
    stranger = auth(login(client, other_family["email"], DEMO_PASSWORD))

    assert client.get(f"{API}/patients/1/care-circle", headers=stranger).status_code == 404
    assert client.patch(
        f"{API}/care-circle/{member['id']}", json={"name": "Mine now"}, headers=stranger
    ).status_code == 404
    assert client.delete(f"{API}/care-circle/{member['id']}", headers=stranger).status_code == 404


def test_circle_changes_are_audited(client, family_headers, db):
    from app.models import AuditAction, AuditEvent

    _add(client, family_headers)
    entry = db.scalar(
        select(AuditEvent).where(AuditEvent.action == AuditAction.CARE_CIRCLE_CHANGED)
    )
    assert entry is not None
    assert entry.patient_id == 1


def test_alert_recipients_are_the_reachable_ones_who_asked(client, db, family_headers):
    from app.services import care_circle_service

    client.get(f"{API}/patients/1/care-circle", headers=family_headers)
    _add(client, family_headers, name="Reachable", receives_alerts=True)
    _add(
        client,
        family_headers,
        name="Not listening",
        email="quiet@example.in",
        receives_alerts=False,
    )

    names = {member.name for member in care_circle_service.alert_recipients(db, 1)}
    assert "Reachable" in names
    assert "Not listening" not in names
