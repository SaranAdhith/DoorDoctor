"""Authentication request/response schemas."""

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import UserRole


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["family@doordoc.demo"])
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
