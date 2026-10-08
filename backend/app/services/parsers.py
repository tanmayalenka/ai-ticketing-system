"""Parsers for pre-transcribed & diarized transcript files.

Normalizes JSON, SRT, and VTT into a common list of Segment objects.

Segment shape:
    {
        "id": "seg_0001",
        "speaker": "Agent",
        "start": 0.0,
        "end": 4.2,
        "text": "Hello..."
    }

Segment IDs are stable references the summarizer will cite later.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

SPEAKER_PREFIX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 _\-]{0,30}):\s+")


@dataclass
class Segment:
    id: str
    speaker: str
    start: float
    end: float
    text: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "speaker": self.speaker,
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }


def _parse_timestamp(ts: str) -> float:
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(parts[0])


def _extract_speaker(text: str) -> tuple[str | None, str]:
    m = SPEAKER_PREFIX_RE.match(text)
    if not m:
        return None, text
    speaker = m.group(1).strip()
    return speaker, text[m.end():].strip()


def _finalize(segments: list[Segment], source_format: str) -> tuple[list[Segment], dict]:
    # renumber IDs in case of skipped blocks
    for i, seg in enumerate(segments):
        seg.id = f"seg_{i + 1:04d}"
    metadata = {
        "source_format": source_format,
        "duration_seconds": segments[-1].end if segments else 0.0,
        "speakers": sorted({s.speaker for s in segments}),
        "segment_count": len(segments),
    }
    return segments, metadata


def parse_json(content: bytes) -> tuple[list[Segment], dict]:
    data = json.loads(content.decode("utf-8"))
    raw = data.get("segments") or data.get("utterances") or data.get("transcript") or []
    if not isinstance(raw, list):
        raise ValueError("JSON transcript must contain a 'segments' list")

    segments: list[Segment] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or item.get("content") or "").strip()
        if not text:
            continue
        speaker = item.get("speaker") or item.get("speaker_label") or item.get("role")
        if not speaker:
            speaker, text = _extract_speaker(text)
        segments.append(
            Segment(
                id="",  # assigned in _finalize
                speaker=speaker or "UNKNOWN",
                start=float(item.get("start", 0.0)),
                end=float(item.get("end", item.get("start", 0.0))),
                text=text,
            )
        )

    _, meta = _finalize(segments, "json")
    if data.get("call_id"):
        meta["call_id"] = data["call_id"]
    if data.get("duration"):
        meta["duration_seconds"] = float(data["duration"])
    return segments, meta


def _parse_cue_blocks(text: str) -> list[Segment]:
    blocks = re.split(r"\r?\n\r?\n", text.strip())
    segments: list[Segment] = []
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        timing_idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if timing_idx is None:
            continue
        start_s, end_s = [p.strip() for p in lines[timing_idx].split("-->", 1)]
        body = " ".join(l.strip() for l in lines[timing_idx + 1:]).strip()
        if not body:
            continue
        speaker, clean = _extract_speaker(body)
        segments.append(
            Segment(
                id="",
                speaker=speaker or "UNKNOWN",
                start=_parse_timestamp(start_s),
                end=_parse_timestamp(end_s),
                text=clean,
            )
        )
    return segments


def parse_srt(content: bytes) -> tuple[list[Segment], dict]:
    text = content.decode("utf-8", errors="replace")
    segments = _parse_cue_blocks(text)
    return _finalize(segments, "srt")


def parse_vtt(content: bytes) -> tuple[list[Segment], dict]:
    text = content.decode("utf-8", errors="replace")
    # strip WEBVTT header and any metadata before the first blank line
    text = re.sub(r"^WEBVTT.*?(\r?\n){2}", "", text, flags=re.DOTALL)
    segments = _parse_cue_blocks(text)
    return _finalize(segments, "vtt")


def parse_transcript(filename: str, content: bytes) -> tuple[list[Segment], dict]:
    name = filename.lower()
    if name.endswith(".json"):
        return parse_json(content)
    if name.endswith(".srt"):
        return parse_srt(content)
    if name.endswith(".vtt"):
        return parse_vtt(content)
    # fallback: try JSON, then SRT
    try:
        return parse_json(content)
    except Exception:
        return parse_srt(content)