"""Skills + workload aware ticket routing.

Algorithm (deterministic, auditable):
  1. Map ticket category -> required skills.
  2. Filter to eligible agents:
       - status == "online"
       - current_load < max_capacity
       - has at least one required skill with proficiency >= MIN_PROFICIENCY
  3. Score each eligible agent:
       skill_score    = sum(proficiency for required skills) /
                        (5 * len(required_skills))            # 0..1
       workload_score = 1 - (current_load / max_capacity)      # 0..1
       composite      = 0.65 * skill_score + 0.35 * workload_score
  4. Highest composite wins. Tie-break by lower current_load,
     then by earlier last_assigned_at (or None first).
  5. If no eligible agent exists, return team fallback and let a
     human triage the queue.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, AgentSkill, Ticket

logger = logging.getLogger(__name__)

MIN_PROFICIENCY = 3
SKILL_WEIGHT = 0.65
WORKLOAD_WEIGHT = 0.35

# Ticket category -> ordered list of skills that can resolve it.
# An agent needs at least MIN_PROFICIENCY in one of these to be eligible.
CATEGORY_TO_SKILLS: dict[str, list[str]] = {
    "authentication": ["authentication", "identity", "general_support"],
    "billing": ["billing", "payments", "general_support"],
    "technical_issue": ["technical", "troubleshooting", "general_support"],
    "account_management": ["identity", "account", "general_support"],
    "feature_request": ["product", "general_support"],
    "how_to": ["general_support", "product"],
    "other": ["general_support"],
}

DEFAULT_SKILLS = ["general_support"]


@dataclass
class Candidate:
    agent_id: str
    agent_name: str
    composite: float
    skill_score: float
    workload_score: float
    matched_skills: list[str] = field(default_factory=list)


@dataclass
class RoutingDecision:
    agent_id: str | None
    agent_name: str | None
    reason: str
    candidates: list[Candidate]


def _required_skills(category: str | None) -> list[str]:
    if not category:
        return DEFAULT_SKILLS
    return CATEGORY_TO_SKILLS.get(category, DEFAULT_SKILLS)


def _skill_score(
        agent_skills: dict[str, int], required: list[str]
) -> tuple[float, list[str]]:
    if not required:
        return 0.0, []
    total = 0
    matched: list[str] = []
    for skill in required:
        prof = agent_skills.get(skill, 0)
        if prof >= MIN_PROFICIENCY:
            matched.append(skill)
        total += prof
    return total / (5 * len(required)), matched


def route_ticket(db: Session, ticket: Ticket) -> RoutingDecision:
    required = _required_skills(ticket.category)
    logger.info(
        "Routing ticket %s (category=%s, required=%s)",
        ticket.id, ticket.category, required,
    )

    # Load eligible agents in one query.
    agents = (
        db.execute(
            select(Agent).where(
                Agent.status == "online",
                Agent.current_load < Agent.max_capacity,
                )
        )
        .scalars()
        .all()
    )
    if not agents:
        return RoutingDecision(
            agent_id=None,
            agent_name=None,
            reason="no_eligible_agents: all agents offline or at capacity",
            candidates=[],
        )

    agent_ids = [a.id for a in agents]
    skill_rows = (
        db.execute(
            select(AgentSkill).where(AgentSkill.agent_id.in_(agent_ids))
        )
        .scalars()
        .all()
    )
    skills_by_agent: dict[str, dict[str, int]] = {}
    for s in skill_rows:
        skills_by_agent.setdefault(str(s.agent_id), {})[s.skill] = s.proficiency

    candidates: list[Candidate] = []
    for agent in agents:
        agent_skills = skills_by_agent.get(str(agent.id), {})
        skill_score, matched = _skill_score(agent_skills, required)
        if not matched:
            continue
        workload_score = 1 - (agent.current_load / max(agent.max_capacity, 1))
        composite = (
                SKILL_WEIGHT * skill_score + WORKLOAD_WEIGHT * workload_score
        )
        candidates.append(
            Candidate(
                agent_id=str(agent.id),
                agent_name=agent.name,
                composite=round(composite, 4),
                skill_score=round(skill_score, 4),
                workload_score=round(workload_score, 4),
                matched_skills=matched,
            )
        )

    if not candidates:
        return RoutingDecision(
            agent_id=None,
            agent_name=None,
            reason=f"no_skill_match: no agent has proficiency >= {MIN_PROFICIENCY} in {required}",
            candidates=[],
        )

    # Sort: composite desc, then current_load asc, then last_assigned_at asc.
    load_by_id = {str(a.id): a.current_load for a in agents}
    last_by_id = {str(a.id): a.last_assigned_at for a in agents}

    def sort_key(c: Candidate):
        last = last_by_id.get(c.agent_id)
        # None (never assigned) sorts first.
        return (
            -c.composite,
            load_by_id.get(c.agent_id, 0),
            0 if last is None else 1,
            last or 0,
        )

    candidates.sort(key=sort_key)
    winner = candidates[0]

    reason = (
        f"composite={winner.composite:.3f} "
        f"(skill={winner.skill_score:.2f}, workload={winner.workload_score:.2f}); "
        f"matched={','.join(winner.matched_skills)}; "
        f"load={load_by_id.get(winner.agent_id, 0)}"
    )

    return RoutingDecision(
        agent_id=winner.agent_id,
        agent_name=winner.agent_name,
        reason=reason,
        candidates=candidates,
    )