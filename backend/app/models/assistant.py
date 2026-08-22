"""Stored assistant exchanges (§2.3).

**Retention stance, decided deliberately with the founder on 2026-08-22 rather
than fallen into:**

A row here is a family member's question about a named relative, together with an
answer describing that relative's health. That is PHI-adjacent, and it is
protected by **access scoping, not redaction**.

Redaction is the wrong tool. Phase 3 redacts password-reset links before storing
them because a stored link *is* a live account takeover — the value is a
credential and the feature does not need it back. Nothing in this row is a
credential; the question and the answer *are* the feature, and redacting them
would destroy it while protecting nobody. What protects this data is that only
one person can ever read it:

* `GET /assistant/conversations` filters on `user_id == current_user.id`, full
  stop.
* **There is no route that lets an admin read another user's history**, and
  adding one is a consent decision rather than a convenience. An admin support
  tool that reads a daughter's questions about her mother needs consent language
  this build does not have.
* Question length is capped in the schema, so this table cannot become an
  unbounded free-text store.

Erasure is **deferred to Phase 10**, alongside the consent record, the
append-only audit log and the family Privacy & Data page with export and
deletion. Deleting rows here without those is a half-built promise.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import AssistantSource

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient
    from .user import User


class AssistantMessage(Base):
    """One question and the answer it received.

    One row per exchange rather than a conversation header plus messages: the
    assistant answers each question from a freshly built context pack and carries
    no dialogue state, so a thread would be a grouping the server does not
    actually use.
    """

    __tablename__ = "assistant_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    """The asker, and the only person who may ever read this row."""
    patient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patients.id"), index=True)
    """Nullable: account questions ("what have I paid?") and every admin question
    are not about one patient. Re-authorized on read rather than trusted."""
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(40), nullable=False)
    """The matched intent id. Stored so the `ASSUMED` catalogue can be evaluated
    against real questions when §2.3 finally arrives."""
    source: Mapped[AssistantSource] = mapped_column(
        SAEnum(AssistantSource, values_callable=lambda e: [m.value for m in e]),
        default=AssistantSource.DETERMINISTIC,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="assistant_messages")
    patient: Mapped[Optional["Patient"]] = relationship()
