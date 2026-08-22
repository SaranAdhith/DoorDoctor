"""Plain-language summaries (§2.2).

The banned-word test *is* the specification for this feature. If it is ever
loosened, the feature has been lost regardless of what the rest of the suite
says.
"""

import pytest
from sqlalchemy import select

from app.models import Patient
from app.services import llm_client, summary_service
from tests.conftest import ABNORMAL_VITALS, auth, login

WINDOWS = ("7d", "30d", "90d")


def _all_prose(payload: dict) -> list[str]:
    """Every string a family member can actually read."""
    return [
        payload["headline"],
        *payload["paragraphs"],
        *[h["text"] for h in payload["highlights"]],
        *payload["what_happens_next"],
        payload["disclaimer"],
        payload["window_label"],
    ]


# --------------------------------------------------------------------------
# The vocabulary rule
# --------------------------------------------------------------------------


@pytest.mark.parametrize("window", WINDOWS)
def test_summary_never_uses_clinical_language(client, family_headers, window):
    response = client.get(f"/api/v1/patients/1/plain-summary?window={window}", headers=family_headers)
    assert response.status_code == 200, response.text

    for text in _all_prose(response.json()):
        offender = summary_service.contains_clinical_language(text)
        assert offender is None, f"{window} summary said {offender!r} in: {text}"


def test_banned_word_check_catches_inflections():
    # "thresholds" and "breached" are the same failure as their stems. A
    # word-boundary check would let every one of them through.
    assert summary_service.contains_clinical_language("no thresholds were crossed") == "threshold"
    assert summary_service.contains_clinical_language("the reading breached the range") == "breach"
    assert summary_service.contains_clinical_language("SpO2 was 98") == "spo2"
    assert summary_service.contains_clinical_language("her blood pressure was steady") is None


def test_summary_talks_about_blood_pressure_not_systolic(client, family_headers):
    payload = client.get("/api/v1/patients/1/plain-summary?window=30d", headers=family_headers).json()
    prose = " ".join(_all_prose(payload)).lower()
    assert "blood pressure" in prose


# --------------------------------------------------------------------------
# Content
# --------------------------------------------------------------------------


def test_summary_counts_match_the_window(client, family_headers):
    week = client.get("/api/v1/patients/1/plain-summary?window=7d", headers=family_headers).json()
    quarter = client.get("/api/v1/patients/1/plain-summary?window=90d", headers=family_headers).json()

    assert quarter["reading_count"] >= week["reading_count"]
    assert quarter["dose_count"] >= week["dose_count"]
    assert week["window_label"] == "the last 7 days"
    assert quarter["window_label"] == "the last 3 months"


def test_summary_is_honest_when_there_is_no_data(client, db, family_headers):
    """A patient with no readings gets an honest empty summary.

    Not a 404, and above all not a fabricated reassurance — an invented "doing
    well" is the single worst thing this feature could produce.
    """
    patient = Patient(
        name="Newly Enrolled",
        age=70,
        gender="Female",
        address="Koramangala, Bengaluru",
        family_user_id=db.scalar(select(Patient.family_user_id).where(Patient.id == 1)),
    )
    db.add(patient)
    db.commit()

    response = client.get(f"/api/v1/patients/{patient.id}/plain-summary", headers=family_headers)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["reading_count"] == 0
    assert "not recorded any checks" in payload["headline"]
    assert payload["paragraphs"], "an empty window still owes the reader an explanation"
    for text in _all_prose(payload):
        assert summary_service.contains_clinical_language(text) is None


def test_summary_reports_deterministic_provenance_without_a_key(client, family_headers):
    payload = client.get("/api/v1/patients/1/plain-summary", headers=family_headers).json()
    assert payload["source"] == "deterministic"
    assert not llm_client.available()


def test_summary_reflects_a_new_reading(client, family_headers, nurse_headers, started_visit_id):
    """The demo path: record 148/92 and the summary notices."""
    before = client.get("/api/v1/patients/1/plain-summary", headers=family_headers).json()
    assert before["open_alert_count"] == 0

    recorded = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=ABNORMAL_VITALS, headers=nurse_headers
    )
    assert recorded.status_code == 201, recorded.text

    after = client.get("/api/v1/patients/1/plain-summary", headers=family_headers).json()
    assert after["reading_count"] == before["reading_count"] + 1
    assert after["open_alert_count"] == 1
    assert after["flagged_count"] >= 1
    assert "closer look" in after["headline"]
    for text in _all_prose(after):
        assert summary_service.contains_clinical_language(text) is None


# --------------------------------------------------------------------------
# Authorization — the same disclosure rule as everywhere else
# --------------------------------------------------------------------------


def test_another_familys_summary_is_a_404_not_a_403(client, other_family):
    """A 403 would confirm the record exists, which is enough to learn that a
    named person is a DoorDoctor patient."""
    headers = auth(login(client, other_family["email"]))
    response = client.get("/api/v1/patients/1/plain-summary", headers=headers)
    assert response.status_code == 404


def test_summary_requires_a_token(client):
    assert client.get("/api/v1/patients/1/plain-summary").status_code == 401


def test_assigned_nurse_may_read_the_summary(client, nurse_headers):
    assert client.get("/api/v1/patients/1/plain-summary", headers=nurse_headers).status_code == 200


def test_admin_may_read_any_summary(client, admin_headers):
    assert client.get("/api/v1/patients/1/plain-summary", headers=admin_headers).status_code == 200


def test_unknown_window_is_rejected(client, family_headers):
    response = client.get("/api/v1/patients/1/plain-summary?window=1y", headers=family_headers)
    assert response.status_code == 422


def test_missing_patient_is_a_404(client, family_headers):
    assert client.get("/api/v1/patients/9999/plain-summary", headers=family_headers).status_code == 404


# --------------------------------------------------------------------------
# The optional rewrite — four gates between a model and a family member
# --------------------------------------------------------------------------


@pytest.fixture
def assisted(monkeypatch):
    """Make the assisted path reachable, and hand back a call counter."""
    monkeypatch.setattr(llm_client.settings, "groq_api_key", "test-key", raising=False)
    monkeypatch.setattr(llm_client.settings, "assistant_enabled", True, raising=False)
    calls: list[str] = []

    def install(reply):
        def fake(*, system, user, timeout, max_tokens=400, temperature=0.2):
            calls.append(user)
            return reply(user) if callable(reply) else reply

        monkeypatch.setattr(summary_service.llm_client, "complete", fake)

    return install, calls


def _summary(client, headers, window="30d") -> dict:
    response = client.get(f"/api/v1/patients/1/plain-summary?window={window}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_clean_rewrite_is_used_and_declared(client, family_headers, assisted):
    install, calls = assisted
    install(lambda source: "Lakshmi has had a calm month.\n\n" + source.split("\n\n", 1)[1])

    payload = _summary(client, family_headers)
    assert payload["source"] == "assisted"
    assert payload["headline"] == "Lakshmi has had a calm month."
    assert len(calls) == 1


def test_a_rewrite_that_reintroduces_clinical_language_is_discarded(client, family_headers, assisted):
    install, _ = assisted
    install("Her systolic trend is fine.\n\nNo threshold breach was recorded this month at all.")

    payload = _summary(client, family_headers)
    assert payload["source"] == "deterministic"
    assert summary_service.contains_clinical_language(payload["headline"]) is None


def test_a_rewrite_that_invents_a_number_is_discarded(client, family_headers, assisted):
    """The anti-hallucination gate, and the one that matters most.

    A model cannot invent a reading if a digit it was never given is grounds for
    rejection.
    """
    install, _ = assisted
    install(
        lambda source: source.replace("\n\n", "\n\nHer blood pressure reached 191 over 121. ", 1)
    )

    payload = _summary(client, family_headers)
    assert payload["source"] == "deterministic"
    assert "191" not in " ".join(_all_prose(payload))


def test_a_rewrite_that_drifts_into_advice_is_discarded(client, family_headers, assisted):
    install, _ = assisted
    install(
        lambda source: "Lakshmi is stable.\n\nI recommend you take her to the "
        "emergency room today. " + source.split("\n\n", 1)[1]
    )

    payload = _summary(client, family_headers)
    assert payload["source"] == "deterministic"


@pytest.mark.parametrize("reply", ["Too short.\n\nTiny.", None, "no blank lines at all here"])
def test_unusable_rewrites_fall_back_silently(client, family_headers, assisted, reply):
    install, _ = assisted
    install(reply)

    payload = _summary(client, family_headers)
    assert payload["source"] == "deterministic"
    assert payload["paragraphs"], "the reader still gets a summary"


def test_repeated_reads_hit_the_cache(client, family_headers, assisted):
    install, calls = assisted
    install(lambda source: "A calm month.\n\n" + source.split("\n\n", 1)[1])

    first = _summary(client, family_headers)
    second = _summary(client, family_headers)

    assert first["headline"] == second["headline"] == "A calm month."
    assert len(calls) == 1, "the second read should have been served from the cache"


def test_each_window_is_cached_separately(client, family_headers, assisted):
    install, calls = assisted
    install(lambda source: "A calm period.\n\n" + source.split("\n\n", 1)[1])

    _summary(client, family_headers, "7d")
    _summary(client, family_headers, "30d")
    _summary(client, family_headers, "7d")

    assert len(calls) == 2


def test_a_new_reading_busts_the_cache(
    client, family_headers, nurse_headers, started_visit_id, assisted
):
    """The TTL is a cost control. Correctness comes from the content fingerprint.

    Time alone would keep serving the last quarter-hour's paragraph after a
    nurse records a new reading.
    """
    install, calls = assisted
    install(lambda source: "A calm month.\n\n" + source.split("\n\n", 1)[1])

    _summary(client, family_headers, "7d")
    _summary(client, family_headers, "7d")
    assert len(calls) == 1

    client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=ABNORMAL_VITALS, headers=nurse_headers
    )

    _summary(client, family_headers, "7d")
    assert len(calls) == 2, "new data must not be answered from a stale cache entry"


def test_no_upstream_call_is_made_when_no_key_is_configured(client, family_headers, monkeypatch):
    def explode(**kwargs):  # pragma: no cover - must never run
        raise AssertionError("the summary reached for a model with no key configured")

    monkeypatch.setattr(summary_service.llm_client, "complete", explode)
    assert _summary(client, family_headers)["source"] == "deterministic"
