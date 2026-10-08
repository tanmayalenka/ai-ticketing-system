import logging
from uuid import UUID

from sqlalchemy import select
from temporalio import activity

from app.db import SessionLocal
from app.models import RedactedTranscript, Transcript, TranscriptChunk
from app.services.chunking import chunk_segments
from app.services.redaction import redact_segments

logger = logging.getLogger(__name__)


@activity.defn
async def redact_pii(transcript_id: str) -> dict:
    """Stage 3: PII redaction.

    Input:  transcript_id (str UUID)
    Output: {transcript_id, redacted_transcript_id, entity_counts}
    """
    logger.info("[redact_pii] transcript_id=%s", transcript_id)
    with SessionLocal() as db:
        transcript = db.get(Transcript, UUID(transcript_id))
        if transcript is None:
            raise ValueError(f"Transcript {transcript_id} not found")

        result = redact_segments(transcript.segments or [])

        existing = db.execute(
            select(RedactedTranscript).where(
                RedactedTranscript.transcript_id == transcript.id
            )
        ).scalar_one_or_none()

        if existing is None:
            existing = RedactedTranscript(
                transcript_id=transcript.id,
                trace_id=transcript.trace_id,
                redacted_segments=result.redacted_segments,
                redaction_manifest=result.manifest,
                entities_detected=result.entity_counts,
            )
            db.add(existing)
        else:
            existing.redacted_segments = result.redacted_segments
            existing.redaction_manifest = result.manifest
            existing.entities_detected = result.entity_counts

        transcript.status = "redacted"
        db.commit()
        db.refresh(existing)

        return {
            "transcript_id": str(transcript.id),
            "redacted_transcript_id": str(existing.id),
            "entity_counts": result.entity_counts,
        }


@activity.defn
async def chunk_transcript(transcript_id: str) -> dict:
    """Stage 4: Topic-aware chunking.

    Reads the redacted transcript, produces topic chunks, persists them.
    Idempotent: replaces existing chunks for the same transcript.
    """
    logger.info("[chunk_transcript] transcript_id=%s", transcript_id)
    with SessionLocal() as db:
        transcript = db.get(Transcript, UUID(transcript_id))
        if transcript is None:
            raise ValueError(f"Transcript {transcript_id} not found")

        redacted = db.execute(
            select(RedactedTranscript).where(
                RedactedTranscript.transcript_id == transcript.id
            )
        ).scalar_one_or_none()
        if redacted is None:
            raise ValueError(
                f"Redacted transcript for {transcript_id} not found; run redact_pii first"
            )

        chunks = chunk_segments(redacted.redacted_segments or [])

        # Idempotency: delete existing chunks then insert fresh ones.
        db.query(TranscriptChunk).filter(
            TranscriptChunk.transcript_id == transcript.id
        ).delete()

        for c in chunks:
            db.add(
                TranscriptChunk(
                    transcript_id=transcript.id,
                    trace_id=transcript.trace_id,
                    chunk_index=c.chunk_index,
                    topic_label=c.topic_label,
                    text=c.text,
                    segment_ids=c.segment_ids,
                    speakers=c.speakers,
                    start_time=c.start_time,
                    end_time=c.end_time,
                    coherence_score=c.coherence_score,
                )
            )

        transcript.status = "chunked"
        db.commit()

        return {
            "transcript_id": str(transcript.id),
            "chunk_count": len(chunks),
            "topics": [c.topic_label for c in chunks],
        }