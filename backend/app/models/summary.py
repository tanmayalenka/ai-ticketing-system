from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Summary(Base):
    """Multi-level summary for a transcript.

    payload shape (matches app.services.summarization.MultiLevelSummary):
    {
      "call_summary": {
        "overview": str,
        "primary_issue": str,
        "resolution_status": "resolved" | "unresolved" | "follow_up_needed" | "unclear",
        "sentiment": "positive" | "neutral" | "negative" | "mixed",
        "citations": [seg_id, ...]
      },
      "issue_summaries": [
        {"chunk_index": int, "title": str, "description": str,
         "citations": [seg_id], "confidence": float}, ...
      ],
      "action_items": [
        {"description": str, "owner": str, "deadline": str | null,
         "citations": [seg_id]}, ...
      ]
    }
    """

    __tablename__ = "summaries"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    transcript_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    trace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    groundedness_score: Mapped[float] = mapped_column(Float, default=0.0)
    citation_validity: Mapped[float] = mapped_column(Float, default=0.0)
    overall_pass: Mapped[bool] = mapped_column(default=False)
    model_name: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16), default="v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )