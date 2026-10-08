"""Grounding validation for LLM summaries.

Two checks:
  1. Citation validity — every cited segment ID must exist in the source.
  2. Semantic support — the claim text must be semantically close to the
     concatenated text of its cited segments (cosine similarity on
     nomic-embed-text embeddings).

Outputs a per-claim report and aggregate scores.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.services.llm import get_embedding_model
from app.services.summarization import MultiLevelSummary

logger = logging.getLogger(__name__)

# Tuned for nomic-embed-text on short claim vs. short segment text.
# Raise to be stricter, lower to be more permissive.
SEMANTIC_THRESHOLD = 0.55
GROUNDEDNESS_PASS_THRESHOLD = 0.60

_SEG_ID_RE = re.compile(r"(\d+)")

# Matches "seg_0003", "seg 3", "segment 3", "3", optionally followed by
# a colon or dash and free-form text (which we keep as the "reason").
_CITATION_RE = re.compile(
    r"""^\s*
    (?:\#|\[|\()*                     # optional leading punctuation
    (?:seg(?:ment)?[\s_]*)?           # optional "seg" / "segment" prefix
    (\d{1,6})                          # the numeric part
    (?:\]|\))?                         # optional trailing punctuation
    \s*(?:[:\-–—]\s*)?                 # optional separator
    (?P<reason>.*?)                    # optional reason text
    \s*$""",
    re.VERBOSE | re.IGNORECASE | re.DOTALL,
    )

@dataclass
class ClaimReport:
    kind: str               # "call_summary" | "issue_summary" | "action_item"
    label: str              # human-readable label for the UI
    citations: list[str]
    valid_citations: list[str]
    invalid_citations: list[str]
    semantic_score: float   # avg cosine similarity against cited segments
    passed: bool
    reasons: dict[str, str] = field(default_factory=dict)


@dataclass
class GroundingReport:
    citation_validity: float        # 0..1, fraction of valid citations overall
    groundedness_score: float       # 0..1, avg semantic score across claims
    overall_pass: bool
    claims: list[ClaimReport] = field(default_factory=list)


def _cosine(a: list[float], b: list[float]) -> float:
    # Embeddings from nomic-embed-text are already L2-normalized by Ollama,
    # but we normalize defensively.
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _normalize_citation(
        raw: str, valid_ids: set[str]
) -> tuple[str | None, str]:
    """Return (segment_id_or_None, reason_text).

    Accepts "seg_0003", "seg_0003: reason", "segment 3 - because ...", "3".
    """
    if not isinstance(raw, str):
        return None, ""

    match = _CITATION_RE.match(raw)
    if not match:
        return None, raw.strip()

    num = int(match.group(1))
    candidate = f"seg_{num:04d}"
    reason = (match.group("reason") or "").strip()

    if candidate in valid_ids:
        return candidate, reason
    return None, reason or raw.strip()


def _normalize_segment_id(raw: str, valid_ids: set[str]) -> str | None:
    """Best-effort normalization of a citation string to a real segment ID.

    Accepts:
        "seg_0001", "seg_1", "segment 1", "1", "#1", "[seg_0001]"
    Returns None if no match is found.
    """
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip().strip("[]()#").lower()

    # Exact match
    if cleaned in valid_ids:
        return cleaned

    # Extract the numeric part
    match = _SEG_ID_RE.search(cleaned)
    if not match:
        return None
    num = int(match.group(1))
    candidate = f"seg_{num:04d}"
    return candidate if candidate in valid_ids else None


def _evaluate_claim(
        kind: str,
        label: str,
        claim_text: str,
        citations: list[str],
        segment_map: dict[str, str],
        embedder,
) -> ClaimReport:
    valid_ids = set(segment_map.keys())

    valid: list[str] = []
    invalid: list[str] = []
    reasons: dict[str, str] = {}

    seen: set[str] = set()
    for raw in citations:
        sid, reason = _normalize_citation(raw, valid_ids)
        if sid is None:
            invalid.append(raw)
            continue
        if sid not in seen:
            seen.add(sid)
            valid.append(sid)
        if reason and sid not in reasons:
            reasons[sid] = reason

    if not valid:
        logger.warning(
            "Claim '%s' has no valid citations. Raw=%s Invalid=%s",
            label, citations, invalid,
        )
        return ClaimReport(
            kind=kind,
            label=label,
            citations=citations,
            valid_citations=[],
            invalid_citations=invalid or list(citations),
            semantic_score=0.0,
            passed=False,
            reasons={},
        )

    cited_text = " ".join(segment_map[c] for c in valid)
    try:
        claim_vec = embedder.embed_query(claim_text)
        cited_vec = embedder.embed_query(cited_text)
        score = _cosine(claim_vec, cited_vec)
    except Exception as exc:
        logger.exception("Embedding failed for claim '%s'", label)
        score = 0.0

    return ClaimReport(
        kind=kind,
        label=label,
        citations=citations,
        valid_citations=valid,
        invalid_citations=invalid,
        semantic_score=round(score, 4),
        passed=(score >= SEMANTIC_THRESHOLD and not invalid),
        reasons=reasons,
    )


def validate(
        summary: MultiLevelSummary, redacted_segments: list[dict]
) -> GroundingReport:
    """Run grounding validation against the redacted segments."""
    segment_map = {s["id"]: s["text"] for s in redacted_segments}
    embedder = get_embedding_model()

    claims: list[ClaimReport] = []

    cs = summary.call_summary
    claims.append(
        _evaluate_claim(
            "call_summary",
            "Call overview",
            f"{cs.primary_issue}. {cs.overview}",
            cs.citations,
            segment_map,
            embedder,
        )
    )

    for issue in summary.issue_summaries:
        claims.append(
            _evaluate_claim(
                "issue_summary",
                f"Issue: {issue.title}",
                f"{issue.title}. {issue.description}",
                issue.citations,
                segment_map,
                embedder,
            )
        )

    for item in summary.action_items:
        claims.append(
            _evaluate_claim(
                "action_item",
                f"Action: {item.description[:60]}",
                item.description,
                item.citations,
                segment_map,
                embedder,
            )
        )

    total_citations = sum(len(c.citations) for c in claims) or 1
    total_valid = sum(len(c.valid_citations) for c in claims)
    citation_validity = round(total_valid / total_citations, 4)

    groundedness = (
        round(sum(c.semantic_score for c in claims) / len(claims), 4)
        if claims else 0.0
    )

    logger.info(
        "Grounding: claims=%d valid_citations=%d/%d citation_validity=%.2f groundedness=%.2f",
        len(claims), total_valid, total_citations, citation_validity, groundedness,
    )

    return GroundingReport(
        citation_validity=citation_validity,
        groundedness_score=groundedness,
        overall_pass=(citation_validity == 1.0 and groundedness >= GROUNDEDNESS_PASS_THRESHOLD),
        claims=claims,
    )