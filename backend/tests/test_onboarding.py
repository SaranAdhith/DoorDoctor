"""Phase 10 — onboarding (§4.15).

One idea: **a step is complete because the thing is true, not because somebody
clicked.** Four of the five steps read the table that would carry the result, so
the checklist cannot drift away from what it describes — and if a family empties
their care circle, that step goes back to incomplete, which is the checklist
being honest rather than broken.
"""

API = "/api/v1"


def _progress(client, headers) -> dict:
    response = client.get(f"{API}/onboarding/patients/1", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _step(body: dict, key: str) -> dict:
    return next(step for step in body["steps"] if step["key"] == key)


def test_the_checklist_lists_every_step_with_somewhere_to_go(client, family_headers):
    body = _progress(client, family_headers)
    assert body["total"] == len(body["steps"])
    for step in body["steps"]:
        assert step["label"] and step["blurb"] and step["path"].startswith("/family/")


def test_thresholds_are_already_done_because_the_patient_has_them(client, family_headers):
    """Sensible defaults are in place from the first visit; the step reads them."""
    assert _step(_progress(client, family_headers), "thresholds")["done"] is True


def test_the_care_circle_step_ignores_the_automatic_primary_member(client, family_headers):
    """The primary is created for them, so its existence proves nothing."""
    client.get(f"{API}/patients/1/care-circle", headers=family_headers)  # creates the primary
    assert _step(_progress(client, family_headers), "care_circle")["done"] is False

    client.post(
        f"{API}/patients/1/care-circle",
        json={"name": "Vasanthi Rao", "relationship_label": "Neighbour", "phone": "+91 90000 30001"},
        headers=family_headers,
    )
    assert _step(_progress(client, family_headers), "care_circle")["done"] is True


def test_a_step_goes_back_to_incomplete_when_the_thing_stops_being_true(client, family_headers):
    member = client.post(
        f"{API}/patients/1/care-circle",
        json={"name": "Vasanthi Rao", "relationship_label": "Neighbour", "phone": "+91 90000 30001"},
        headers=family_headers,
    ).json()
    assert _step(_progress(client, family_headers), "care_circle")["done"] is True

    client.delete(f"{API}/care-circle/{member['id']}", headers=family_headers)
    assert _step(_progress(client, family_headers), "care_circle")["done"] is False


def test_consent_completes_when_the_required_consents_are_granted(client, family_headers):
    before = _step(_progress(client, family_headers), "consent")["done"]
    client.post(
        f"{API}/privacy/consents",
        json={"kind": "care_delivery", "granted": True, "patient_id": 1},
        headers=family_headers,
    )
    assert _step(_progress(client, family_headers), "consent")["done"] is True
    assert before in (True, False)


def test_notifications_completes_once_preferences_exist(client, family_headers):
    client.get(f"{API}/notifications/preferences", headers=family_headers)
    assert _step(_progress(client, family_headers), "notifications")["done"] is True


def test_confirming_the_patient_is_the_one_step_that_is_a_tick(client, family_headers):
    assert _step(_progress(client, family_headers), "confirm_patient")["derived"] is False
    body = client.post(
        f"{API}/onboarding/patients/1/steps/confirm_patient", headers=family_headers
    ).json()
    assert _step(body, "confirm_patient")["done"] is True


def test_acknowledging_twice_is_harmless(client, family_headers):
    for _ in range(2):
        response = client.post(
            f"{API}/onboarding/patients/1/steps/confirm_patient", headers=family_headers
        )
        assert response.status_code == 200


def test_a_derived_step_refuses_to_be_ticked(client, family_headers):
    response = client.post(
        f"{API}/onboarding/patients/1/steps/care_circle", headers=family_headers
    )
    assert response.status_code == 400
    assert "nothing to tick" in response.json()["detail"]


def test_an_unknown_step_is_refused(client, family_headers):
    assert (
        client.post(
            f"{API}/onboarding/patients/1/steps/buy_a_pony", headers=family_headers
        ).status_code
        == 400
    )


def test_next_step_points_at_the_first_thing_left_to_do(client, family_headers):
    body = _progress(client, family_headers)
    if body["complete"]:
        assert body["next_step"] is None
    else:
        assert body["next_step"]["done"] is False
        assert body["next_step"]["key"] == next(s["key"] for s in body["steps"] if not s["done"])


def test_another_family_cannot_read_this_checklist(client, other_family):
    from tests.conftest import DEMO_PASSWORD, auth, login

    headers = auth(login(client, other_family["email"], DEMO_PASSWORD))
    assert client.get(f"{API}/onboarding/patients/1", headers=headers).status_code == 404
