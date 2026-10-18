from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    settings = get_settings()
    checks = {"database": False, "serviceBusConfigured": bool(settings.service_bus_connection_string)}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "checks": checks, "error": str(exc)}
    return {"status": "ok", "checks": checks}
