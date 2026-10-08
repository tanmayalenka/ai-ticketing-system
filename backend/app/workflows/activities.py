import logging
from uuid import UUID

from sqlalchemy import select
from temporalio import activity

from app.db import SessionLocal
from app.models import (
    RedactedTranscript,
    Summary,
    Transcript,
    TranscriptChunk,
)
from app.services.chunking import chunk_segments
from app.services.redaction import redact_segments
from app.services.grounding import validate as validate_grounding
from app.services.summarization import PROMPT_VERSION, summarize
from app.config import settings

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

@activity.defn
async def summarize_call(transcript_id: str) -> dict:
    """Stage 5+6: multi-level summarization + grounding validation.

    Reads redacted transcript and chunks, calls Ollama, validates grounding,
    and persists one Summary row per transcript (idempotent replace).
    """
    logger.info("[summarize_call] transcript_id=%s", transcript_id)

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
                f"Redacted transcript missing for {transcript_id}; "
                "run redact_pii first"
            )

        chunk_rows = (
            db.execute(
                select(TranscriptChunk)
                .where(TranscriptChunk.transcript_id == transcript.id)
                .order_by(TranscriptChunk.chunk_index)
            )
            .scalars()
            .all()
        )
        if not chunk_rows:
            raise ValueError(
                f"No chunks for {transcript_id}; run chunk_transcript first"
            )

        chunks_for_llm = [
            {
                "chunk_index": c.chunk_index,
                "topic_label": c.topic_label,
                "segment_ids": c.segment_ids,
                "text": c.text,
            }
            for c in chunk_rows
        ]

        # --- LLM call ---
        try:
            result = summarize(chunks_for_llm)
        except Exception as exc:
            logger.exception("Summarization failed")
            transcript.status = "summarization_failed"
            db.commit()
            raise

        # --- Grounding validation ---
        report = validate_grounding(result, redacted.redacted_segments or [])

        # --- Persist (idempotent replace) ---
        existing = db.execute(
            select(Summary).where(Summary.transcript_id == transcript.id)
        ).scalar_one_or_none()

        payload = result.model_dump()
        if existing is None:
            existing = Summary(
                transcript_id=transcript.id,
                trace_id=transcript.trace_id,
                payload=payload,
                groundedness_score=report.groundedness_score,
                citation_validity=report.citation_validity,
                overall_pass=report.overall_pass,
                model_name=settings.ollama_model,
                prompt_version=PROMPT_VERSION,
            )
            db.add(existing)
        else:
            existing.payload = payload
            existing.groundedness_score = report.groundedness_score
            existing.citation_validity = report.citation_validity
            existing.overall_pass = report.overall_pass
            existing.model_name = settings.ollama_model
            existing.prompt_version = PROMPT_VERSION

        transcript.status = "summarized"
        db.commit()
        db.refresh(existing)

        return {
            "summary_id": str(existing.id),
            "groundedness_score": report.groundedness_score,
            "citation_validity": report.citation_validity,
            "overall_pass": report.overall_pass,
            "issue_count": len(result.issue_summaries),
            "action_item_count": len(result.action_items),
            "claim_count": len(report.claims),
        }