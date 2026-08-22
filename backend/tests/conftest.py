"""Test fixtures.

Each test runs against a throwaway copy of a freshly seeded demo database, so
tests never touch the developer database and never depend on each other.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="doordoctor-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'app.db'}"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["JWT_EXPIRE_MINUTES"] = "60"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import SMALL, seed  # noqa: E402

DEMO_PASSWORD = "Demo@123"
FAMILY_EMAIL = "family@doordoctor.in"
NURSE_EMAIL = "nurse@doordoctor.in"
ADMIN_EMAIL = "admin@doordoctor.in"

NORMAL_VITALS = {
    "systolic_bp": 130,
    "diastolic_bp": 80,
    "heart_rate": 82,
    "blood_glucose": 110,
    "spo2": 98,
    "temperature": 98.2,
    "weight": 64,
}

ABNORMAL_VITALS = {**NORMAL_VITALS, "systolic_bp": 148, "diastolic_bp": 92, "blood_glucose": 112, "spo2": 97}
SINGLE_BREACH_VITALS = {**NORMAL_VITALS, "systolic_bp": 148}


@pytest.fixture(autouse=True)
def clean_rate_limiter():
    """The rate limiter is process-global, so without this test order would
    decide test outcomes."""
    from app.core.ratelimit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(scope="session")
def template_db() -> Path:
    """A seeded database built once and copied per test.

    Seeded with `SMALL` — the demo core and its full billing history, and nothing
    else. These tests exercise the *application*, and they assert against it by
    hand (`total == 15` doses, `paid_months == 14`, `active_subscriptions == 4`).
    Rewriting them to tolerate 28 patients would weaken them for no gain, and
    copying a full-population database once per test would put megabytes of I/O
    between every assertion.

    `tests/test_seed.py` covers the `FULL` profile, once, on its own fixtures.
    """
    path = _TMP / "template.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        seed(db, SMALL)
    engine.dispose()
    return path


@pytest.fixture
def db_factory(template_db: Path, tmp_path: Path):
    db_path = tmp_path / "test.db"
    shutil.copy(template_db, db_path)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    engine.dispose()


@pytest.fixture
def db(db_factory) -> Session:
    session = db_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_factory) -> TestClient:
    def override_get_db():
        session = db_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def login(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def family_headers(client: TestClient) -> dict[str, str]:
    return auth(login(client, FAMILY_EMAIL))


@pytest.fixture
def nurse_headers(client: TestClient) -> dict[str, str]:
    return auth(login(client, NURSE_EMAIL))


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    return auth(login(client, ADMIN_EMAIL))


@pytest.fixture
def scheduled_visit_id(client: TestClient, nurse_headers: dict[str, str]) -> int:
    """Today's seeded visit, still in `scheduled` state."""
    response = client.get("/api/v1/visits/today", headers=nurse_headers)
    assert response.status_code == 200, response.text
    scheduled = [v for v in response.json() if v["status"] == "scheduled"]
    assert scheduled, "seed should leave at least one scheduled visit"
    return scheduled[0]["id"]


@pytest.fixture
def started_visit_id(client: TestClient, nurse_headers, scheduled_visit_id: int) -> int:
    response = client.post(f"/api/v1/visits/{scheduled_visit_id}/checkin", headers=nurse_headers)
    assert response.status_code == 200, response.text
    return scheduled_visit_id


@pytest.fixture
def other_family(db: Session):
    """A second family account with its own patient, used for isolation tests."""
    from app.core.security import hash_password
    from app.models import Patient, User, UserRole

    user = User(
        name="Other Family",
        email="other-family@doordoctor.in",
        phone="+91 90000 00009",
        password_hash=hash_password(DEMO_PASSWORD),
        role=UserRole.FAMILY,
    )
    db.add(user)
    db.flush()
    patient = Patient(
        name="Other Patient",
        age=71,
        gender="Male",
        address="Indiranagar, Bengaluru",
        family_user_id=user.id,
    )
    db.add(patient)
    db.commit()
    return {"email": user.email, "user_id": user.id, "patient_id": patient.id}
