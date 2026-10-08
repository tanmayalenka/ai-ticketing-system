from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TicketDraft(Base):
    """A pending ticket draft awaiting agent review.

    Lifecycle:
        pending  -> agent edits + approves -> approved (then submitted to tickets)
        pending  -> agent rejects           -> rejected (with reason)
        pending  -> workflow timeout        -> expired

    payload shape (see app.services.ticket_draft.TicketDraftSchema):
    {
      "title": str,
      "description": str,
      "priority": "low" | "medium" | "high" | "critical",
      "category": str,
      "suggested_team": str,
      "customer_impact": str | null,
      "citations": [str],
      "confidence": { "title": float, "priority": float, ... }
    }
    """

    __tablename__ = "ticket_drafts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    transcript_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    summary_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("summaries.id", ondelete="CASCADE")
    )
    trace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)

    # AI-produced draft
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Existing ticket detection result
    duplicate_candidates: Mapped[list] = mapped_column(JSON, default=list)
    duplicate_recommendation: Mapped[str] = mapped_column(
        String(32), default="create_new"
    )

    # Human-in-the-loop
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    reviewed_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    model_name: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16), default="v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )