"""Seed sample agents with skills and capacity.

Run:  python -m app.seed_agents
"""

from app.db import SessionLocal
from app.models import Agent, AgentSkill

AGENTS = [
    {
        "name": "Priya Sharma",
        "email": "priya@example.com",
        "team": "Identity",
        "status": "online",
        "max_capacity": 8,
        "current_load": 2,
        "skills": {
            "authentication": 5,
            "identity": 5,
            "account": 4,
            "general_support": 4,
        },
    },
    {
        "name": "Marcus Chen",
        "email": "marcus@example.com",
        "team": "Billing",
        "status": "online",
        "max_capacity": 6,
        "current_load": 1,
        "skills": {
            "billing": 5,
            "payments": 4,
            "general_support": 3,
        },
    },
    {
        "name": "Sofia Patel",
        "email": "sofia@example.com",
        "team": "Tier-1 Support",
        "status": "online",
        "max_capacity": 12,
        "current_load": 5,
        "skills": {
            "general_support": 5,
            "troubleshooting": 4,
            "product": 3,
            "how_to": 4,
        },
    },
    {
        "name": "Daniel Okafor",
        "email": "daniel@example.com",
        "team": "Engineering",
        "status": "online",
        "max_capacity": 5,
        "current_load": 3,
        "skills": {
            "technical": 5,
            "troubleshooting": 5,
            "general_support": 3,
        },
    },
    {
        "name": "Emma Lopez",
        "email": "emma@example.com",
        "team": "Identity",
        "status": "offline",
        "max_capacity": 8,
        "current_load": 0,
        "skills": {
            "authentication": 4,
            "identity": 4,
            "general_support": 4,
        },
    },
]


def main() -> None:
    with SessionLocal() as db:
        existing = db.query(Agent).count()
        if existing > 0:
            print(f"Seed skipped ({existing} agents already present).")
            return
        for a in AGENTS:
            skills = a.pop("skills")
            agent = Agent(**a)
            db.add(agent)
            db.flush()
            for skill, prof in skills.items():
                db.add(
                    AgentSkill(
                        agent_id=agent.id, skill=skill, proficiency=prof
                    )
                )
        db.commit()
        print(f"Seeded {len(AGENTS)} agents with skills.")


if __name__ == "__main__":
    main()