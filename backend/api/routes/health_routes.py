"""
/api/health — used by ops, deployment platforms, and local sanity checks.
Deliberately unauthenticated and lightweight.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from database.connection import check_database_health

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/health")
async def health_check():
    db_ok = await check_database_health()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
