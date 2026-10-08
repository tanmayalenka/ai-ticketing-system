"""Multi-level summarization with strict citation requirements.

The output schema forces the LLM to attach segment IDs to every claim.
Downstream, the grounding validator (app.services.grounding) checks that
those citations are real and semantically support the claim text.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.services.llm import structured_chat

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"


# ---------- Output schema ----------

class CallSummary(BaseModel):
    overview: str = Field(
        description="3-5 sentence overview of the entire call."
    )
    primary_issue: str = Field(description="One-sentence primary issue.")
    resolution_status: Literal[
        "resolved", "unresolved", "follow_up_needed", "unclear"
    ] = Field(description="How the call ended from a resolution standpoint.")
    sentiment: Literal["positive", "neutral", "negative", "mixed"] = Field(
        description="Overall customer sentiment."
    )
    citations: list[str] = Field(
        min_length=1,
        description="Segment IDs (e.g. seg_0001) that support the overview.",
    )


class IssueSummary(BaseModel):
    chunk_index: int = Field(description="Index of the chunk this summarizes.")
    title: str = Field(description="Short title (<= 8 words).")
    description: str = Field(description="2-4 sentence grounded description.")
    citations: list[str] = Field(
        min_length=1, description="Segment IDs supporting this summary."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Self-reported confidence."
    )


class ActionItem(BaseModel):
    description: str = Field(description="Concrete next step or commitment.")
    owner: str = Field(
        description='Who owns it: "Agent", "Customer", or a named role.'
    )
    deadline: str | None = Field(
        default=None, description="Deadline if mentioned, else null."
    )
    citations: list[str] = Field(
        min_length=1, description="Segment IDs supporting this action item."
    )


class MultiLevelSummary(BaseModel):
    call_summary: CallSummary
    issue_summaries: list[IssueSummary] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)


# ---------- Prompt construction ----------

SYSTEM_PROMPT = """You are an expert support call analyst. You produce grounded, \
citation-backed summaries of customer support calls.

STRICT OUTPUT RULES:
1. Every factual claim MUST cite at least one segment ID.
2. Citation strings MUST use the exact format: seg_0001, seg_0002, seg_0010, etc.
   - Four-digit zero-padded number, prefix "seg_", underscore separator.
   - Do NOT use "1", "seg 1", "segment 1", or "#1".
   - Copy the IDs verbatim from the "segment_ids:" line of each chunk.
3. Only cite segment IDs that appear in the input below.
4. If information is not present in the transcript, write "not mentioned" rather than guessing.
5. Do not invent customer names, account numbers, dates, order IDs, or any detail not explicitly present.
6. primary_issue: one sentence. overview: 3-5 sentences.
7. Produce exactly one issue_summary per input chunk."""


def _render_chunks(chunks: list[dict]) -> str:
    """Render chunk rows into a compact, citation-friendly prompt block."""
    parts: list[str] = []
    for c in chunks:
        seg_ids = ", ".join(c["segment_ids"])
        parts.append(
            f"=== Chunk {c['chunk_index']} ===\n"
            f"topic: {c.get('topic_label') or 'unlabelled'}\n"
            f"segment_ids: {seg_ids}\n"
            f"---\n{c['text']}"
        )
    return "\n\n".join(parts)


def build_prompt(chunks: list[dict]) -> str:
    rendered = _render_chunks(chunks)
    example_ids = ", ".join(chunks[0]["segment_ids"][:3]) if chunks else "seg_0001, seg_0002"
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"VALID CITATION FORMAT EXAMPLE: \"citations\": [\"{example_ids.split(', ')[0]}\"]\n"
        f"(and only IDs that appear in the chunks below)\n\n"
        f"INPUT TRANSCRIPT CHUNKS:\n{rendered}\n\n"
        "Return JSON matching the required schema. Every citation must be a segment ID "
        "copied verbatim from the segment_ids line above."
    )


# ---------- Public entry point ----------

def summarize(chunks: list[dict]) -> MultiLevelSummary:
    """Run the summarization chain. Raises on LLM or schema failure."""
    if not chunks:
        raise ValueError("No chunks provided to summarize")

    prompt = build_prompt(chunks)
    chain = structured_chat(MultiLevelSummary)

    logger.info(
        "Summarizing %d chunk(s), prompt length=%d chars",
        len(chunks),
        len(prompt),
    )
    result: MultiLevelSummary = chain.invoke(prompt)
    return result