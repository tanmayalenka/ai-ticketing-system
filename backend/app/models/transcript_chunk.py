from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TranscriptChunk(Base):
    """A topic-coherent chunk derived from the redacted transcript.

    Each chunk carries the list of source segment IDs it was built from,
    so downstream summarization can cite those segments directly.
    """

    __tablename__ = "transcript_chunks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    transcript_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("transcripts.id"), index=True
    )
    trace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    segment_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    speakers: Mapped[list] = mapped_column(JSON, default=list)
    start_time: Mapped[float] = mapped_column(nullable=False)
    end_time: Mapped[float] = mapped_column(nullable=False)
    coherence_score: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )