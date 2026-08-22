"""The FULL seed profile: the realistic dataset, and the demo it has to protect.

`tests/conftest.py` seeds `SMALL`, so every other test file runs against the
demo core alone. Nothing would otherwise notice if the wider population broke
the demo it exists to surround — and the ways it can are specific and quiet:
a second scheduled visit on Anitha's board silently points the alert tests at
another patient, an open alert on Lakshmi silently changes what her dashboard
says.

So this file builds the full dataset **once** and asserts the invariants that
the rest of the suite depends on but cannot see.
"""

from __future__ import annotations

import random
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import (
    Alert,
    AlertStatus,
    Lead,
    LeadKind,
    LeadStatus,
    MedicationLog,
    Notification,
    Nurse,
    Patient,
    User,
    UserRole,
    Visit,
    VisitStatus,
    Vital,
)
from app.seed import FULL, demo_reset, seed
from app.seed import demo_data, generators
from app.services import medication_service, vitals_service

from .conftest import ADMIN_EMAIL, FAMILY_EMAIL, NURSE_EMAIL, auth, login

_FULL_TMP = Path(tempfile.mkdtemp(prefix="doordoctor-fullseed-"))


# --------------------------------------------------------------------------
# Fixtures — one full seed for the whole module
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def full_template() -> Path:
    path = _FULL_TMP / "full.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        seed(session, FULL)
    engine.dispose()
    return path


@pytest.fixture
def full_factory(full_template: Path, tmp_path: Path):
    db_path = tmp_path / "full-copy.db"
    shutil.copy(full_template, db_path)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    engine.dispose()


@pytest.fixture
def full_db(full_factory) -> Session:
    session = full_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def full_client(full_factory) -> TestClient:
    def override_get_db():
        session = full_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------
# The invariants the rest of the suite depends on
# --------------------------------------------------------------------------


def test_the_demo_core_survives_the_population(full_db: Session):
    """Patient 1 and nurse 1 are still who every other test file thinks they are."""
    patient = full_db.get(Patient, 1)
    nurse = full_db.get(Nurse, 1)

    assert patient is not None and patient.name == "Lakshmi D'Souza"
    assert nurse is not None and nurse.user.email == NURSE_EMAIL
    assert patient.family_user.email == FAMILY_EMAIL


def test_the_demo_nurse_has_exactly_one_open_visit_today(full_client: TestClient):
    """`conftest.scheduled_visit_id` takes the first open visit on Anitha's board.

    A second scheduled visit today, or any unfinished visit from an earlier day,
    would point the whole alert suite at a different patient — and every one of
    those tests would still pass, against the wrong data.
    """
    headers = auth(login(full_client, NURSE_EMAIL))
    board = full_client.get("/api/v1/visits/today", headers=headers).json()

    scheduled = [visit for visit in board if visit["status"] == "scheduled"]
    assert len(scheduled) == 1, board
    assert scheduled[0]["patient"]["name"] == "Lakshmi D'Souza"


def test_the_demo_patient_carries_no_open_alert(full_db: Session):
    """Her dashboard must read `Stable` until the live demo raises 148/92."""
    open_alerts = full_db.scalars(
        select(Alert).where(Alert.patient_id == 1, Alert.status != AlertStatus.RESOLVED)
    ).all()
    assert open_alerts == []

    # She should still have history, or the family alerts page is empty.
    resolved = full_db.scalar(
        select(func.count(Alert.id)).where(Alert.patient_id == 1, Alert.status == AlertStatus.RESOLVED)
    )
    assert resolved >= 1


def test_the_demo_family_is_still_the_first_family_subscription(full_db: Session):
    """`test_seeded_history_earned_exactly_one_loyalty_reward` selects it by id order."""
    from app.models import Subscription

    first = full_db.scalar(
        select(Subscription).where(Subscription.family_user_id.is_not(None)).order_by(Subscription.id)
    )
    assert first.family_user.email == FAMILY_EMAIL
    assert first.paid_months == 14


def test_adherence_for_the_demo_patient_still_reads_87_percent(full_db: Session):
    assert medication_service.adherence_for_patient(full_db, 1)["percentage"] == 87


# --------------------------------------------------------------------------
# The population itself
# --------------------------------------------------------------------------


def test_the_roster_matches_the_specified_dataset(full_db: Session):
    """§2.4: 3 admins, 14 nurses, 28 patients, 18 families."""
    roles = Counter(role for (role,) in full_db.execute(select(User.role)))

    assert roles[UserRole.ADMIN] == 3
    assert roles[UserRole.NURSE] == 14
    assert roles[UserRole.FAMILY] == 18
    assert full_db.scalar(select(func.count(Patient.id))) == 28
    assert full_db.scalar(select(func.count(Nurse.id))) == 14


def test_patients_are_spread_across_six_bangalore_zones(full_db: Session):
    addresses = list(full_db.scalars(select(Patient.address)))
    for zone, _pincode in demo_data.ZONES:
        assert any(zone in address for address in addresses), f"no patient in {zone}"


def test_ninety_days_of_care_were_recorded(full_db: Session):
    """~1,400 visits over 90 days is the recorded §2.4 volume."""
    visits = full_db.scalar(select(func.count(Visit.id)))
    readings = full_db.scalar(select(func.count(Vital.id)))
    doses = full_db.scalar(select(func.count(MedicationLog.id)))

    assert 1_300 <= visits <= 1_600, visits
    assert readings > 1_000
    assert doses > 2_500


def test_every_patient_has_a_chart_worth_looking_at(full_db: Session):
    """A patient with no readings renders an empty dashboard, which reads as a bug."""
    for patient_id in full_db.scalars(select(Patient.id)):
        readings = full_db.scalar(
            select(func.count(Vital.id)).where(Vital.patient_id == patient_id)
        )
        assert readings >= 8, f"patient {patient_id} has only {readings} readings"


def test_a_visit_that_did_not_happen_is_recorded_as_such(full_db: Session):
    """An operations screen where every visit completed is not an operations screen."""
    statuses = Counter(status for (status,) in full_db.execute(select(Visit.status)))
    assert statuses[VisitStatus.MISSED] > 0
    assert statuses[VisitStatus.CANCELLED] > 0
    # ...but they stay rare enough to look like a real service.
    completed = statuses[VisitStatus.COMPLETED]
    assert (statuses[VisitStatus.MISSED] + statuses[VisitStatus.CANCELLED]) < completed * 0.1


def test_adherence_covers_the_recorded_range(full_db: Session):
    """§2.4 records 62-98%. Everyone above 90% gives an admin nothing to act on."""
    values = [
        medication_service.adherence_for_patient(full_db, patient_id)["percentage"]
        for patient_id in full_db.scalars(select(Patient.id))
    ]
    assert all(value is not None for value in values)
    assert min(values) <= 70
    assert max(values) >= 90
    assert generators.ADHERENCE_MIN <= min(values) <= max(values) <= generators.ADHERENCE_MAX


# --------------------------------------------------------------------------
# Alerts — raised by the real engine, thirty resolved and four open
# --------------------------------------------------------------------------


def test_the_alert_queue_has_thirty_resolved_and_four_open(full_db: Session):
    statuses = Counter(status for (status,) in full_db.execute(select(Alert.status)))
    assert statuses[AlertStatus.RESOLVED] == 30
    assert statuses[AlertStatus.ACTIVE] == 4


def test_every_out_of_range_reading_raised_an_alert(full_db: Session):
    """The seed never writes an Alert row — it puts a reading out of range and lets
    the threshold engine do what it does in production. So this holds for the same
    reason it holds in production, and would catch a reading that quietly drifted
    outside its range without anybody noticing."""
    alerted = set(full_db.scalars(select(Alert.vitals_id)))

    for vital in full_db.scalars(select(Vital)):
        thresholds = vitals_service.load_thresholds(full_db, vital.patient_id)
        breaches = vitals_service.evaluate_thresholds(vital, thresholds)
        if breaches:
            assert vital.id in alerted, (
                f"reading {vital.id} for patient {vital.patient_id} is outside its range "
                "and raised no alert"
            )
            assert vital.threshold_breached is True
        else:
            assert vital.id not in alerted


def test_resolved_alerts_took_a_believable_amount_of_time(full_db: Session):
    """An alert queue where everything closed instantly is not a demo of an SLA."""
    resolved = full_db.scalars(select(Alert).where(Alert.status == AlertStatus.RESOLVED)).all()

    for alert in resolved:
        assert alert.acknowledged_at is not None and alert.resolved_at is not None
        assert alert.acknowledged_by is not None
        assert alert.created_at <= alert.acknowledged_at <= alert.resolved_at
        minutes = (alert.resolved_at - alert.created_at).total_seconds() / 60
        assert 5 <= minutes <= 8 * 60, minutes


def test_only_the_open_alerts_are_still_asking_for_attention(full_db: Session):
    """Otherwise the bell opens on 136 unread items dated this morning."""
    admin = full_db.scalar(select(User).where(User.email == ADMIN_EMAIL))
    unread = full_db.scalars(
        select(Notification).where(Notification.user_id == admin.id, Notification.read.is_(False))
    ).all()

    assert len(unread) == 4
    for notification in unread:
        alert = full_db.get(Alert, notification.alert_id)
        assert alert.status == AlertStatus.ACTIVE


def test_the_alert_history_is_not_all_dated_today(full_db: Session):
    """`create_threshold_alert` stamps the real clock; the seed has to backdate it."""
    days = {alert.created_at.date() for alert in full_db.scalars(select(Alert))}
    assert len(days) > 10, days


# --------------------------------------------------------------------------
# Today's board — §2.4 specifies its exact shape
# --------------------------------------------------------------------------


def test_todays_board_is_six_scheduled_one_unassigned_one_in_progress(full_client: TestClient):
    headers = auth(login(full_client, ADMIN_EMAIL))
    board = full_client.get("/api/v1/visits/today", headers=headers).json()

    scheduled = [visit for visit in board if visit["status"] == "scheduled"]
    in_progress = [visit for visit in board if visit["status"] == "in_progress"]
    unassigned = [visit for visit in scheduled if visit["nurse_id"] is None]

    assert len(scheduled) == 6 + 1  # six assigned, plus the unassigned one
    assert len(unassigned) == 1
    assert len(in_progress) == 1
    assert len([v for v in board if v["status"] == "completed"]) >= 1


def test_the_operations_dashboard_agrees_with_the_board(full_client: TestClient):
    """The counts and the table are two reads of the same day; they must match."""
    headers = auth(login(full_client, ADMIN_EMAIL))
    summary = full_client.get("/api/v1/admin/summary", headers=headers).json()
    board = full_client.get("/api/v1/visits/today", headers=headers).json()

    assert summary["today_visits"] == len(board)
    assert summary["completed_today"] == len([v for v in board if v["status"] == "completed"])
    assert summary["active_alerts"] == 4
    assert summary["patients"] == 28


# --------------------------------------------------------------------------
# --demo-reset
# --------------------------------------------------------------------------


def test_demo_reset_rewinds_the_demo_path_and_nothing_else(full_client: TestClient, full_factory):
    """Run the live demo, then rewind it — without renumbering fourteen months of
    invoices, which is what a full re-seed would do."""
    nurse = auth(login(full_client, NURSE_EMAIL))
    admin = auth(login(full_client, ADMIN_EMAIL))

    before_invoices = len(full_client.get("/api/v1/invoices", headers=admin).json())
    before_patients = full_client.get("/api/v1/admin/summary", headers=admin).json()["patients"]

    visit_id = [v for v in full_client.get("/api/v1/visits/today", headers=nurse).json()
                if v["status"] == "scheduled"][0]["id"]
    full_client.post(f"/api/v1/visits/{visit_id}/checkin", headers=nurse)
    raised = full_client.post(
        f"/api/v1/visits/{visit_id}/vitals",
        json={"systolic_bp": 148, "diastolic_bp": 92, "heart_rate": 82,
              "blood_glucose": 112, "spo2": 97, "temperature": 98.2, "weight": 64},
        headers=nurse,
    )
    assert raised.status_code == 201
    assert full_client.get("/api/v1/admin/summary", headers=admin).json()["active_alerts"] == 5

    with full_factory() as session:
        changed = demo_reset(session)
    assert changed["alerts_removed"] == 1
    assert changed["readings_removed"] == 1

    summary = full_client.get("/api/v1/admin/summary", headers=admin).json()
    assert summary["active_alerts"] == 4, "the demo alert is gone"
    assert summary["patients"] == before_patients, "nobody was deleted"
    assert len(full_client.get("/api/v1/invoices", headers=admin).json()) == before_invoices

    board = [v for v in full_client.get("/api/v1/visits/today", headers=nurse).json()
             if v["status"] == "scheduled"]
    assert len(board) == 1
    assert board[0]["patient"]["name"] == "Lakshmi D'Souza"


# --------------------------------------------------------------------------
# The generators, directly — they are pure, so they can be
# --------------------------------------------------------------------------


def test_the_generators_are_deterministic():
    """A fixed seed that quietly is not fixed is worse than an honestly random one."""
    def run() -> list:
        rng = random.Random(demo_data.RANDOM_SEED + 4)
        baseline = generators.baseline_for(("Hypertension",), 74, rng)
        arc = generators.arc_for(("Hypertension",), rng)
        return [generators.reading(baseline, arc, step, 40, 1.0, rng) for step in range(40)]

    assert run() == run()


def test_a_trajectory_has_a_shape_rather_than_being_noise():
    """A drifting patient's last third must sit above their first third."""
    rng = random.Random(demo_data.RANDOM_SEED)
    baseline = generators.baseline_for(("Hypertension",), 76, rng)
    readings = [
        generators.reading(baseline, generators.ARC_DRIFTING, step, 45, 0.0, rng)
        for step in range(45)
    ]
    first = sum(r["systolic_bp"] for r in readings[:15]) / 15
    last = sum(r["systolic_bp"] for r in readings[-15:]) / 15
    assert last > first + 5, (first, last)


def test_generated_readings_are_clamped_inside_the_configured_range():
    """This is what makes the alert count exact — only an excursion can breach."""
    ranges = dict(vitals_service.DEFAULT_THRESHOLDS)
    rng = random.Random(demo_data.RANDOM_SEED + 9)
    baseline = generators.baseline_for(("Type 2 diabetes", "COPD"), 84, rng)

    for step in range(60):
        raw = generators.reading(baseline, generators.ARC_DRIFTING, step, 60, 2.0, rng)
        values = generators.clamp_inside(raw, ranges)
        for metric, value in values.items():
            low, high = ranges[metric]
            assert low < value < high, (metric, value, low, high)


def test_generated_readings_are_not_pinned_to_the_clamp():
    """The clamp must be a guard rail, not the shape of the chart.

    The first version of these amplitudes put 27% of systolic readings hard
    against the ceiling: the trajectory was there in the arithmetic and sheared
    off before it reached the database, and every hypertensive patient's chart
    drew a flat line. Baselines are now sized so a full swing fits inside the
    safe band, and this is what keeps them that way.
    """
    ranges = dict(vitals_service.DEFAULT_THRESHOLDS)
    profiles = [
        ("Hypertension",),
        ("Type 2 diabetes",),
        ("COPD",),
        ("Congestive heart failure",),
        ("Chronic kidney disease",),
        ("Hypertension", "Type 2 diabetes"),
        ("Anaemia",),
        ("Hypothyroidism",),
    ]

    pinned = 0
    total = 0
    for index, conditions in enumerate(profiles):
        rng = random.Random(demo_data.RANDOM_SEED + index)
        baseline = generators.baseline_for(conditions, 78, rng)
        for arc in generators.ARCS:
            for step in range(40):
                values = generators.clamp_inside(
                    generators.reading(baseline, arc, step, 40, float(index), rng), ranges
                )
                for metric, value in values.items():
                    if metric == "weight":
                        continue  # deliberately flat — a home scale is not noisy
                    low, high = ranges[metric]
                    total += 1
                    if abs(value - low) < 1 or abs(value - high) < 1:
                        pinned += 1

    assert pinned / total < 0.05, f"{pinned}/{total} readings sit against the clamp"


def test_a_hypertensive_patient_still_has_a_readable_chart():
    """Their baseline is closest to the ceiling, so they clip first."""
    ranges = dict(vitals_service.DEFAULT_THRESHOLDS)
    rng = random.Random(demo_data.RANDOM_SEED + 3)
    baseline = generators.baseline_for(("Hypertension",), 82, rng)

    readings = [
        generators.clamp_inside(
            generators.reading(baseline, generators.ARC_STABLE, step, 40, 0.5, rng), ranges
        )["systolic_bp"]
        for step in range(40)
    ]
    # A flat line is a chart nobody learns anything from.
    assert len(set(readings)) >= 8, sorted(set(readings))
    assert max(readings) < ranges["systolic_bp"][1] - 3


def test_the_adherence_plan_lands_on_its_target():
    """Exactly on target, not on target on average.

    A twelve-dose window can only express multiples of 8.3%, so the contract is
    the *count* — the closest whole number of doses to the target. At the sizes
    the seed actually produces the printed percentage follows to within a point.
    """
    for doses in (12, 45, 144, 301):
        for target in (62, 75, 87, 98):
            plan = generators.adherence_plan(doses, target)
            assert len(plan) == doses
            assert plan.count("administered") == round(doses * target / 100)
            if doses >= 45:
                achieved = round(plan.count("administered") / doses * 100)
                assert abs(achieved - target) <= 1, (doses, target, achieved)


def test_the_excursion_table_is_the_specified_thirty_four():
    active = [e for e in demo_data.EXCURSIONS if not e.resolved]
    assert len(demo_data.EXCURSIONS) == 34
    assert len(active) == 4
    assert all(e.patient_slot != 0 for e in active), "the demo patient must carry no open alert"
    assert set(e.kind for e in demo_data.EXCURSIONS) <= set(demo_data.EXCURSION_KINDS)


def test_every_excursion_actually_breaches_something():
    """An excursion inside the range would silently reduce the alert count."""
    ranges = dict(vitals_service.DEFAULT_THRESHOLDS)
    for kind, overrides in demo_data.EXCURSION_KINDS.items():
        breached = [
            metric for metric, value in overrides.items()
            if not ranges[metric][0] <= value <= ranges[metric][1]
        ]
        assert breached, f"excursion '{kind}' is inside every configured range"


# --------------------------------------------------------------------------
# Public enquiries (Phase 8)
# --------------------------------------------------------------------------


def test_the_full_profile_seeds_a_working_lead_queue(full_db: Session):
    """Admin -> Leads should demo a queue, not an inbox of six identical rows."""
    leads = list(full_db.scalars(select(Lead).order_by(Lead.created_at.desc())))

    assert len(leads) == len(demo_data.LEADS)
    # Every enquiry kind on the marketing site is represented.
    assert {lead.kind for lead in leads} >= {LeadKind.FAMILY, LeadKind.CORPORATE, LeadKind.INSTITUTION, LeadKind.NRI}
    # And the queue has been partly worked, so the status filter has something to filter.
    statuses = {lead.status for lead in leads}
    assert LeadStatus.NEW in statuses
    assert len(statuses) > 1


def test_a_worked_lead_records_who_worked_it_and_when(full_db: Session):
    worked = [lead for lead in full_db.scalars(select(Lead)) if lead.status != LeadStatus.NEW]

    assert worked, "the seeded queue should contain at least one worked enquiry"
    for lead in worked:
        assert lead.handled_by_user_id is not None
        assert lead.handled_at is not None
        # Worked after it arrived. A negative interval is the kind of thing a
        # backdating seed gets wrong and nothing else notices.
        assert lead.handled_at >= lead.created_at


def test_unworked_leads_carry_no_handler(full_db: Session):
    for lead in full_db.scalars(select(Lead).where(Lead.status == LeadStatus.NEW)):
        assert lead.handled_by_user_id is None
        assert lead.handled_at is None


def test_the_small_profile_seeds_no_leads(db: Session):
    """`SMALL` is what `tests/conftest.py` uses. `tests/test_leads.py` asserts
    exact counts against an empty queue, so a lead seeded here would break it."""
    assert db.scalar(select(func.count(Lead.id))) == 0
