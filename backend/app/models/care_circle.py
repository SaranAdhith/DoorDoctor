"""The people around one patient (§4.13).

**This is the table Phase 11 extends, not a table Phase 11 duplicates.**
`user_id` is nullable on purpose. A care circle contains two kinds of people:

* those with a DoorDoctor login — today only the patient's `family_user`, and
  after Phase 11's invite flow, anyone they invite;
* those without one — the uncle in Bangalore who has the spare key, the
  neighbour who checks in on a Sunday. They have no account and never will, and
  they are frequently the most useful person to reach at 2am.

Phase 11's multi-family work is therefore *populate `user_id` and migrate
authorization onto this table*, not *build a second membership table beside it*.
The plan file called that table `PatientFamilyMember`; it is this one.

`Patient.family_user_id` stays authoritative as the primary contact and is
mirrored here as a primary member, so nothing in Phase 11 has to guess who was
first.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import CareCircleRole

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient


class CareCircleMember(Base):
    __tablename__ = "care_circle_members"
    # An email may appear once per patient. SQLite treats NULLs as distinct, so
    # the several members with no email address do not collide.
    __table_args__ = (UniqueConstraint("patient_id", "email", name="uq_circle_patient_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Free text, not an enum. "My mother's neighbour who has the spare key" is a
    # real and important member of a care circle and no enum was going to hold it.
    relationship_label: Mapped[str] = mapped_column(String(60), default="Family", nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(255))

    role: Mapped[CareCircleRole] = mapped_column(
        SAEnum(CareCircleRole, values_callable=lambda e: [m.value for m in e]),
        default=CareCircleRole.VIEWER,
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    receives_alerts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    receives_reports: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(255))

    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="care_circle")

    @property
    def is_reachable(self) -> bool:
        """Whether there is any way to actually contact this person.

        A circle member with `receives_alerts` and neither a phone nor an email
        is a promise the platform cannot keep, and the routing in Phase 10's
        notification stage records the attempt it could not make rather than
        pretending it reached them.
        """
        return bool(self.phone or self.email)
