"""Authentication request/response schemas."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.security import password_problem
from ..models.enums import UserRole


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["family@doordoctor.in"])
    password: str = Field(..., min_length=1, examples=["Demo@123"])


class UserOut(BaseModel):
    """Public user representation. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str | None = None
    role: UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., max_length=255, examples=["family@doordoctor.in"])


class ForgotPasswordResponse(BaseModel):
    """Deliberately identical whether or not the account exists."""

    message: str
    debug_reset_url: str | None = Field(
        default=None,
        description="Development only. Absent in every other environment.",
    )


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., examples=["NewPass@2026"])

    @field_validator("password")
    @classmethod
    def _strong_enough(cls, value: str) -> str:
        problem = password_problem(value)
        if problem:
            raise ValueError(problem)
        return value


class ResetPasswordResponse(BaseModel):
    message: str


class ResetTokenStatus(BaseModel):
    valid: bool
