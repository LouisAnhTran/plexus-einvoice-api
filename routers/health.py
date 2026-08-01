from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import settings
from db import get_conn

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Unauthenticated liveness probe."""
    db_ok = False
    try:
        conn = await get_conn()
        await conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    body = {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "storage": settings.database_path,
        "autoAdvanceSeconds": settings.auto_advance_seconds,
    }
    return JSONResponse(body, status_code=200 if db_ok else 503)
