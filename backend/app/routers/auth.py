"""Authentication endpoints."""

from fastapi import APIRouter, Request

from ..config import settings
from ..core.dependencies import CurrentUser, DbSession
from ..core.ratelimit import FORGOT_PASSWORD_PER_EMAIL, FORGOT_PASSWORD_PER_IP, limiter
from ..schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ResetTokenStatus,
    UserOut,
)
from ..services import auth_service, password_reset_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Said to everyone, whether or not the address belongs to an account.
FORGOT_PASSWORD_MESSAGE = (
    "If that email is registered with DoorDoctor, a reset link is on its way. "
    "The link is valid for 30 minutes."
)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse, summary="Exchange demo credentials for a JWT")
def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    user = auth_service.authenticate(db, payload.email, payload.password)
    token = auth_service.issue_token(user)
    return LoginResponse(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="Current authenticated user")
def me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request a password reset link",
)
def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: DbSession
) -> ForgotPasswordResponse:
    """Always succeeds, so the response cannot be used to discover who has an account.

    Rate limiting is the exception, and it leaks nothing: the budget is spent by
    the request, not by whether an account was found.
    """
    ip = _client_ip(request)
    email_limit, email_window = FORGOT_PASSWORD_PER_EMAIL
    ip_limit, ip_window = FORGOT_PASSWORD_PER_IP
    limiter.check("forgot-password:ip", ip, limit=ip_limit, per_seconds=ip_window)
    limiter.check("forgot-password:email", payload.email, limit=email_limit, per_seconds=email_window)

    raw_token = password_reset_service.request_reset(db, email=payload.email, ip=ip)

    debug_url = (
        password_reset_service.reset_url(raw_token)
        if raw_token and settings.is_development
        else None
    )
    return ForgotPasswordResponse(message=FORGOT_PASSWORD_MESSAGE, debug_reset_url=debug_url)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Set a new password using a reset token",
)
def reset_password(
    payload: ResetPasswordRequest, request: Request, db: DbSession
) -> ResetPasswordResponse:
    ip_limit, ip_window = FORGOT_PASSWORD_PER_IP
    limiter.check("reset-password:ip", _client_ip(request), limit=ip_limit, per_seconds=ip_window)

    password_reset_service.reset_password(db, raw_token=payload.token, new_password=payload.password)
    return ResetPasswordResponse(message="Your password has been changed. You can sign in with it now.")


@router.get(
    "/reset-token/{token}/valid",
    response_model=ResetTokenStatus,
    summary="Check a reset token before showing the form",
)
def reset_token_valid(token: str, db: DbSession) -> ResetTokenStatus:
    return ResetTokenStatus(valid=password_reset_service.is_token_valid(db, token))
