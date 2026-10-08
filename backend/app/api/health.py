import socket
from fastapi import APIRouter
import httpx
from app.config import settings

router = APIRouter(tags=["health"])

def _tcp_check(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

@router.get("/health")
async def health() -> dict:
    checks: dict[str, str] = {}

    # Postgres
    checks["postgres"] = "ok" if _tcp_check("localhost", 5432) else "unreachable"
    # Redis
    checks["redis"] = "ok" if _tcp_check("localhost", 6379) else "unreachable"
    # MinIO
    checks["minio"] = "ok" if _tcp_check("localhost", 9000) else "unreachable"
    # Temporal
    checks["temporal"] = "ok" if _tcp_check("localhost", 7233) else "unreachable"

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            checks["ollama"] = "ok" if r.status_code == 200 else f"error {r.status_code}"
    except Exception:
        checks["ollama"] = "unreachable"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}