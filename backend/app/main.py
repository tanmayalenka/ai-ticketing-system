from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, tickets, transcripts
from app.config import settings

app = FastAPI(title="AI Ticketing System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(transcripts.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")


@app.get("/")
async def root() -> dict:
    return {"service": "ai-ticketing", "status": "ok", "env": settings.app_env}