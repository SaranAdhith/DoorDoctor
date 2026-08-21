"""Authentication endpoints."""

from fastapi import APIRouter

from ..core.dependencies import CurrentUser, DbSession
from ..schemas.auth import LoginRequest, LoginResponse, UserOut
from ..services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, summary="Exchange demo credentials for a JWT")
def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    user = auth_service.authenticate(db, payload.email, payload.password)
    token = auth_service.issue_token(user)
    return LoginResponse(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="Current authenticated user")
def me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)
