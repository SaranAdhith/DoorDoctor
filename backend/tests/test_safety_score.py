"""The Senior Safety Score (§4.5).

RECORDED and therefore pinned as literals: the score runs 0-100, it is
deterministic, and a drop of 10 or more points inside 30 days raises an alert.

Everything else is `ASSUMED` and is asserted *against `core/clinical.py`* rather
than against a number typed here — so reconciling the real §4 stays a one-file
edit and does not require rewriting this module. The two exceptions are marked.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core import clinical
from app.database import now
from app.models import (
    Alert,
    Notification,
    Patient,
    SafetyScore,
    Screening,
    ScreeningInstrument,
    Vital,
)
from app.services import safety_score, summary_service

from .conftest import NORMAL_VITALS, auth, login


@pytest.fixture
def patient(db) -> Patient:
    return db.get(Patient, 1)


# --------------------------------------------------------------------------
# The constant block itself
# --------------------------------------------------------------------------


def test_the_weights_sum_to_one_hundred():
    """A 94-point scale reported as "out of 100" is a lie the UI cannot detect."""
    assert sum(clinical.SAFETY_WEIGHTS.values()) == clinical.SCORE_MAX


def test_every_component_has_a_function_and_every_function_has_a_component():
    assert set(safety_score.COMPONENT_FUNCTIONS) == set(clinical.SAFETY_WEIGHTS)


def test_the_bands_tile_the_whole_range_without_a_gap():
    floors = [band.floor for band in clinical.SAFETY_BANDS]
    assert floors == sorted(floors, reverse=True), "bands must be ordered high to low"
    assert floors[-1] == clinical.SCORE_MIN, "the lowest band must catch every score"
    for score in range(clinical.SCORE_MIN, clinical.SCORE_MAX + 1):
        assert clinical.band_for(score) is not None


def test_no_clinical_constant_is_duplicated_into_the_service():
    """`core/clinical.py` is the one file the founder edits when §4 arrives.

    A weight, a band floor or a window typed into the service breaks that
    promise silently — reconciling would then need two edits and nothing would
    say so. This asserts the literals in `safety_score.py` and the values in
    `clinical.py` are disjoint.

    0 and 1 are excluded: they are structural (an empty sum, a `case` default, a
    clamp bound) and appear in both by coincidence, not by duplication.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(safety_score))
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    }

    clinical_values = set(clinical.SAFETY_WEIGHTS.values())
    clinical_values |= {band.floor for band in clinical.SAFETY_BANDS}
    clinical_values |= {
        clinical.SAFETY_WINDOW_DAYS,
        clinical.SAFETY_DROP_POINTS,
        clinical.SAFETY_DROP_WINDOW_DAYS,
        clinical.SAFETY_MIN_COVERED_WEIGHT,
        clinical.SAFETY_MIN_READINGS,
        clinical.SAFETY_ALERT_SATURATION,
        clinical.SAFETY_CRITICAL_MULTIPLIER,
        clinical.SAFETY_MOOD_LOOKBACK_DAYS,
        clinical.SCORE_MAX,
    }
    structural = {0, 1, 0.0, 1.0}

    duplicated = (literals - structural) & (clinical_values - structural)
    assert not duplicated, f"clinical constants duplicated into safety_score.py: {duplicated}"


# --------------------------------------------------------------------------
# The rule that matters most: missing data is not zero
# --------------------------------------------------------------------------


def test_a_component_with_no_data_is_dropped_not_scored_zero(db, patient):
    """No mood check on file must not read as "worst possible mood"."""
    payload = safety_score.compute(db, patient)
    mood = next(c for c in payload["components"] if c["key"] == "mood")

    assert mood["has_data"] is False
    assert mood["points"] is None
    assert payload["covered_weight"] < payload["total_weight"]
    assert mood["weight"] not in (payload["covered_weight"],)


def test_the_score_is_rescaled_across_the_weights_that_had_data(db, patient):
    payload = safety_score.compute(db, patient)
    earned = sum(c["points"] for c in payload["components"] if c["has_data"])
    expected = int(round(earned / payload["covered_weight"] * clinical.SCORE_MAX))
    # Rounding of the stored per-component points can move the total by one.
    assert abs(payload["score"] - expected) <= 1


def test_too_little_data_publishes_no_score_at_all(db, other_family):
    """A patient with almost nothing recorded gets an honest refusal.

    A number derived from one component looks exactly as authoritative as a real
    one, which is what makes it worse than saying nothing.
    """
    patient = db.get(Patient, other_family["patient_id"])
    payload = safety_score.compute(db, patient)

    assert payload["available"] is False
    assert payload["score"] is None
    assert payload["covered_weight"] < clinical.SAFETY_MIN_COVERED_WEIGHT
    assert payload["unavailable_reason"]


def test_nothing_is_stored_when_no_score_can_be_published(db, other_family):
    patient = db.get(Patient, other_family["patient_id"])
    assert safety_score.record(db, patient) is None
    assert db.scalars(select(SafetyScore).where(SafetyScore.patient_id == patient.id)).first() is None


# --------------------------------------------------------------------------
# Determinism and range
# --------------------------------------------------------------------------


def test_the_score_is_deterministic(db, patient):
    moment = now()
    first = safety_score.compute(db, patient, as_of=moment)
    second = safety_score.compute(db, patient, as_of=moment)
    assert first == second


def test_the_score_stays_inside_zero_to_one_hundred(db, patient):
    payload = safety_score.compute(db, patient)
    assert clinical.SCORE_MIN <= payload["score"] <= clinical.SCORE_MAX


def test_the_components_are_reported_in_the_constants_file_order(db, patient):
    payload = safety_score.compute(db, patient)
    assert [c["key"] for c in payload["components"]] == [
        c.key for c in clinical.SAFETY_COMPONENTS
    ]


# --------------------------------------------------------------------------
# The recorded drop rule
# --------------------------------------------------------------------------


def _store(db, patient, score: int, when):
    row = SafetyScore(
        patient_id=patient.id,
        score=score,
        band=clinical.band_for(score).key,
        window_days=clinical.SAFETY_WINDOW_DAYS,
        covered_weight=clinical.SCORE_MAX,
        calculated_at=when,
    )
    row.components = []
    db.add(row)
    db.flush()
    return row


def test_a_ten_point_drop_in_thirty_days_raises_an_alert(db, patient):
    """RECORDED. The 10 and the 30 are literals here on purpose."""
    old = now() - timedelta(days=clinical.SAFETY_DROP_WINDOW_DAYS + 1)
    live = safety_score.compute(db, patient)["score"]
    _store(db, patient, live + 10, old)

    before = len(db.scalars(select(Alert).where(Alert.patient_id == patient.id)).all())
    row = safety_score.record(db, patient)
    after = db.scalars(
        select(Alert).where(Alert.patient_id == patient.id, Alert.alert_type == "safety_score_drop")
    ).all()

    assert row.delta <= -10
    assert len(after) == 1
    assert len(db.scalars(select(Alert).where(Alert.patient_id == patient.id)).all()) == before + 1


def test_a_drop_smaller_than_the_rule_raises_nothing(db, patient):
    old = now() - timedelta(days=clinical.SAFETY_DROP_WINDOW_DAYS + 1)
    live = safety_score.compute(db, patient)["score"]
    _store(db, patient, live + clinical.SAFETY_DROP_POINTS - 1, old)

    safety_score.record(db, patient)
    assert not db.scalars(
        select(Alert).where(Alert.patient_id == patient.id, Alert.alert_type == "safety_score_drop")
    ).all()


def test_a_recent_score_is_not_used_as_the_comparison(db, patient):
    """The rule is "in 30 days". Comparing with yesterday would fire on noise."""
    live = safety_score.compute(db, patient)["score"]
    _store(db, patient, live + 40, now() - timedelta(days=1))

    row = safety_score.record(db, patient)
    assert row.previous_score is None
    assert row.delta is None


def test_the_drop_alert_goes_through_alert_service(db, patient):
    """Nothing outside `alert_service` may build an `Alert` row — the Phase 5
    seed's exact alert count depends on it, and so does the family ever hearing."""
    old = now() - timedelta(days=clinical.SAFETY_DROP_WINDOW_DAYS + 1)
    _store(db, patient, safety_score.compute(db, patient)["score"] + 30, old)
    safety_score.record(db, patient)
    db.flush()  # the session is autoflush=False; the router commits

    alert = db.scalar(
        select(Alert).where(Alert.patient_id == patient.id, Alert.alert_type == "safety_score_drop")
    )
    assert alert is not None
    # The observable consequence of going through `alert_service`: the family
    # was notified. A hand-built `Alert` row would be silent.
    recipients = db.scalars(
        select(Notification.user_id).where(Notification.alert_id == alert.id)
    ).all()
    assert patient.family_user_id in recipients


# --------------------------------------------------------------------------
# It is read by families, so Phase 6's vocabulary rule applies
# --------------------------------------------------------------------------


def test_no_component_detail_uses_clinical_vocabulary(db, patient):
    """A new family-facing surface must not be where "systolic" comes back."""
    payload = safety_score.compute(db, patient)
    for component in payload["components"]:
        for text in (component["label"], component["blurb"], component["detail"]):
            assert summary_service.contains_clinical_language(text) is None, text


def test_every_band_blurb_is_family_safe():
    for band in clinical.SAFETY_BANDS:
        assert summary_service.contains_clinical_language(band.label) is None
        assert summary_service.contains_clinical_language(band.blurb) is None


def test_the_drop_alert_message_is_readable_by_a_family(db, patient):
    old = now() - timedelta(days=clinical.SAFETY_DROP_WINDOW_DAYS + 1)
    _store(db, patient, safety_score.compute(db, patient)["score"] + 30, old)
    safety_score.record(db, patient)
    alert = db.scalar(
        select(Alert).where(Alert.patient_id == patient.id, Alert.alert_type == "safety_score_drop")
    )
    assert summary_service.contains_clinical_language(alert.message) is None


# --------------------------------------------------------------------------
# Individual components
# --------------------------------------------------------------------------


def test_a_positive_mood_screen_lowers_the_mood_component(db, patient):
    screening = Screening(
        patient_id=patient.id,
        instrument=ScreeningInstrument.PHQ2,
        score=clinical.PHQ2_MAX_TOTAL,
        max_score=clinical.PHQ2_MAX_TOTAL,
        positive=True,
        administered_by=1,
        administered_at=now() - timedelta(days=1),
    )
    screening.answers = [clinical.PHQ2_MAX_PER_ITEM, clinical.PHQ2_MAX_PER_ITEM]
    db.add(screening)
    db.flush()

    mood = next(c for c in safety_score.compute(db, patient)["components"] if c["key"] == "mood")
    assert mood["has_data"] is True
    assert mood["value"] == 0.0
    assert mood["points"] == 0.0


def test_alert_burden_counts_absence_of_alerts_as_evidence(db, patient):
    """A quiet period is data. This component is never "no data"."""
    burden = next(
        c for c in safety_score.compute(db, patient)["components"] if c["key"] == "alert_burden"
    )
    assert burden["has_data"] is True


def test_no_connected_device_does_not_cost_points(db, patient):
    monitoring = next(
        c
        for c in safety_score.compute(db, patient)["components"]
        if c["key"] == "connected_monitoring"
    )
    assert monitoring["has_data"] is False
    assert monitoring["points"] is None


def test_readings_outside_range_lower_vital_stability(db, patient):
    before = next(
        c for c in safety_score.compute(db, patient)["components"] if c["key"] == "vital_stability"
    )
    for _ in range(10):
        db.add(
            Vital(
                patient_id=patient.id,
                **{**NORMAL_VITALS, "systolic_bp": 180},
                threshold_breached=True,
                recorded_at=now() - timedelta(days=1),
            )
        )
    db.flush()
    after = next(
        c for c in safety_score.compute(db, patient)["components"] if c["key"] == "vital_stability"
    )
    assert after["value"] < before["value"]


# --------------------------------------------------------------------------
# API surface
# --------------------------------------------------------------------------


def test_family_reads_the_score_with_its_full_breakdown(client, family_headers):
    response = client.get("/api/v1/patients/1/safety-score", headers=family_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True
    assert clinical.SCORE_MIN <= body["score"] <= clinical.SCORE_MAX
    assert len(body["components"]) == len(clinical.SAFETY_COMPONENTS)
    assert body["band_label"]


def test_another_familys_patient_is_a_404(client, other_family):
    headers = auth(login(client, other_family["email"]))
    assert client.get("/api/v1/patients/1/safety-score", headers=headers).status_code == 404


def test_only_an_admin_may_recalculate(client, family_headers, admin_headers):
    assert (
        client.post("/api/v1/patients/1/safety-score/recalculate", headers=family_headers).status_code
        == 403
    )
    response = client.post("/api/v1/patients/1/safety-score/recalculate", headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json()["score"] is not None


def test_history_is_oldest_first(client, admin_headers):
    for _ in range(2):
        client.post("/api/v1/patients/1/safety-score/recalculate", headers=admin_headers)
    response = client.get("/api/v1/patients/1/safety-score/history", headers=admin_headers)
    assert response.status_code == 200
    stamps = [point["calculated_at"] for point in response.json()]
    assert stamps == sorted(stamps)
