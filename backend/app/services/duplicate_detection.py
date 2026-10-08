"""Detects whether a new call resembles an existing ticket.

Strategy:
  1. Embed the call summary text with nomic-embed-text.
  2. Query pgvector for the nearest existing ticket embeddings.
  3. Apply a two-threshold policy:
     - similarity >= HIGH_THRESHOLD: auto-link candidate
     - MEDIUM..HIGH: candidate for human review
     - < MEDIUM: create new
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TicketEmbedding
from app.services.llm import get_embedding_model

logger = logging.getLogger(__name__)

HIGH_THRESHOLD = 0.85
MEDIUM_THRESHOLD = 0.70
TOP_K = 5


@dataclass
class Candidate:
    ticket_id: str
    similarity: float
    title: str | None = None


def _summary_text(summary_payload: dict) -> str:
    cs = summary_payload.get("call_summary") or {}
    parts = [
        cs.get("primary_issue", ""),
        cs.get("overview", ""),
    ]
    for issue in summary_payload.get("issue_summaries") or []:
        parts.append(issue.get("title", ""))
        parts.append(issue.get("description", ""))
    return " ".join(p for p in parts if p).strip()


def detect_existing_tickets(
        db: Session, summary_payload: dict
) -> tuple[list[Candidate], str]:
    """Return (candidates, recommendation).

    recommendation is one of: "create_new" | "link_to_existing" | "needs_human_decision"
    """
    text = _summary_text(summary_payload)
    if not text:
        return [], "create_new"

    try:
        embedder = get_embedding_model()
        vec = embedder.embed_query(text)
    except Exception as exc:
        logger.warning("Embedding failed for duplicate detection: %s", exc)
        return [], "create_new"

    # pgvector cosine distance operator: <=>
    rows = db.execute(
        select(
            TicketEmbedding.ticket_id,
            (1 - TicketEmbedding.embedding.cosine_distance(vec)).label("similarity"),
        )
        .order_by(TicketEmbedding.embedding.cosine_distance(vec))
        .limit(TOP_K)
    ).all()

    candidates = [
        Candidate(ticket_id=str(r.ticket_id), similarity=round(float(r.similarity), 4))
        for r in rows
        if r.similarity is not None
    ]

    if not candidates:
        return [], "create_new"

    top = candidates[0].similarity
    if top >= HIGH_THRESHOLD:
        return candidates, "link_to_existing"
    if top >= MEDIUM_THRESHOLD:
        return candidates, "needs_human_decision"
    return candidates, "create_new"