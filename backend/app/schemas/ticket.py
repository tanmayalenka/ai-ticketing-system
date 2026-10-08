from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TicketSummary(BaseModel):
    id: UUID
    title: str
    priority: str
    category: str | None
    status: str
    assigned_agent_id: UUID | None
    created_at: datetime


class TicketDetail(TicketSummary):
    description: str | None
    citations: list
    confidence_scores: dict