"""Generates a structured ticket draft from grounded summaries."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.services.llm import structured_chat

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"

CATEGORIES = [
    "authentication",
    "billing",
    "technical_issue",
    "account_management",
    "feature_request",
    "how_to",
    "other",
]

PRIORITIES = ["low", "medium", "high", "critical"]


class TicketDraftSchema(BaseModel):
    title: str = Field(
        max_length=140,
        description="Concise, specific title (<= 12 words). Do not prefix with 'Issue:'.",
    )
    description: str = Field(
        description=(
            "Grounded problem statement followed by what was attempted and current "
            "status. 3-6 sentences. Every factual claim must trace to the summary."
        )
    )
    priority: Literal["low", "medium", "high", "critical"] = Field(
        description="Business impact. Use 'critical' only for outage or security."
    )
    category: str = Field(
        description=f"One of: {', '.join(CATEGORIES)}"
    )
    suggested_team: str = Field(
        description="Team best suited to handle this, e.g. 'Identity', 'Billing', 'Tier-1 Support'."
    )
    customer_impact: str | None = Field(
        default=None,
        description="One sentence on customer-facing impact, or null if unclear.",
    )
    citations: list[str] = Field(
        min_length=1,
        description="Segment IDs supporting the description. Use format 'seg_0001'.",
    )
    confidence: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Per-field self-assessed confidence between 0 and 1. Include keys: "
            "title, description, priority, category."
        ),
    )


SYSTEM_PROMPT = """You are a support operations assistant. Convert a call summary \
into a ticket draft for a support agent to review.

STRICT RULES:
1. The description MUST only contain facts from the summary. Do not invent.
2. Every citation MUST be a segment ID of the form "seg_0001" (four digits, zero-padded).
3. Choose the most specific category from the allowed list.
4. Priority reflects business impact, not customer emotion.
5. Title must be specific: "Cannot reset password after account lock" is good; "Login issue" is bad.
6. customer_impact must be a single sentence or null.
7. Fill the confidence map with values between 0 and 1 for keys:
   title, description, priority, category.
"""


def _render_summary(payload: dict) -> str:
    cs = payload.get("call_summary") or {}
    lines = [
        f"primary_issue: {cs.get('primary_issue', '')}",
        f"overview: {cs.get('overview', '')}",
        f"resolution_status: {cs.get('resolution_status', '')}",
        f"sentiment: {cs.get('sentiment', '')}",
        "",
        "issue_summaries:",
    ]
    for issue in payload.get("issue_summaries") or []:
        lines.append(
            f"- [chunk {issue.get('chunk_index')}] {issue.get('title')}: "
            f"{issue.get('description')}"
        )
        lines.append(f"  citations: {', '.join(issue.get('citations') or [])}")

    lines.append("")
    lines.append("action_items:")
    for item in payload.get("action_items") or []:
        lines.append(
            f"- {item.get('description')} (owner: {item.get('owner')}, "
            f"deadline: {item.get('deadline')})"
        )
        lines.append(f"  citations: {', '.join(item.get('citations') or [])}")

    return "\n".join(lines)


def build_prompt(summary_payload: dict, duplicate_candidates: list[dict]) -> str:
    dup_block = "None"
    if duplicate_candidates:
        dup_block = "\n".join(
            f"- ticket {c['ticket_id']} (similarity {c['similarity']:.2f})"
            for c in duplicate_candidates
        )
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"ALLOWED CATEGORIES: {', '.join(CATEGORIES)}\n\n"
        f"SUMMARY:\n{_render_summary(summary_payload)}\n\n"
        f"POSSIBLE DUPLICATE TICKETS (informational):\n{dup_block}\n\n"
        "Return JSON matching the required schema."
    )


def generate(
        summary_payload: dict, duplicate_candidates: list[dict]
) -> TicketDraftSchema:
    prompt = build_prompt(summary_payload, duplicate_candidates)
    chain = structured_chat(TicketDraftSchema)
    logger.info(
        "Generating ticket draft: summary chars=%d, dup candidates=%d",
        len(prompt),
        len(duplicate_candidates),
    )
    return chain.invoke(prompt)