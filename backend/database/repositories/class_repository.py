from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models.class_model import ClassCreate, TimetableEntryCreate


class ClassRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["classes"]

    async def create(self, data: ClassCreate, teacher_id: str) -> dict:
        from datetime import datetime, timezone

        doc = {**data.model_dump(), "teacher_id": teacher_id, "created_at": datetime.now(timezone.utc)}
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def get_by_id(self, class_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(class_id)
        except (InvalidId, TypeError):
            return None
        return await self._collection.find_one({"_id": oid})

    async def list_all(self, limit: int = 100) -> list[dict]:
        cursor = self._collection.find().sort("subject", 1).limit(limit)
        return [doc async for doc in cursor]

    async def delete(self, class_id: str) -> bool:
        try:
            oid = ObjectId(class_id)
        except (InvalidId, TypeError):
            return False
        result = await self._collection.delete_one({"_id": oid})
        return result.deleted_count > 0


class TimetableRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["timetable_entries"]

    async def create(self, data: TimetableEntryCreate) -> dict:
        from datetime import datetime, timezone

        doc = {**data.model_dump(mode="json"), "created_at": datetime.now(timezone.utc)}
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def get_by_id(self, entry_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(entry_id)
        except (InvalidId, TypeError):
            return None
        return await self._collection.find_one({"_id": oid})

    async def list_all(self) -> list[dict]:
        cursor = self._collection.find().sort("day_of_week", 1)
        return [doc async for doc in cursor]

    async def delete(self, entry_id: str) -> bool:
        try:
            oid = ObjectId(entry_id)
        except (InvalidId, TypeError):
            return False
        result = await self._collection.delete_one({"_id": oid})
        return result.deleted_count > 0
