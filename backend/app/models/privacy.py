"""Consent decisions and erasure requests (§4.14).

**Nothing here is ever updated in place.** Granting a consent is a row.
Withdrawing it is another row. The current position is the newest row for that
kind, and the history is the record — a status column overwritten on withdrawal
would destroy the only evidence that consent was ever given.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, now
from .enums import ConsentStatus, ErasureStatus


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    # Null for a consent about the account rather than about one patient.
    patient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patients.id"), index=True)
    # The key from `core.ops.CONSENT_KINDS`, stored as a plain string: consents
    # outlive the code that defined them, and a decision recorded under a kind
    # that has since been renamed still has to be readable.
    kind: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    # The policy version the person was shown. A consent to a document nobody
    # can identify is not a consent.
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[ConsentStatus] = mapped_column(
        SAEnum(ConsentStatus, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
    decided_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    decided_by_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    # Where the decision came from: "onboarding", "privacy_page", "seed".
    source: Mapped[str] = mapped_column(String(40), default="privacy_page", nullable=False)


class ErasureRequest(Base):
    """A family asking for a patient's record to be destroyed.

    Two steps on purpose — the family raises it, an admin executes it. It is
    irreversible and it destroys a named person's health record; one click by
    one member of a shared account is not a good design for that.
    """

    __tablename__ = "erasure_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    # Denormalised, because after execution the patient row no longer carries a
    # name and the queue still has to say whose record this was about.
    patient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    requested_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    requested_by_name: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[ErasureStatus] = mapped_column(
        SAEnum(ErasureStatus, values_callable=lambda e: [m.value for m in e]),
        default=ErasureStatus.REQUESTED,
        nullable=False,
    )
    decided_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    decided_by_name: Mapped[Optional[str]] = mapped_column(String(120))
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    decision_note: Mapped[Optional[str]] = mapped_column(Text)
    # What was actually destroyed, as a readable line per dataset. The proof
    # that the promise on the privacy page was kept.
    outcome: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
