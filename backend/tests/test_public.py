"""The public price list (§2.6).

The point of these tests is one promise: **the marketing site and the invoice
quote the same number, because they read the same constants through the same
code.** Everything here defends that.
"""

from fastapi.testclient import TestClient

from app.core import pricing

PUBLIC_PLANS = "/api/v1/public/plans"
PLANS = "/api/v1/plans"


def test_the_price_list_needs_no_login(client: TestClient):
    response = client.get(PUBLIC_PLANS)

    assert response.status_code == 200, response.text
    assert response.json()["plans"], "the public price list must not be empty"


def test_the_public_payload_is_identical_to_the_authenticated_one(client: TestClient, family_headers):
    """Not `similar` — identical.

    Two serializers would eventually disagree, and the one that disagreed
    quietly would be the public one. This is the assertion that stops a second
    serializer being written.
    """
    public = client.get(PUBLIC_PLANS).json()["plans"]
    authenticated = client.get(PLANS, headers=family_headers).json()

    assert public == authenticated


def test_the_served_prices_are_the_constants(client: TestClient):
    """The DB round-trip is verified, not assumed. If the seed ever writes a
    price the constants do not hold, this fails rather than the pricing page
    quietly publishing it."""
    served = {plan["code"]: plan for plan in client.get(PUBLIC_PLANS).json()["plans"]}

    for spec in pricing.PLANS:
        assert spec.code in served, spec.code
        assert served[spec.code]["monthly_paise"] == spec.monthly_paise, spec.code
        assert served[spec.code]["annual_paise"] == spec.annual_paise, spec.code


def test_the_recorded_individual_prices_are_published_verbatim(client: TestClient):
    """The three numbers the build prompt records for individuals, spelled out.

    Written as literals on purpose: every other test compares the API to
    `pricing.py`, which would still pass if `pricing.py` itself were edited. This
    one fails if the published price stops being ₹2,500 / ₹3,500 / ₹4,500.
    """
    served = {plan["code"]: plan for plan in client.get(PUBLIC_PLANS).json()["plans"]}

    assert served["essential"]["monthly_paise"] == 250_000
    assert served["care_plus"]["monthly_paise"] == 350_000
    assert served["premium"]["monthly_paise"] == 450_000

    assert served["essential"]["annual_paise"] == 2_500_000
    assert served["care_plus"]["annual_paise"] == 3_500_000
    assert served["premium"]["annual_paise"] == 4_500_000


def test_exactly_one_individual_plan_is_recommended(client: TestClient):
    """₹3,500 is the recommended tier, and the page reads `recommended` rather
    than hard-coding a plan code."""
    plans = client.get(f"{PUBLIC_PLANS}?audience=individual").json()["plans"]
    recommended = [plan for plan in plans if plan["recommended"]]

    assert len(recommended) == 1
    assert recommended[0]["monthly_paise"] == 350_000


def test_the_corporate_and_institutional_headlines_are_published(client: TestClient):
    served = {plan["code"]: plan for plan in client.get(PUBLIC_PLANS).json()["plans"]}

    assert served["corporate"]["unit_paise"] == 280_000  # ₹2,800 per employee per month
    assert served["corporate"]["unit_period"] == "month"

    for code, per_day, monthly in (
        ("institution_15", 8_400, 3_800_000),
        ("institution_25", 7_700, 5_800_000),
        ("institution_40", 6_500, 7_800_000),
    ):
        assert served[code]["unit_paise"] == per_day, code
        assert served[code]["unit_period"] == "day", code
        assert served[code]["monthly_paise"] == monthly, code


def test_the_audience_filter_works_without_a_login(client: TestClient):
    for audience in ("individual", "corporate", "institution"):
        plans = client.get(f"{PUBLIC_PLANS}?audience={audience}").json()["plans"]
        assert plans, audience
        assert {plan["audience"] for plan in plans} == {audience}


def test_the_add_ons_are_published_from_the_constants(client: TestClient):
    add_ons = {a["code"]: a for a in client.get(PUBLIC_PLANS).json()["add_ons"]}

    assert add_ons["blood_panel"]["price_paise"] == 49_900  # ₹499
    assert add_ons["pill_organiser"]["price_paise"] == 19_900  # ₹199
    assert len(add_ons) == len(pricing.ADD_ONS)


def test_the_two_months_free_claim_carries_its_own_number(client: TestClient):
    """The page says "2 months free" in words; this is where that number comes
    from, so the claim cannot outlive the offer."""
    payload = client.get(PUBLIC_PLANS).json()

    assert payload["annual_months_free"] == 2
    assert payload["annual_months_free"] == pricing.ANNUAL_MONTHS_FREE


def test_the_public_endpoint_exposes_no_subscriber_data(client: TestClient):
    """A price list is what DoorDoctor tells strangers. Nothing about a named
    person may ride along in the same payload."""
    payload = client.get(PUBLIC_PLANS).json()

    assert set(payload) == {"plans", "add_ons", "annual_months_free"}
    for plan in payload["plans"]:
        assert "subscriptions" not in plan
        assert "subscriber_count" not in plan


def test_no_other_route_became_public(client: TestClient):
    """Guards against an auth dependency being dropped while adding this router."""
    for path in (
        "/api/v1/patients",
        "/api/v1/visits",
        "/api/v1/subscriptions",
        "/api/v1/leads",
        PLANS,
    ):
        assert client.get(path).status_code == 401, path
