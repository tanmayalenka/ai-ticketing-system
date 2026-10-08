from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Ticket
from app.schemas.ticket import TicketDetail, TicketSummary

router = APIRouter(prefix="/tickets", tags=["tickets"])


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