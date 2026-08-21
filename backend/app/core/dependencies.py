"""Reusable authentication / authorization dependencies.

Authorization is enforced here (and in the services) so the frontend never
decides what a user may see.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Caregiver, Patient, User, UserRole, Visit
from .exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    """Resolve the authenticated user from the bearer token."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError()

    claims = decode_access_token(credentials.credentials)
    if not claims or "sub" not in claims:
        raise UnauthorizedError("Invalid or expired token.")

    try:
        user_id = int(claims["sub"])
    except (TypeError, ValueError):
        raise UnauthorizedError("Invalid or expired token.") from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired token.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory restricting an endpoint to the given roles."""

    def _dependency(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise ForbiddenError()
        return current_user

    return _dependency


require_family = require_roles(UserRole.FAMILY)
require_caregiver = require_roles(UserRole.CAREGIVER)
require_coordinator = require_roles(UserRole.COORDINATOR)
require_family_or_coordinator = require_roles(UserRole.FAMILY, UserRole.COORDINATOR)

FamilyUser = Annotated[User, Depends(require_family)]
CaregiverUser = Annotated[User, Depends(require_caregiver)]
CoordinatorUser = Annotated[User, Depends(require_coordinator)]


def get_caregiver_profile(db: Session, user: User) -> Caregiver:
    """Caregiver profile for a caregiver user account."""
    caregiver = db.scalar(select(Caregiver).where(Caregiver.user_id == user.id))
    if caregiver is None:
        raise ForbiddenError("No caregiver profile is linked to this account.")
    return caregiver


def _caregiver_has_patient_access(db: Session, user: User, patient_id: int) -> bool:
    """A caregiver may read a patient only while assigned to one of their visits."""
    caregiver = db.scalar(select(Caregiver).where(Caregiver.user_id == user.id))
    if caregiver is None:
        return False
    visit = db.scalar(
        select(Visit.id).where(Visit.patient_id == patient_id, Visit.caregiver_id == caregiver.id)
    )
    return visit is not None


def authorize_patient(db: Session, user: User, patient_id: int) -> Patient:
    """Load a patient the user is allowed to see.

    A missing patient and someone else's patient both return 404 so the API never
    reveals that another family's record exists.
    """
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise NotFoundError("Patient not found.")

    if user.role == UserRole.COORDINATOR:
        return patient
    if user.role == UserRole.FAMILY and patient.family_user_id == user.id:
        return patient
    if user.role == UserRole.CAREGIVER and _caregiver_has_patient_access(db, user, patient_id):
        return patient

    raise NotFoundError("Patient not found.")


def authorize_visit(db: Session, user: User, visit_id: int) -> Visit:
    """Load a visit the user is allowed to see."""
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise NotFoundError("Visit not found.")

    if user.role == UserRole.COORDINATOR:
        return visit
    if user.role == UserRole.FAMILY:
        if visit.patient is not None and visit.patient.family_user_id == user.id:
            return visit
        raise NotFoundError("Visit not found.")
    if user.role == UserRole.CAREGIVER:
        caregiver = db.scalar(select(Caregiver).where(Caregiver.user_id == user.id))
        if caregiver is not None and visit.caregiver_id == caregiver.id:
            return visit
        raise NotFoundError("Visit not found.")

    raise NotFoundError("Visit not found.")


def authorize_caregiver_visit(db: Session, user: User, visit_id: int) -> tuple[Visit, Caregiver]:
    """Load a visit the caregiver owns, for write operations during the visit."""
    caregiver = get_caregiver_profile(db, user)
    visit = db.get(Visit, visit_id)
    if visit is None or visit.caregiver_id != caregiver.id:
        raise NotFoundError("Visit not found.")
    return visit, caregiver
