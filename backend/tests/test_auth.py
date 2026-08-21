"""Authentication behaviour."""

from .conftest import CAREGIVER_EMAIL, DEMO_PASSWORD, FAMILY_EMAIL, auth, login


def test_login_with_demo_credentials(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": FAMILY_EMAIL, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["role"] == "family"
    assert "password_hash" not in body["user"]


def test_login_is_case_insensitive_on_email(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": FAMILY_EMAIL.upper(), "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200


def test_login_with_wrong_password_is_rejected(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": FAMILY_EMAIL, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_with_unknown_email_gives_the_same_error(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@doordoc.demo", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_me_requires_a_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_rejects_an_invalid_token(client):
    response = client.get("/api/v1/auth/me", headers=auth("not-a-real-token"))
    assert response.status_code == 401


def test_me_rejects_an_expired_token(client):
    from app.core.security import create_access_token

    expired = create_access_token(subject=1, role="family", expires_minutes=-5)
    response = client.get("/api/v1/auth/me", headers=auth(expired))
    assert response.status_code == 401


def test_me_returns_the_authenticated_user(client):
    response = client.get("/api/v1/auth/me", headers=auth(login(client, CAREGIVER_EMAIL)))
    assert response.status_code == 200
    assert response.json()["email"] == CAREGIVER_EMAIL
    assert response.json()["role"] == "caregiver"


def test_health_endpoint(client):
    assert client.get("/health").json() == {"status": "ok"}
