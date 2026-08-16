"""
SmartAttend AI — FastAPI application entrypoint.

Phase 1: auth, database connectivity, RBAC, API foundation.
Phase 2: student management, face enrollment (CV pipeline).
Phase 3: attendance sessions, recognition-driven attendance marking,
liveness verification, integrity scoring, review center, audit trail.
Phase 9: multi-face recognition, calibration tooling.
Phase 10: retention enforcement background job (docs/retention.md).
"""

import asyncio
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Your existing imports continue below:
from services.face_service import get_face_analyzer
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config.settings import get_settings
from database.connection import close_mongo_connection, connect_to_mongo, get_database
from database.repositories.attendance_repository import AttendanceRepository
from database.repositories.audit_repository import AuditRepository
from database.repositories.policy_repository import PolicyRepository
from database.repositories.review_repository import ReviewRepository
from services.retention_service import RetentionService
from utils.exceptions import register_exception_handlers
from utils.logger import configure_logging, get_logger

# Import face service helper for model pre-loading
from services.face_service import get_face_analyzer

from api.routes import (
    analytics_routes,
    attendance_routes,
    auth_routes,
    class_routes,
    demo_routes,
    face_routes,
    health_routes,
    notification_routes,
    policy_routes,
    report_routes,
    review_routes,
    session_routes,
    student_routes,
    websocket_routes,
)

configure_logging()
logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

_retention_task: asyncio.Task | None = None
_warmup_task: asyncio.Task | None = None


async def _warmup_face_models_async() -> None:
    """
    Runs model downloading & ONNX loading in an executor thread during app startup.
    This prevents the first face recognition API call from timing out.
    """
    logger.info("Starting background warmup of InsightFace recognition models...")
    loop = asyncio.get_running_loop()
    try:
        # Run sync model initialization in a thread pool so it doesn't block FastAPI
        await loop.run_in_executor(None, get_face_analyzer)
        logger.info("Face recognition models successfully warmed up and loaded in memory.")
    except Exception as exc:
        logger.error("Failed to pre-load face recognition models: %s", exc)


async def _retention_background_loop() -> None:
    """
    Runs RetentionService.run_purge_cycle() on a fixed interval. The
    service itself is the actual safety gate (retention_enforcement_enabled
    must be True) — this loop just calls it periodically and never crashes
    the app if a single cycle fails.
    """
    settings = get_settings()
    interval_seconds = settings.RETENTION_CHECK_INTERVAL_HOURS * 3600

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            db = get_database()
            service = RetentionService(
                PolicyRepository(db), AttendanceRepository(db), ReviewRepository(db), AuditRepository(db)
            )
            result = await service.run_purge_cycle()
            logger.info("Scheduled retention cycle: %s", result)
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001 — a bad cycle must not kill the loop or the app
            logger.error("Retention background cycle failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _retention_task, _warmup_task
    settings = get_settings()

    if settings.is_production and settings.JWT_SECRET == "insecure-dev-secret-change-me":
        raise RuntimeError(
            "Refusing to start: JWT_SECRET is still the default dev value in a "
            "production environment. Set a real secret in .env."
        )

    logger.info("Starting %s (env=%s)...", settings.APP_NAME, settings.APP_ENV)
    try:
        await connect_to_mongo()
    except Exception as exc:
        logger.error(
            "Could not connect to MongoDB at startup: %s. "
            "Check MONGODB_URI in your .env and that MongoDB is running.",
            exc,
        )
        raise

    # 1. Trigger background model warmup task on startup
    _warmup_task = asyncio.create_task(_warmup_face_models_async())

    # 2. Start retention background loop
    _retention_task = asyncio.create_task(_retention_background_loop())

    yield

    logger.info("Shutting down %s...", settings.APP_NAME)
    if _retention_task:
        _retention_task.cancel()
    if _warmup_task and not _warmup_task.done():
        _warmup_task.cancel()
    await close_mongo_connection()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        description="AI-Powered Attendance Integrity & Intelligence Platform — API",
        version="1.0.0-phase9-10",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # API Routers
    app.include_router(health_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(student_routes.router)
    app.include_router(face_routes.router)
    app.include_router(session_routes.router)
    app.include_router(attendance_routes.router)
    app.include_router(review_routes.router)
    app.include_router(websocket_routes.router)
    app.include_router(analytics_routes.router)
    app.include_router(report_routes.router)
    app.include_router(policy_routes.router)
    app.include_router(class_routes.router)
    app.include_router(notification_routes.router)
    app.include_router(demo_routes.router)

    # Serve the frontend UI at both /app and root /
    if FRONTEND_DIR.exists():
        app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend_app")
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend_root")
    else:
        @app.get("/")
        def root_fallback():
            return JSONResponse(
                {
                    "status": "online",
                    "app": settings.APP_NAME,
                    "message": "Backend API is live. Frontend files not found in /frontend directory.",
                    "docs": "/docs",
                }
            )

    return app


app = create_app()