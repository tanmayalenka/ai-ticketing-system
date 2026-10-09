from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    team: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="online", index=True)
    max_capacity: Mapped[int] = mapped_column(Integer, default=10)
    current_load: Mapped[int] = mapped_column(Integer, default=0)
    last_assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    skills: Mapped[list["AgentSkill"]] = relationship(
        "AgentSkill",
        back_populates="agent",
        cascade="all, delete-orphan",
    )


class AgentSkill(Base):
    __tablename__ = "agent_skills"
    __table_args__ = (
        UniqueConstraint("agent_id", "skill", name="uq_agent_skill"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),   # ← this was missing
        index=True,
        nullable=False,
    )
    skill: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    proficiency: Mapped[int] = mapped_column(Integer, default=3)

    agent: Mapped[Agent] = relationship("Agent", back_populates="skills")