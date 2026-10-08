"""Rule-based + spaCy PII redaction.

Strategy:
  1. Regex pass for high-precision patterns (email, phone, SSN, credit card).
  2. spaCy NER pass (en_core_web_sm) for PERSON, GPE, LOC, ORG.
  3. Deterministic placeholder assignment: [NAME_1], [EMAIL_1], ...
     The same original value always maps to the same placeholder within
     a single transcript, so the LLM sees consistent references.
  4. A redaction manifest maps placeholder -> original for reversible
     access (stored separately, access-controlled).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

import spacy

# ---------- Regex patterns ----------

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)"
)
SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
CREDIT_CARD_RE = re.compile(
    r"(?<!\d)(?:\d[ -]?){13,16}\d(?!\d)"
)

# spaCy entity labels we redact
SPACY_PII_LABELS = {"PERSON", "GPE", "LOC", "ORG"}

# Placeholder type mapping
LABEL_TO_TYPE = {
    "PERSON": "NAME",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "ORG": "ORG",
    "EMAIL": "EMAIL",
    "PHONE": "PHONE",
    "SSN": "SSN",
    "CREDIT_CARD": "CREDIT_CARD",
}


@dataclass
class RedactionResult:
    redacted_segments: list[dict] = field(default_factory=list)
    manifest: dict[str, str] = field(default_factory=dict)
    entity_counts: dict[str, int] = field(default_factory=dict)


class _PlaceholderAssigner:
    """Assigns stable placeholders like [NAME_1], [EMAIL_2] within one run."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._value_to_placeholder: dict[tuple[str, str], str] = {}

    def assign(self, entity_type: str, original: str) -> str:
        key = (entity_type, original.lower().strip())
        if key in self._value_to_placeholder:
            return self._value_to_placeholder[key]
        self._counters[entity_type] += 1
        placeholder = f"[{entity_type}_{self._counters[entity_type]}]"
        self._value_to_placeholder[key] = placeholder
        return placeholder


def _load_spacy():
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        # Model not installed; fall back to regex-only redaction.
        return None


_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = _load_spacy()
    return _nlp


def _redact_text(text: str, assigner: _PlaceholderAssigner, manifest: dict, counts: dict) -> str:
    # 1. Regex pass (highest precision)
    def _regex_replace(pattern: re.Pattern, entity_type: str):
        nonlocal text
        for match in pattern.finditer(text):
            original = match.group(0)
            placeholder = assigner.assign(entity_type, original)
            manifest[placeholder] = original
            counts[entity_type] = counts.get(entity_type, 0) + 1
            text = text.replace(original, placeholder)
        return text

    text = _regex_replace(EMAIL_RE, "EMAIL")
    text = _regex_replace(PHONE_RE, "PHONE")
    text = _regex_replace(SSN_RE, "SSN")
    text = _regex_replace(CREDIT_CARD_RE, "CREDIT_CARD")

    # 2. spaCy NER pass
    nlp = _get_nlp()
    if nlp is not None:
        doc = nlp(text)
        # Collect entities sorted by start char descending so replacements
        # don't shift offsets for earlier entities.
        entities = sorted(
            (ent for ent in doc.ents if ent.label_ in SPACY_PII_LABELS),
            key=lambda e: e.start_char,
            reverse=True,
        )
        for ent in entities:
            entity_type = LABEL_TO_TYPE.get(ent.label_, "MISC")
            placeholder = assigner.assign(entity_type, ent.text)
            manifest[placeholder] = ent.text
            counts[entity_type] = counts.get(entity_type, 0) + 1
            text = text[: ent.start_char] + placeholder + text[ent.end_char :]

    return text


def redact_segments(segments: list[dict]) -> RedactionResult:
    """Redact a list of normalized segments.

    Each segment dict is expected to have at least: id, speaker, start, end, text.
    """
    assigner = _PlaceholderAssigner()
    manifest: dict[str, str] = {}
    counts: dict[str, int] = {}

    redacted: list[dict] = []
    for seg in segments:
        redacted_text = _redact_text(
            seg.get("text", ""), assigner, manifest, counts
        )
        redacted.append(
            {
                "id": seg["id"],
                "speaker": seg.get("speaker", "UNKNOWN"),
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "text": redacted_text,
            }
        )

    return RedactionResult(
        redacted_segments=redacted,
        manifest=manifest,
        entity_counts=counts,
    )