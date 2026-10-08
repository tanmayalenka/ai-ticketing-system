"""Segment-aware topic chunking.

Stage 1 — Mechanical chunking:
    Greedily pack consecutive segments into blocks up to ~600 tokens,
    never splitting a segment. This preserves segment IDs for citation.

Stage 2 — Coherence refinement:
    Ask the LLM to label each block's topic and, if adjacent blocks share
    a topic, merge them. This is optional: if the LLM is unavailable we
    keep the mechanical chunks and set coherence_score=None.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.services.llm import structured_chat

logger = logging.getLogger(__name__)

TARGET_CHARS = 2400  # ~600 tokens at ~4 chars/token
MAX_CHARS = 3200


class _TopicAssignment(BaseModel):
    topic_label: str = Field(description="3-6 word topic label for this block")
    coherence: float = Field(
        ge=0.0, le=1.0, description="How internally coherent this block is"
    )
    merge_with_previous: bool = Field(
        default=False,
        description="True if this block should merge with the previous one",
    )


@dataclass
class Chunk:
    chunk_index: int
    topic_label: str | None
    text: str
    segment_ids: list[str]
    speakers: list[str]
    start_time: float
    end_time: float
    coherence_score: float | None


def _mechanical_chunks(segments: list[dict]) -> list[list[dict]]:
    blocks: list[list[dict]] = []
    current: list[dict] = []
    current_len = 0

    for seg in segments:
        text = seg.get("text", "")
        seg_len = len(text) + len(seg.get("speaker", "")) + 4
        if current and current_len + seg_len > MAX_CHARS:
            blocks.append(current)
            current = [seg]
            current_len = seg_len
        else:
            current.append(seg)
            current_len += seg_len
            if current_len >= TARGET_CHARS:
                blocks.append(current)
                current = []
                current_len = 0

    if current:
        blocks.append(current)
    return blocks


def _render_block(block: list[dict]) -> str:
    lines = []
    for seg in block:
        speaker = seg.get("speaker", "UNKNOWN")
        lines.append(f"{speaker}: {seg.get('text', '')}")
    return "\n".join(lines)


def _label_block(block_text: str) -> _TopicAssignment | None:
    try:
        chain = structured_chat(_TopicAssignment)
        prompt = (
            "You are analysing a diarized support call transcript. "
            "Given the following block of consecutive utterances, produce:\n"
            "1. A short topic label (3-6 words).\n"
            "2. A coherence score from 0 to 1 describing how tightly "
            "the block stays on one topic.\n"
            "3. Whether this block should be merged with the previous block "
            "(true only if it is a continuation of the same topic).\n\n"
            f"Block:\n{block_text}"
        )
        return chain.invoke(prompt)
    except Exception as exc:  # pragma: no cover
        logger.warning("Topic labelling failed: %s", exc)
        return None


def chunk_segments(segments: list[dict]) -> list[Chunk]:
    """Return topic-aware chunks from redacted segments."""
    if not segments:
        return []

    blocks = _mechanical_chunks(segments)
    labelled: list[tuple[list[dict], _TopicAssignment | None]] = []
    for block in blocks:
        assignment = _label_block(_render_block(block))
        labelled.append((block, assignment))

    # Merge blocks flagged as continuations of the previous topic.
    merged: list[tuple[list[dict], list[_TopicAssignment]]] = []
    for block, assignment in labelled:
        if (
                assignment is not None
                and assignment.merge_with_previous
                and merged
        ):
            prev_block, prev_assignments = merged[-1]
            merged[-1] = (prev_block + block, prev_assignments + [assignment])
        else:
            merged.append((block, [assignment] if assignment else []))

    chunks: list[Chunk] = []
    for i, (block, assignments) in enumerate(merged):
        seg_ids = [s["id"] for s in block]
        speakers = sorted({s.get("speaker", "UNKNOWN") for s in block})
        start = min(s.get("start", 0.0) for s in block)
        end = max(s.get("end", 0.0) for s in block)

        topic_label = None
        coherence = None
        if assignments:
            first = assignments[0]
            if first is not None:
                topic_label = first.topic_label
                coherence = round(
                    sum(a.coherence for a in assignments if a) / len(assignments),
                    3,
                    )

        chunks.append(
            Chunk(
                chunk_index=i,
                topic_label=topic_label,
                text=_render_block(block),
                segment_ids=seg_ids,
                speakers=speakers,
                start_time=start,
                end_time=end,
                coherence_score=coherence,
            )
        )

    return chunks