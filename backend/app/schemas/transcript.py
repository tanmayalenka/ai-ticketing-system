from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Segment(BaseModel):
    id: str
    speaker: str
    start: float
    end: float
    text: str


class TranscriptUploadResponse(BaseModel):
    transcript_id: UUID
    trace_id: UUID
    status: str
    message: str
    segment_count: int


class TranscriptDetail(BaseModel):
    id: UUID
    trace_id: UUID
    source_format: str
    original_filename: str
    status: str
    segments: list[Segment]
    metadata: dict
    created_at: datetime