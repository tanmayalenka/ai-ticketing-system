from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RedactedTranscript(Base):
    """Stores the PII-redacted version of a transcript.

    The redaction_manifest maps placeholders back to original values.
    In production this manifest would be encrypted at rest and access-logged.
    """

    __tablename__ = "redacted_transcripts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    transcript_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("transcripts.id"), unique=True, index=True
    )
    trace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    redacted_segments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    redaction_manifest: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    entities_detected: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )