from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from temporalio.client import Client

from app.config import settings
from app.db import get_db
from app.models import Ticket, TicketDraft, Transcript
from app.schemas.ticket import TicketDetail, TicketSummary

router = APIRouter(prefix="/tickets", tags=["tickets"])


# ---------- Existing list/get routes ----------

@router.get("", response_model=list[TicketSummary])
async def list_tickets(db: Session = Depends(get_db)) -> list[TicketSummary]:
    rows = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(200).all()
    return [TicketSummary.model_validate(t, from_attributes=True) for t in rows]


@router.get("/{ticket_id}", response_model=TicketDetail)
async def get_ticket(ticket_id: UUID, db: Session = Depends(get_db)) -> TicketDetail:
    t = db.get(Ticket, ticket_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketDetail.model_validate(t, from_attributes=True)


# ---------- Draft endpoints ----------

class ReviewDecision(BaseModel):
    reviewed_by: str = Field(default="agent", description="Agent identifier")
    reviewed_payload: dict | None = Field(
        default=None,
        description="Full edited draft payload. If null, use the AI draft as-is.",
    )
    reason: str | None = Field(default=None, description="Rejection reason.")


async def _temporal_client() -> Client:
    return await Client.connect(
        settings.temporal_host, namespace=settings.temporal_namespace
    )


def _draft_to_dict(d: TicketDraft) -> dict:
    return {
        "draft_id": str(d.id),
        "transcript_id": str(d.transcript_id),
        "trace_id": str(d.trace_id),
        "status": d.status,
        "payload": d.payload,
        "reviewed_payload": d.reviewed_payload,
        "duplicate_candidates": d.duplicate_candidates or [],
        "duplicate_recommendation": d.duplicate_recommendation,
        "review_notes": d.review_notes,
        "reviewed_by": d.reviewed_by,
        "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
        "model_name": d.model_name,
        "prompt_version": d.prompt_version,
        "created_at": d.created_at.isoformat(),
    }


@router.get("/drafts/by-trace/{trace_id}")
async def get_draft_by_trace(
        trace_id: UUID, db: Session = Depends(get_db)
) -> dict:
    d = db.execute(
        select(TicketDraft).where(TicketDraft.trace_id == trace_id)
    ).scalar_one_or_none()
    if d is None:
        raise HTTPException(status_code=404, detail="Draft not ready")
    return _draft_to_dict(d)


@router.get("/drafts/pending")
async def list_pending_drafts(db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.execute(
            select(TicketDraft)
            .where(TicketDraft.status == "pending")
            .order_by(TicketDraft.created_at.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )
    return [_draft_to_dict(d) for d in rows]


async def _signal(transcript: Transcript, payload: dict) -> None:
    if not transcript.workflow_id:
        raise HTTPException(
            status_code=409,
            detail="No active workflow for this transcript; cannot signal decision",
        )
    try:
        client = await _temporal_client()
        handle = client.get_workflow_handle(transcript.workflow_id)
        await handle.signal("agent_decision", payload)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Signal failed: {exc}"
        ) from exc


@router.post("/drafts/{trace_id}/approve")
async def approve_draft(
        trace_id: UUID,
        body: ReviewDecision = Body(...),
        db: Session = Depends(get_db),
) -> dict:
    transcript = db.execute(
        select(Transcript).where(Transcript.trace_id == trace_id)
    ).scalar_one_or_none()
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found")

    draft = db.execute(
        select(TicketDraft).where(TicketDraft.trace_id == trace_id)
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"Draft already {draft.status}"
        )

    # Snapshot the payload the agent approved (edited or as-is).
    approved = body.reviewed_payload or draft.payload
    draft.reviewed_payload = approved
    draft.reviewed_by = body.reviewed_by
    draft.reviewed_at = datetime.now(timezone.utc)
    # Keep status as 'pending' until the workflow confirms; the workflow's
    # activity will flip it to 'approved' durably.
    db.commit()

    await _signal(
        transcript,
        {
            "action": "approve",
            "reviewed_by": body.reviewed_by,
            "reviewed_payload": approved,
        },
    )
    return {"status": "approval_sent", "draft_id": str(draft.id)}


@router.post("/drafts/{trace_id}/reject")
async def reject_draft(
        trace_id: UUID,
        body: ReviewDecision = Body(...),
        db: Session = Depends(get_db),
) -> dict:
    transcript = db.execute(
        select(Transcript).where(Transcript.trace_id == trace_id)
    ).scalar_one_or_none()
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found")

    draft = db.execute(
        select(TicketDraft).where(TicketDraft.trace_id == trace_id)
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"Draft already {draft.status}"
        )

    await _signal(
        transcript,
        {
            "action": "reject",
            "reviewed_by": body.reviewed_by,
            "reason": body.reason or "",
        },
    )
    return {"status": "rejection_sent", "draft_id": str(draft.id)}