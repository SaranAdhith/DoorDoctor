"""Public lead capture (§2.6).

`POST /leads` is the only endpoint in this codebase a stranger can write to, so
these tests are weighted towards what happens when the stranger is hostile
rather than towards the happy path.
"""

from fastapi.testclient import TestClient

from app.core.ratelimit import LEADS_PER_EMAIL, LEADS_PER_IP
from app.schemas.lead import MAX_MESSAGE_CHARS, MAX_NAME_CHARS

LEADS = "/api/v1/leads"


def _payload(**overrides) -> dict:
    payload = {
        "name": "Ramesh Iyer",
        "email": "Ramesh.Iyer@Example.com",
        "phone": "+91 98450 12345",
        "city": "Bengaluru",
        "kind": "family",
        "message": "My mother is 78 and lives alone. What would you recommend?",
        "source_page": "/pricing",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------


def test_anyone_can_submit_an_enquiry_without_signing_in(client: TestClient):
    response = client.post(LEADS, json=_payload())

    assert response.status_code == 201, response.text
    assert "in touch" in response.json()["message"]
    # The reply carries no id and no echo of the submission.
    assert set(response.json()) == {"message"}


def test_a_submitted_enquiry_reaches_the_admin_queue(client: TestClient, admin_headers):
    client.post(LEADS, json=_payload())

    leads = client.get(LEADS, headers=admin_headers).json()

    assert len(leads) == 1
    assert leads[0]["name"] == "Ramesh Iyer"
    assert leads[0]["status"] == "new"
    assert leads[0]["source_page"] == "/pricing"
    assert leads[0]["handled_by"] is None


def test_the_email_is_stored_lowercased(client: TestClient, admin_headers):
    """The rate limiter keys on the address, so two spellings must be one person."""
    client.post(LEADS, json=_payload(email="Ramesh.Iyer@Example.com"))

    lead = client.get(LEADS, headers=admin_headers).json()[0]
    assert lead["email"] == "ramesh.iyer@example.com"


def test_every_enquiry_kind_is_accepted(client: TestClient, admin_headers):
    for index, kind in enumerate(("family", "corporate", "institution", "nri", "other")):
        response = client.post(
            LEADS, json=_payload(kind=kind, email=f"lead-{index}@example.com")
        )
        assert response.status_code == 201, response.text

    kinds = {lead["kind"] for lead in client.get(LEADS, headers=admin_headers).json()}
    assert kinds == {"family", "corporate", "institution", "nri", "other"}


def test_only_a_name_and_an_email_are_required(client: TestClient):
    response = client.post(LEADS, json={"name": "Anon", "email": "anon@example.com"})
    assert response.status_code == 201, response.text


# --------------------------------------------------------------------------
# The honeypot
# --------------------------------------------------------------------------


def test_a_filled_honeypot_stores_nothing(client: TestClient, admin_headers):
    client.post(LEADS, json=_payload(company_website="https://spam.example.com"))

    assert client.get(LEADS, headers=admin_headers).json() == []


def test_a_filled_honeypot_answers_exactly_like_a_real_submission(client: TestClient):
    """A 400 would tell a bot its script was detected. The bodies must be identical."""
    real = client.post(LEADS, json=_payload(email="real@example.com"))
    bot = client.post(
        LEADS, json=_payload(email="bot@example.com", company_website="https://spam.example.com")
    )

    assert bot.status_code == real.status_code
    assert bot.json() == real.json()


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_the_same_email_is_limited(client: TestClient):
    limit, _ = LEADS_PER_EMAIL
    for _ in range(limit):
        assert client.post(LEADS, json=_payload()).status_code == 201

    response = client.post(LEADS, json=_payload())

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert int(response.headers["Retry-After"]) > 0


def test_one_address_is_limited_across_different_emails(client: TestClient):
    """The per-email budget alone would let one host post from endless addresses."""
    limit, _ = LEADS_PER_IP
    for index in range(limit):
        response = client.post(LEADS, json=_payload(email=f"visitor-{index}@example.com"))
        assert response.status_code == 201, response.text

    response = client.post(LEADS, json=_payload(email="one-too-many@example.com"))
    assert response.status_code == 429


def test_the_limit_message_is_human(client: TestClient):
    limit, _ = LEADS_PER_EMAIL
    for _ in range(limit):
        client.post(LEADS, json=_payload())

    detail = client.post(LEADS, json=_payload()).json()["detail"]
    assert "try again" in detail.lower()


# --------------------------------------------------------------------------
# Caps and validation
# --------------------------------------------------------------------------


def test_an_over_long_message_is_refused(client: TestClient):
    response = client.post(LEADS, json=_payload(message="x" * (MAX_MESSAGE_CHARS + 1)))
    assert response.status_code == 422


def test_an_over_long_name_is_refused(client: TestClient):
    response = client.post(LEADS, json=_payload(name="x" * (MAX_NAME_CHARS + 1)))
    assert response.status_code == 422


def test_an_implausible_email_is_refused(client: TestClient):
    for address in ("not-an-email", "@example.com", "someone@"):
        response = client.post(LEADS, json=_payload(email=address))
        assert response.status_code == 422, address


def test_a_blank_name_is_refused(client: TestClient):
    assert client.post(LEADS, json=_payload(name="   ")).status_code == 422


def test_unknown_fields_are_ignored_rather_than_rejected(client: TestClient):
    """A scraper posting junk keys learns nothing from a bland 201."""
    response = client.post(LEADS, json={**_payload(), "utm_source": "somewhere", "x": 1})
    assert response.status_code == 201, response.text


# --------------------------------------------------------------------------
# Reads are admin-only — a lead list is a list of named strangers
# --------------------------------------------------------------------------


def test_anonymous_callers_cannot_read_leads(client: TestClient):
    assert client.get(LEADS).status_code == 401


def test_a_family_member_cannot_read_leads(client: TestClient, family_headers):
    assert client.get(LEADS, headers=family_headers).status_code == 403


def test_a_nurse_cannot_read_leads(client: TestClient, nurse_headers):
    assert client.get(LEADS, headers=nurse_headers).status_code == 403


def test_a_family_member_cannot_work_a_lead(client: TestClient, family_headers, admin_headers):
    client.post(LEADS, json=_payload())
    lead_id = client.get(LEADS, headers=admin_headers).json()[0]["id"]

    response = client.patch(
        f"{LEADS}/{lead_id}", json={"status": "contacted"}, headers=family_headers
    )
    assert response.status_code == 403


def test_the_summary_is_admin_only(client: TestClient, family_headers):
    assert client.get(f"{LEADS}/summary", headers=family_headers).status_code == 403


# --------------------------------------------------------------------------
# Working the queue
# --------------------------------------------------------------------------


def test_an_admin_marks_a_lead_contacted_and_is_recorded_as_having_done_so(
    client: TestClient, admin_headers
):
    client.post(LEADS, json=_payload())
    lead_id = client.get(LEADS, headers=admin_headers).json()[0]["id"]

    response = client.patch(
        f"{LEADS}/{lead_id}",
        json={"status": "contacted", "admin_note": "Called; wants a callback on Monday."},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    lead = response.json()
    assert lead["status"] == "contacted"
    assert lead["admin_note"] == "Called; wants a callback on Monday."
    assert lead["handled_by"] is not None
    assert lead["handled_at"] is not None


def test_moving_a_lead_back_to_new_clears_who_handled_it(client: TestClient, admin_headers):
    """A stale name on an unworked enquiry is worse than no name."""
    client.post(LEADS, json=_payload())
    lead_id = client.get(LEADS, headers=admin_headers).json()[0]["id"]
    client.patch(f"{LEADS}/{lead_id}", json={"status": "contacted"}, headers=admin_headers)

    lead = client.patch(
        f"{LEADS}/{lead_id}", json={"status": "new"}, headers=admin_headers
    ).json()

    assert lead["status"] == "new"
    assert lead["handled_by"] is None
    assert lead["handled_at"] is None


def test_a_note_can_be_added_without_moving_the_status(client: TestClient, admin_headers):
    client.post(LEADS, json=_payload())
    lead_id = client.get(LEADS, headers=admin_headers).json()[0]["id"]

    lead = client.patch(
        f"{LEADS}/{lead_id}", json={"admin_note": "Left a voicemail."}, headers=admin_headers
    ).json()

    assert lead["status"] == "new"
    assert lead["admin_note"] == "Left a voicemail."


def test_working_an_unknown_lead_is_a_404(client: TestClient, admin_headers):
    response = client.patch(f"{LEADS}/9999", json={"status": "closed"}, headers=admin_headers)
    assert response.status_code == 404


def test_leads_can_be_filtered_by_status_and_kind(client: TestClient, admin_headers):
    client.post(LEADS, json=_payload(email="a@example.com", kind="family"))
    client.post(LEADS, json=_payload(email="b@example.com", kind="corporate"))
    first = client.get(LEADS, headers=admin_headers).json()[0]["id"]
    client.patch(f"{LEADS}/{first}", json={"status": "closed"}, headers=admin_headers)

    new_only = client.get(f"{LEADS}?status=new", headers=admin_headers).json()
    corporate_only = client.get(f"{LEADS}?kind=corporate", headers=admin_headers).json()

    assert [lead["status"] for lead in new_only] == ["new"]
    assert [lead["kind"] for lead in corporate_only] == ["corporate"]


def test_leads_are_listed_newest_first(client: TestClient, admin_headers):
    client.post(LEADS, json=_payload(name="First", email="first@example.com"))
    client.post(LEADS, json=_payload(name="Second", email="second@example.com"))

    names = [lead["name"] for lead in client.get(LEADS, headers=admin_headers).json()]
    assert names == ["Second", "First"]


def test_the_summary_counts_by_status_and_kind(client: TestClient, admin_headers):
    client.post(LEADS, json=_payload(email="a@example.com", kind="family"))
    client.post(LEADS, json=_payload(email="b@example.com", kind="corporate"))
    first = client.get(LEADS, headers=admin_headers).json()[0]["id"]
    client.patch(f"{LEADS}/{first}", json={"status": "contacted"}, headers=admin_headers)

    summary = client.get(f"{LEADS}/summary", headers=admin_headers).json()

    assert summary["total"] == 2
    assert summary["new"] == 1
    assert summary["contacted"] == 1
    assert summary["qualified"] == 0
    assert summary["closed"] == 0
    assert summary["by_kind"] == {"family": 1, "corporate": 1}


def test_the_summary_reports_zeroes_rather_than_missing_keys(client: TestClient, admin_headers):
    """`SMALL` seeds no leads, so the admin queue's first render is this payload."""
    summary = client.get(f"{LEADS}/summary", headers=admin_headers).json()

    assert summary == {
        "total": 0,
        "new": 0,
        "contacted": 0,
        "qualified": 0,
        "closed": 0,
        "by_kind": {},
    }
