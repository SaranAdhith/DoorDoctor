"""Nurse profiles, and the credentials a family is entitled to see.

Phase 10 (§4.10) makes the person at the door checkable. A credential is a
row with an issuing body, a number, an expiry and — when it is verified — a
named verifier and a date. `verification_status` cannot read `verified`
without both; anything else is a badge that means nothing.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import CredentialKind, NurseStatus, VerificationStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .user import User
    from .visit import Visit


class Nurse(Base):
    __tablename__ = "nurses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True, nullable=False)
    credential: Mapped[str] = mapped_column(String(50), nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, values_callable=lambda e: [m.value for m in e]),
        default=VerificationStatus.PENDING,
        nullable=False,
    )
    status: Mapped[NurseStatus] = mapped_column(
        SAEnum(NurseStatus, values_callable=lambda e: [m.value for m in e]),
        default=NurseStatus.ACTIVE,
        nullable=False,
    )
    zone: Mapped[Optional[str]] = mapped_column(String(60), index=True)

    # --- Phase 10, the family-facing profile (§4.10) ----------------------
    # None of this is required, and the profile renders honestly without it: a
    # nurse with no bio shows no bio rather than a placeholder sentence written
    # by the platform on their behalf.
    joined_on: Mapped[Optional[date]] = mapped_column(Date)
    languages: Mapped[Optional[str]] = mapped_column(String(120))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    years_experience: Mapped[Optional[int]] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    user: Mapped["User"] = relationship(back_populates="nurse_profile")
    visits: Mapped[list["Visit"]] = relationship(back_populates="nurse")
    credentials: Mapped[list["NurseCredential"]] = relationship(
        back_populates="nurse", cascade="all, delete-orphan", order_by="NurseCredential.id"
    )

    @property
    def verified_credentials(self) -> list["NurseCredential"]:
        return [c for c in self.credentials if c.is_verified]


class NurseCredential(Base):
    """One licence, qualification, check or course.

    Kept as rows rather than columns on `Nurse` because a nurse holds several,
    they expire independently, and "verified on 12 March by Priya" is the part a
    family actually wants — a boolean on the nurse could not carry it.
    """

    __tablename__ = "nurse_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    nurse_id: Mapped[int] = mapped_column(ForeignKey("nurses.id"), index=True, nullable=False)
    kind: Mapped[CredentialKind] = mapped_column(
        SAEnum(CredentialKind, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    issuing_body: Mapped[str] = mapped_column(String(120), nullable=False)
    # Shown to admins only. A family gets to know the licence is verified and by
    # whom; the registration number is the nurse's, not the customer's.
    registration_number: Mapped[Optional[str]] = mapped_column(String(60))
    issued_on: Mapped[Optional[date]] = mapped_column(Date)
    expires_on: Mapped[Optional[date]] = mapped_column(Date)

    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, values_callable=lambda e: [m.value for m in e]),
        default=VerificationStatus.PENDING,
        nullable=False,
    )
    verified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    verified_by_name: Mapped[Optional[str]] = mapped_column(String(120))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    note: Mapped[Optional[str]] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    nurse: Mapped["Nurse"] = relationship(back_populates="credentials")

    @property
    def is_verified(self) -> bool:
        """Verified means somebody checked it and left their name on the check.

        A `verified` status with no verifier and no date is what this property
        exists to refuse — `nurse_service` cannot produce one, and
        `test_nurse_profile.py` proves the projection agrees.
        """
        return (
            self.verification_status == VerificationStatus.VERIFIED
            and self.verified_at is not None
            and self.verified_by_name is not None
        )

    def is_expired(self, today: date) -> bool:
        return self.expires_on is not None and self.expires_on < today
