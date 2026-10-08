from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from temporalio.client import Client

from app.config import settings
from app.db import get_db
from app.models import Transcript, RedactedTranscript, TranscriptChunk, Summary
from app.schemas.transcript import (
    Segment,
    TranscriptDetail,
    TranscriptUploadResponse,
)
from app.services import storage
from app.services.parsers import parse_transcript
from app.workflows.transcript_workflow import TranscriptProcessingWorkflow

router = APIRouter(prefix="/transcripts", tags=["transcripts"])

MAX_BYTES = 25 * 1024 * 1024


async def _temporal_client() -> Client:
    return await Client.connect(
        settings.temporal_host, namespace=settings.temporal_namespace
    )

def _workflow_id(transcript_id: UUID, rerun: bool) -> str:
    """First run uses a stable ID; re-runs get a timestamp suffix.

    Temporal rejects starting a workflow with an ID that already completed,
    so re-runs need a distinct ID. The `transcript-{id}` prefix keeps them
    searchable in the Temporal UI.
    """
    base = f"transcript-{transcript_id}"
    return base if not rerun else f"{base}-rerun-{int(time.time() * 1000)}"


async def _start_workflow(transcript_id: UUID, rerun: bool) -> str:
    client = await _temporal_client()
    wf_id = _workflow_id(transcript_id, rerun)
    await client.start_workflow(
        TranscriptProcessingWorkflow.run,
        str(transcript_id),
        id=wf_id,
        task_queue=settings.temporal_task_queue,
    )
    return wf_id

@router.post("/upload", response_model=TranscriptUploadResponse)
async def upload_transcript(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
) -> TranscriptUploadResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_BYTES // (1024 * 1024)} MB)",
        )

    try:
        segments, meta = parse_transcript(file.filename or "upload.json", content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Parse error: {exc}") from exc

    if not segments:
        raise HTTPException(status_code=422, detail="No segments parsed from file")

    trace_id = uuid4()
    object_key = f"{trace_id}/{file.filename or 'transcript.json'}"

    try:
        storage.upload_bytes(
            object_key, content, content_type=file.content_type or "application/octet-stream"
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Storage error: {exc}") from exc

    transcript = Transcript(
        trace_id=trace_id,
        source_format=meta.get("source_format", "unknown"),
        original_filename=file.filename or "transcript.json",
        minio_object_key=object_key,
        segments=[s.to_dict() for s in segments],
        metadata_json=meta,
        status="uploaded",
    )
    db.add(transcript)
    db.commit()
    db.refresh(transcript)

    # Start the workflow. Failure to start is non-fatal; the upload is still persisted.
    try:
        wf_id = await _start_workflow(transcript.id, rerun=False)  # or rerun=True
        transcript.workflow_id = wf_id
        transcript.status = "processing"
        db.commit()
        status = "processing"
        message = "Transcript uploaded and workflow started"
    except Exception as exc:  # pragma: no cover - depends on Temporal availability
        transcript.status = "workflow_start_failed"
        db.commit()
        status = transcript.status
        message = f"Uploaded, but workflow did not start: {exc}"

    return TranscriptUploadResponse(
        transcript_id=transcript.id,
        trace_id=trace_id,
        status=status,
        message=message,
        segment_count=len(segments),
    )

@router.get("/by-trace/{trace_id}", response_model=TranscriptDetail)
async def get_transcript_by_trace(
        trace_id: UUID, db: Session = Depends(get_db)
) -> TranscriptDetail:
    t = db.execute(
        select(Transcript).where(Transcript.trace_id == trace_id)
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return TranscriptDetail(
        id=t.id,
        trace_id=t.trace_id,
        source_format=t.source_format,
        original_filename=t.original_filename,
        status=t.status,
        segments=[Segment(**s) for s in t.segments],
        metadata=t.metadata_json or {},
        created_at=t.created_at,
    )

@router.get("/{transcript_id}", response_model=TranscriptDetail)
async def get_transcript(
        transcript_id: UUID, db: Session = Depends(get_db)
) -> TranscriptDetail:
    t = db.get(Transcript, transcript_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return TranscriptDetail(
        id=t.id,
        trace_id=t.trace_id,
        source_format=t.source_format,
        original_filename=t.original_filename,
        status=t.status,
        segments=[Segment(**s) for s in t.segments],
        metadata=t.metadata_json or {},
        created_at=t.created_at,
    )

@router.get("/{transcript_id}/redacted")
async def get_redacted_transcript(
        transcript_id: UUID, db: Session = Depends(get_db)
) -> dict:
    """Return the redacted transcript (manifest is NOT exposed by default)."""
    t = db.get(Transcript, transcript_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Transcript not found")

    redacted = db.execute(
        select(RedactedTranscript).where(RedactedTranscript.transcript_id == t.id)
    ).scalar_one_or_none()
    if redacted is None:
        raise HTTPException(status_code=404, detail="Redacted transcript not ready")

    return {
        "transcript_id": str(t.id),
        "trace_id": str(t.trace_id),
        "segments": redacted.redacted_segments,
        "entities_detected": redacted.entities_detected,
    }


@router.get("/{transcript_id}/chunks")
async def get_transcript_chunks(
        transcript_id: UUID, db: Session = Depends(get_db)
) -> dict:
    """Return topic chunks for a transcript."""
    t = db.get(Transcript, transcript_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Transcript not found")

    rows = (
        db.execute(
            select(TranscriptChunk)
            .where(TranscriptChunk.transcript_id == t.id)
            .order_by(TranscriptChunk.chunk_index)
        )
        .scalars()
        .all()
    )
    return {
        "transcript_id": str(t.id),
        "trace_id": str(t.trace_id),
        "chunk_count": len(rows),
        "chunks": [
            {
                "chunk_index": c.chunk_index,
                "topic_label": c.topic_label,
                "text": c.text,
                "segment_ids": c.segment_ids,
                "speakers": c.speakers,
                "start_time": c.start_time,
                "end_time": c.end_time,
                "coherence_score": c.coherence_score,
            }
            for c in rows
        ],
    }


@router.get("/{transcript_id}/summary")
async def get_summary(
        transcript_id: UUID, db: Session = Depends(get_db)
) -> dict:
    t = db.get(Transcript, transcript_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Transcript not found")

    summary = db.execute(
        select(Summary).where(Summary.transcript_id == t.id)
    ).scalar_one_or_none()
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not ready")

    return {
        "transcript_id": str(t.id),
        "trace_id": str(t.trace_id),
        "payload": summary.payload,
        "groundedness_score": summary.groundedness_score,
        "citation_validity": summary.citation_validity,
        "overall_pass": summary.overall_pass,
        "model_name": summary.model_name,
        "prompt_version": summary.prompt_version,
        "created_at": summary.created_at.isoformat(),
    }