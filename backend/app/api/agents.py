from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Agent, AgentSkill

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_to_dict(a: Agent, skills: list[AgentSkill]) -> dict:
    return {
        "id": str(a.id),
        "name": a.name,
        "email": a.email,
        "team": a.team,
        "status": a.status,
        "max_capacity": a.max_capacity,
        "current_load": a.current_load,
        "utilization": round(a.current_load / max(a.max_capacity, 1), 3),
        "last_assigned_at": a.last_assigned_at.isoformat()
        if a.last_assigned_at
        else None,
        "skills": [
            {"skill": s.skill, "proficiency": s.proficiency}
            for s in sorted(skills, key=lambda x: -x.proficiency)
        ],
    }


@router.get("")
async def list_agents(db: Session = Depends(get_db)) -> list[dict]:
    agents = db.execute(select(Agent).order_by(Agent.name)).scalars().all()
    if not agents:
        return []
    ids = [a.id for a in agents]
    skills = (
        db.execute(select(AgentSkill).where(AgentSkill.agent_id.in_(ids)))
        .scalars()
        .all()
    )
    by_agent: dict[str, list[AgentSkill]] = {}
    for s in skills:
        by_agent.setdefault(str(s.agent_id), []).append(s)
    return [_agent_to_dict(a, by_agent.get(str(a.id), [])) for a in agents]


@router.get("/workload")
async def agent_workload(db: Session = Depends(get_db)) -> dict:
    agents = db.execute(select(Agent)).scalars().all()
    by_team: dict[str, dict] = {}
    for a in agents:
        t = by_team.setdefault(
            a.team,
            {
                "team": a.team,
                "agent_count": 0,
                "online_count": 0,
                "total_capacity": 0,
                "total_load": 0,
            },
        )
        t["agent_count"] += 1
        if a.status == "online":
            t["online_count"] += 1
            t["total_capacity"] += a.max_capacity
            t["total_load"] += a.current_load

    for t in by_team.values():
        t["utilization"] = round(
            t["total_load"] / max(t["total_capacity"], 1), 3
        )

    return {
        "teams": sorted(by_team.values(), key=lambda x: x["team"]),
        "total_agents": len(agents),
        "online_agents": sum(1 for a in agents if a.status == "online"),
    }


@router.get("/{agent_id}")
async def get_agent(agent_id: UUID, db: Session = Depends(get_db)) -> dict:
    a = db.get(Agent, agent_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    skills = (
        db.execute(select(AgentSkill).where(AgentSkill.agent_id == a.id))
        .scalars()
        .all()
    )
    return _agent_to_dict(a, skills)