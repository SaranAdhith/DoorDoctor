"""Forgotten-password flow.

Two promises are asserted here beyond the happy path: the API never reveals
whether an address has an account, and a live reset link is never written to the
delivery log.
"""

from datetime import timedelta

from sqlalchemy import select

from app.database import now
from app.models import DeliveryLog, PasswordResetToken, User

from .conftest import DEMO_PASSWORD, FAMILY_EMAIL

NEW_PASSWORD = "Fresh@2026pass"

FORGOT = "/api/v1/auth/forgot-password"
RESET = "/api/v1/auth/reset-password"


def request_reset(client, email: str = FAMILY_EMAIL):
    response = client.post(FORGOT, json={"email": email})
    assert response.status_code == 200, response.text
    return response.json()


def token_from(client, email: str = FAMILY_EMAIL) -> str:
    body = request_reset(client, email)
    assert body["debug_reset_url"], "development builds return the link so the demo works offline"
    return body["debug_reset_url"].split("token=", 1)[1]


# --- happy path ---------------------------------------------------------------


def test_reset_lets_the_user_sign_in_with_the_new_password(client):
    token = token_from(client)

    response = client.post(RESET, json={"token": token, "password": NEW_PASSWORD})
    assert response.status_code == 200, response.text

    assert (
        client.post("/api/v1/auth/login", json={"email": FAMILY_EMAIL, "password": NEW_PASSWORD})
    ).status_code == 200


def test_the_old_password_stops_working(client):
    token = token_from(client)
    client.post(RESET, json={"token": token, "password": NEW_PASSWORD})

    response = client.post(
        "/api/v1/auth/login", json={"email": FAMILY_EMAIL, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 401


def test_email_is_matched_case_insensitively(client):
    body = request_reset(client, FAMILY_EMAIL.upper())
    assert body["debug_reset_url"]


# --- token lifecycle ----------------------------------------------------------


def test_a_token_cannot_be_used_twice(client):
    token = token_from(client)
    assert client.post(RESET, json={"token": token, "password": NEW_PASSWORD}).status_code == 200

    response = client.post(RESET, json={"token": token, "password": "Second@2026pass"})
    assert response.status_code == 400
    assert "invalid or has expired" in response.json()["detail"]


def test_an_expired_token_is_rejected(client, db):
    token = token_from(client)

    record = db.scalars(select(PasswordResetToken).order_by(PasswordResetToken.id.desc())).first()
    record.expires_at = now() - timedelta(minutes=1)
    db.commit()

    response = client.post(RESET, json={"token": token, "password": NEW_PASSWORD})
    assert response.status_code == 400


def test_requesting_again_invalidates_the_previous_link(client):
    first = token_from(client)
    second = token_from(client)
    assert first != second

    assert client.post(RESET, json={"token": first, "password": NEW_PASSWORD}).status_code == 400
    assert client.post(RESET, json={"token": second, "password": NEW_PASSWORD}).status_code == 200


def test_an_unknown_token_is_rejected(client):
    response = client.post(RESET, json={"token": "not-a-real-token", "password": NEW_PASSWORD})
    assert response.status_code == 400


def test_token_validity_can_be_checked_before_showing_the_form(client):
    token = token_from(client)
    assert client.get(f"/api/v1/auth/reset-token/{token}/valid").json() == {"valid": True}

    client.post(RESET, json={"token": token, "password": NEW_PASSWORD})
    assert client.get(f"/api/v1/auth/reset-token/{token}/valid").json() == {"valid": False}


def test_validity_check_on_an_unknown_token_is_false_not_an_error(client):
    response = client.get("/api/v1/auth/reset-token/made-up-token/valid")
    assert response.status_code == 200
    assert response.json() == {"valid": False}


# --- account enumeration ------------------------------------------------------


def test_an_unknown_email_gets_the_same_message_and_no_link(client):
    known = request_reset(client, FAMILY_EMAIL)
    unknown = request_reset(client, "nobody@doordoctor.in")

    assert known["message"] == unknown["message"]
    assert unknown["debug_reset_url"] is None


def test_an_unknown_email_creates_no_token(client, db):
    request_reset(client, "nobody@doordoctor.in")
    assert db.scalars(select(PasswordResetToken)).all() == []


def test_an_inactive_account_is_treated_like_an_unknown_one(client, db):
    user = db.scalar(select(User).where(User.email == FAMILY_EMAIL))
    user.is_active = False
    db.commit()

    body = request_reset(client, FAMILY_EMAIL)
    assert body["debug_reset_url"] is None
    assert db.scalars(select(PasswordResetToken)).all() == []


# --- password rules -----------------------------------------------------------


def test_a_short_password_is_rejected(client):
    token = token_from(client)
    response = client.post(RESET, json={"token": token, "password": "Ab1"})
    assert response.status_code == 422
    assert "at least 8 characters" in response.json()["detail"]


def test_a_password_without_a_number_is_rejected(client):
    token = token_from(client)
    response = client.post(RESET, json={"token": token, "password": "onlyletters"})
    assert response.status_code == 422
    assert "one number" in response.json()["detail"]


def test_a_password_without_a_letter_is_rejected(client):
    token = token_from(client)
    response = client.post(RESET, json={"token": token, "password": "12345678"})
    assert response.status_code == 422
    assert "one letter" in response.json()["detail"]


def test_a_rejected_password_leaves_the_token_usable(client):
    token = token_from(client)
    client.post(RESET, json={"token": token, "password": "short"})

    assert client.post(RESET, json={"token": token, "password": NEW_PASSWORD}).status_code == 200


# --- rate limiting ------------------------------------------------------------


def test_the_sixth_request_for_one_email_is_refused(client):
    for _ in range(5):
        assert client.post(FORGOT, json={"email": FAMILY_EMAIL}).status_code == 200

    response = client.post(FORGOT, json={"email": FAMILY_EMAIL})
    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_the_email_budget_is_per_address(client):
    for _ in range(5):
        client.post(FORGOT, json={"email": FAMILY_EMAIL})

    # A different address is still inside the 20/hour IP budget.
    assert client.post(FORGOT, json={"email": "nurse@doordoctor.in"}).status_code == 200


def test_the_ip_budget_caps_the_whole_flow(client):
    for index in range(20):
        assert client.post(FORGOT, json={"email": f"user{index}@doordoctor.in"}).status_code == 200

    assert client.post(FORGOT, json={"email": "user99@doordoctor.in"}).status_code == 429


# --- delivery -----------------------------------------------------------------


def test_the_reset_email_is_recorded(client, db):
    request_reset(client)

    record = db.scalars(select(DeliveryLog).order_by(DeliveryLog.id.desc())).first()
    assert record is not None
    assert record.channel.value == "email"
    assert record.recipient == FAMILY_EMAIL
    assert record.status.value == "simulated"


def test_the_delivery_log_never_holds_a_live_reset_link(client, db):
    token = token_from(client)

    bodies = " ".join(record.body for record in db.scalars(select(DeliveryLog)))
    assert token not in bodies
    assert "[redacted]" in bodies


def test_changing_the_password_notifies_the_account(client, db):
    token = token_from(client)
    client.post(RESET, json={"token": token, "password": NEW_PASSWORD})

    subjects = [record.subject for record in db.scalars(select(DeliveryLog))]
    assert "Your DoorDoctor password was changed" in subjects


def test_no_link_is_delivered_for_an_unknown_email(client, db):
    request_reset(client, "nobody@doordoctor.in")
    assert db.scalars(select(DeliveryLog)).all() == []
