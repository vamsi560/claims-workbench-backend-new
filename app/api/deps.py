import secrets

from fastapi import Header, HTTPException

from app.config import get_settings


async def require_ingest_key(x_ingest_key: str | None = Header(default=None, alias="X-Ingest-Key")) -> None:
    expected = get_settings().ingest_api_key
    if not expected:
        return
    if not x_ingest_key or not secrets.compare_digest(x_ingest_key, expected):
        raise HTTPException(status_code=401, detail="Invalid ingest key")
