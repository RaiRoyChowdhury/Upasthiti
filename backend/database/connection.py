"""
MongoDB connection management via Motor (async driver).

The rest of the app never imports motor directly — it goes through
get_database() so the underlying driver could be swapped later (e.g. for a
vector-search-capable setup) without touching services or routes.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


class MongoManager:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


mongo_manager = MongoManager()


async def connect_to_mongo() -> None:
    settings = get_settings()
    logger.info("Connecting to MongoDB database '%s'...", settings.MONGODB_DB_NAME)
    mongo_manager.client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=5000,
    )
    mongo_manager.db = mongo_manager.client[settings.MONGODB_DB_NAME]

    # Fail fast with a clear error rather than a silent, slow-to-diagnose hang.
    await mongo_manager.client.admin.command("ping")
    logger.info("MongoDB connection established.")

    await _ensure_indexes()


async def close_mongo_connection() -> None:
    if mongo_manager.client is not None:
        mongo_manager.client.close()
        logger.info("MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:
    if mongo_manager.db is None:
        raise RuntimeError(
            "Database is not initialized. connect_to_mongo() must run before use "
            "(this happens automatically on app startup)."
        )
    return mongo_manager.db


async def _ensure_indexes() -> None:
    """Create indexes that the app depends on for correctness (not just speed)."""
    db = mongo_manager.db
    assert db is not None
    await db["users"].create_index("email", unique=True)
    await db["students"].create_index("student_id", unique=True)
    await db["face_profiles"].create_index("student_id", unique=True)
    await db["attendance_sessions"].create_index("status")
    # Idempotent attendance marking: the DB-level guarantee, not just a
    # service-level check. See attendance_repository.py for the full rationale.
    await db["attendance_records"].create_index(
        [("student_id", 1), ("session_id", 1)], unique=True, name="uniq_student_session"
    )
    await db["review_events"].create_index("status")
    await db["audit_logs"].create_index([("entity_type", 1), ("entity_id", 1)])
    await db["policy"].create_index("_key", unique=True)
    await db["classes"].create_index([("class_name", 1), ("section", 1)])
    await db["timetable_entries"].create_index("class_id")
    await db["notifications"].create_index([("user_id", 1), ("read", 1)])
    logger.info("Database indexes ensured.")


async def check_database_health() -> bool:
    """Used by /api/health — returns True if the DB responds to a ping."""
    try:
        if mongo_manager.client is None:
            return False
        await mongo_manager.client.admin.command("ping")
        return True
    except Exception as exc:  # noqa: BLE001 — health check must never raise
        logger.warning("Database health check failed: %s", exc)
        return False
