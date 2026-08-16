from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models.session_model import SessionCreate, SessionStatus


class SessionRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["attendance_sessions"]

    async def get_by_id(self, session_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(session_id)
        except (InvalidId, TypeError):
            return None
        return await self._collection.find_one({"_id": oid})

    async def create(self, data: SessionCreate, teacher_id: str) -> dict:
        now = datetime.now(timezone.utc)
        doc = {
            **data.model_dump(),
            "teacher_id": teacher_id,
            "status": SessionStatus.SCHEDULED.value,
            "start_time": None,
            "end_time": None,
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def set_status(
        self, session_id: str, status: SessionStatus, start_time=None, end_time=None
    ) -> Optional[dict]:
        try:
            oid = ObjectId(session_id)
        except (InvalidId, TypeError):
            return None

        updates: dict = {"status": status.value, "updated_at": datetime.now(timezone.utc)}
        if start_time is not None:
            updates["start_time"] = start_time
        if end_time is not None:
            updates["end_time"] = end_time

        await self._collection.update_one({"_id": oid}, {"$set": updates})
        return await self.get_by_id(session_id)

    async def list_sessions(
        self, status: Optional[SessionStatus] = None, skip: int = 0, limit: int = 50
    ) -> tuple[list[dict], int]:
        query: dict = {}
        if status:
            query["status"] = status.value
        total = await self._collection.count_documents(query)
        cursor = self._collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = [doc async for doc in cursor]
        return docs, total

    async def get_active_session(self) -> Optional[dict]:
        """
        MVP simplification: assumes a single active session at a time
        institution-wide (documented limitation — multi-classroom concurrent
        sessions are a scalability item, not a Phase 2/3 requirement).
        """
        return await self._collection.find_one({"status": SessionStatus.ACTIVE.value})
