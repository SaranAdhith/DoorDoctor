"""Uploaded medical documents and the text read from them (Phase 12, Layer 1).

A `Document` is the clinical meaning of an upload: whose it is, who handed it
over, what it is, and how far through the pipeline it has got. The bytes live in
an ordinary `Attachment`, so the authenticated fetch route, content addressing
and the erasure sweep are reused as they are rather than written a second time.

A `DocumentPage` is what one page said, and **how we know** — `text_layer`
(exact, from the PDF itself), `ocr` (an engine's reading, which can be wrong),
or `none` (nothing could read it). The method is stored on every page because
"the report says 5.6" means something different in each case.

Nothing on this table is a fact about the patient yet. Text becomes facts in
Stage 2, and facts become part of the record only when an admin verifies them.

Deliberately one-directional relationships: `Patient`, `Visit` and `User` are
not edited to point back here, so Phase 12 adds no line to an existing model.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import DocumentStatus, DocumentType, PageMethod, UserRole

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .attachment import Attachment
    from .patient import Patient
    from .user import User
    from .visit import Visit


def _values(enum_cls):
    return [member.value for member in enum_cls]


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    # Set for a nurse's upload, and only then: it is what ties a photograph of a
    # prescription to the visit, the check-in and the geofence verdict it was
    # taken under.
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visits.id"), index=True)
    attachment_id: Mapped[int] = mapped_column(ForeignKey("attachments.id"), nullable=False)

    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    uploader_role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, values_callable=_values), nullable=False
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    doc_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, values_callable=_values), default=DocumentType.UNKNOWN, nullable=False
    )
    #: The date printed on the document, once someone knows it. Not the upload date.
    document_date: Mapped[Optional[date]] = mapped_column(Date)

    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, values_callable=_values),
        default=DocumentStatus.UPLOADED,
        index=True,
        nullable=False,
    )
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    #: A reason a person can act on. Never page content, never an exception repr.
    error: Mapped[Optional[str]] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Written by Stage 2's verification; present from the start so the table
    # never needs a column added to it after databases exist.
    verified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    patient: Mapped["Patient"] = relationship()
    visit: Mapped[Optional["Visit"]] = relationship()
    attachment: Mapped["Attachment"] = relationship()
    uploader: Mapped[Optional["User"]] = relationship(foreign_keys=[uploaded_by])
    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentPage.page_no",
    )

    @property
    def is_pdf(self) -> bool:
        return self.attachment is not None and self.attachment.content_type == "application/pdf"


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_no", name="uq_document_page"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True, nullable=False)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based, as printed
    method: Mapped[PageMethod] = mapped_column(
        SAEnum(PageMethod, values_callable=_values), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: e.g. "pypdf" or "chandra-ocr-2". Which reader said this.
    engine: Mapped[Optional[str]] = mapped_column(String(60))
    elapsed_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="pages")
