"""Uploaded files. One table for all of them.

RECORDED: uploads live under `backend/app/uploads/` and are **never served
statically**. One table means the authenticated fetch route, the size accounting
and the erasure sweep are written once rather than per feature.

The row holds the sha256 of the stored bytes as well as the path. Storage is
content-addressed, so two rows can legitimately point at one file — which is why
deleting a row must never delete a file without checking whether anything else
still references it. `attachment_service` is the only place that decides.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import AttachmentKind

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[AttachmentKind] = mapped_column(
        SAEnum(AttachmentKind, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    # Relative to the upload root, forward-slashed. Never a client-supplied name:
    # the original filename is a string somebody else chose and this path is
    # derived entirely from the bytes.
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(60), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    width: Mapped[Optional[int]] = mapped_column()
    height: Mapped[Optional[int]] = mapped_column()

    # Every attachment belongs to a patient, which is what makes the fetch route
    # able to reuse `authorize_patient` and the erasure able to find it.
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="attachments")
