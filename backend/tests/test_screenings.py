"""PHQ-2 screening (§4.7).

PHQ-2 is a **published instrument**. Its two questions, its 0-3 scale, its 0-6
total and its cutoff of 3 are the instrument's, and are pinned as literals here
precisely so a later "reconciliation" of §4 cannot quietly change them.
"""

import pytest
from sqlalchemy import select

from app.core import clinical
from app.core.exceptions import BadRequestError
from app.models import Alert, FollowUpTask, Patient, TaskKind, TaskStatus
from app.services import screening_service

from .conftest import auth, login


def _record(client, headers, answers, patient_id=1):
    return client.post(
        f"/api/v1/patients/{patient_id}/screenings", json={"answers": answers}, headers=headers
    )


# --------------------------------------------------------------------------
# The instrument itself — literals, because they are not ours to change
# --------------------------------------------------------------------------


def test_phq2_has_two_questions_scored_zero_to_three():
    assert len(clinical.PHQ2_QUESTIONS) == 2
    assert [value for value, _ in clinical.PHQ2_ANSWERS] == [0, 1, 2, 3]


def test_the_total_runs_zero_to_six():
    assert clinical.PHQ2_MAX_TOTAL == 6


def test_the_validated_cutoff_is_three():
    """The instrument's, not the founder's. Reconciling §4 must not move it."""
    assert clinical.PHQ2_POSITIVE_CUTOFF == 3


def test_the_questions_are_the_published_wording():
    assert clinical.PHQ2_QUESTIONS == (
        "Little interest or pleasure in doing things",
        "Feeling down, depressed, or hopeless",
    )


def test_the_instrument_is_served_rather_than_hard_coded_in_the_client(client, nurse_headers):
    response = client.get("/api/v1/screenings/instruments/phq2", headers=nurse_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["questions"] == list(clinical.PHQ2_QUESTIONS)
    assert body["positive_cutoff"] == clinical.PHQ2_POSITIVE_CUTOFF
    assert body["max_total"] == clinical.PHQ2_MAX_TOTAL
    assert "not a diagnosis" in body["disclaimer"]


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answers,total,positive",
    [
        ([0, 0], 0, False),
        ([1, 1], 2, False),
        ([2, 1], 3, True),
        ([3, 0], 3, True),
        ([3, 3], 6, True),
    ],
)
def test_scoring_follows_the_instrument(answers, total, positive):
    assert screening_service.score_answers(answers) == (total, positive)


def test_the_wrong_number_of_answers_is_refused():
    with pytest.raises(BadRequestError):
        screening_service.score_answers([1])
    with pytest.raises(BadRequestError):
        screening_service.score_answers([1, 1, 1])


def test_an_answer_outside_the_scale_is_refused():
    with pytest.raises(BadRequestError):
        screening_service.score_answers([4, 0])
    with pytest.raises(BadRequestError):
        screening_service.score_answers([-1, 0])


# --------------------------------------------------------------------------
# The two answers are kept, not just the sum
# --------------------------------------------------------------------------


def test_both_answers_are_stored_not_only_the_total(client, nurse_headers):
    """A 3 made of (3, 0) is not the same clinical picture as one made of
    (1, 2). Storing the sum throws that away permanently."""
    body = _record(client, nurse_headers, [3, 0]).json()
    assert body["score"] == 3
    assert [a["value"] for a in body["answers"]] == [3, 0]
    assert [a["question"] for a in body["answers"]] == list(clinical.PHQ2_QUESTIONS)


def test_two_screens_with_the_same_total_are_distinguishable(client, nurse_headers):
    first = _record(client, nurse_headers, [3, 0]).json()
    second = _record(client, nurse_headers, [1, 2]).json()
    assert first["score"] == second["score"] == 3
    assert [a["value"] for a in first["answers"]] != [a["value"] for a in second["answers"]]


# --------------------------------------------------------------------------
# A positive screen makes a task, never an alert
# --------------------------------------------------------------------------


def test_a_positive_screen_opens_a_follow_up_task(client, nurse_headers, db):
    response = _record(client, nurse_headers, [2, 2])
    assert response.status_code == 201, response.text
    assert response.json()["positive"] is True

    tasks = db.scalars(
        select(FollowUpTask).where(FollowUpTask.kind == TaskKind.SCREENING_FOLLOW_UP)
    ).all()
    assert len(tasks) == 1
    assert tasks[0].status == TaskStatus.OPEN
    hours = (tasks[0].due_at - tasks[0].created_at).total_seconds() / 3600
    assert round(hours) == clinical.PHQ2_FOLLOW_UP_HOURS


def test_a_positive_screen_never_raises_an_alert(client, nurse_headers, db):
    """A low mood score is not a threshold breach, and dressing it as one would
    be a diagnosis this platform is not entitled to make."""
    before = len(db.scalars(select(Alert)).all())
    _record(client, nurse_headers, [3, 3])
    after = db.scalars(select(Alert)).all()
    assert len(after) == before
    assert not [a for a in after if "screen" in a.alert_type or "mood" in a.alert_type]


def test_a_negative_screen_opens_nothing(client, nurse_headers, db):
    assert _record(client, nurse_headers, [1, 1]).json()["positive"] is False
    assert not db.scalars(
        select(FollowUpTask).where(FollowUpTask.kind == TaskKind.SCREENING_FOLLOW_UP)
    ).all()


def test_the_task_says_plainly_that_it_is_a_screen_not_a_diagnosis(client, nurse_headers, db):
    _record(client, nurse_headers, [3, 3])
    task = db.scalar(
        select(FollowUpTask).where(FollowUpTask.kind == TaskKind.SCREENING_FOLLOW_UP)
    )
    assert "not a diagnosis" in task.detail


# --------------------------------------------------------------------------
# Cadence
# --------------------------------------------------------------------------


def test_a_patient_never_screened_is_due(db):
    assert screening_service.is_due(db, 1) is True


def test_a_patient_screened_today_is_not_due(client, nurse_headers, db):
    _record(client, nurse_headers, [0, 0])
    assert screening_service.is_due(db, 1) is False


def test_the_status_endpoint_reports_the_cadence_and_the_last_screen(client, nurse_headers):
    _record(client, nurse_headers, [1, 0])
    body = client.get("/api/v1/patients/1/screenings/status", headers=nurse_headers).json()
    assert body["due"] is False
    assert body["cadence_days"] == clinical.PHQ2_CADENCE_DAYS
    assert body["latest"]["score"] == 1


# --------------------------------------------------------------------------
# Access
# --------------------------------------------------------------------------


def test_a_family_cannot_self_administer_a_screening(client, family_headers):
    """The instrument's validity depends on it being asked, not filled in."""
    assert _record(client, family_headers, [0, 0]).status_code == 403


def test_a_family_can_read_the_history(client, nurse_headers, family_headers):
    _record(client, nurse_headers, [1, 1])
    response = client.get("/api/v1/patients/1/screenings", headers=family_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_a_nurse_records_it_during_a_visit(client, nurse_headers, started_visit_id):
    response = client.post(
        "/api/v1/patients/1/screenings",
        json={"answers": [1, 0], "visit_id": started_visit_id},
        headers=nurse_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["visit_id"] == started_visit_id


def test_another_familys_patient_cannot_be_screened(client, other_family, admin_headers, db):
    headers = auth(login(client, other_family["email"]))
    assert client.get("/api/v1/patients/1/screenings", headers=headers).status_code == 404


def test_the_score_feeds_the_safety_score_mood_component(client, nurse_headers, family_headers):
    """The two features are wired together, not two disconnected screens."""
    before = client.get("/api/v1/patients/1/safety-score", headers=family_headers).json()
    assert next(c for c in before["components"] if c["key"] == "mood")["has_data"] is False

    _record(client, nurse_headers, [0, 0])

    after = client.get("/api/v1/patients/1/safety-score", headers=family_headers).json()
    mood = next(c for c in after["components"] if c["key"] == "mood")
    assert mood["has_data"] is True
    assert mood["value"] == 1.0
