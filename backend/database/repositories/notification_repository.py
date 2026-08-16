from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models.notification_model import NotificationInDB


class NotificationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["notifications"]

    async def create(self, notification: NotificationInDB) -> dict:
        doc = notification.model_dump(by_alias=True, exclude={"id"})
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def list_for_user(self, user_id: str, unread_only: bool = False, limit: int = 50) -> list[dict]:
        query: dict = {"user_id": user_id}
        if unread_only:
            query["read"] = False
        cursor = self._collection.find(query).sort("created_at", -1).limit(limit)
        return [doc async for doc in cursor]

    async def unread_count(self, user_id: str) -> int:
        return await self._collection.count_documents({"user_id": user_id, "read": False})

    async def mark_read(self, notification_id: str, user_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(notification_id)
        except (InvalidId, TypeError):
            return None
        await self._collection.update_one({"_id": oid, "user_id": user_id}, {"$set": {"read": True}})
        return await self._collection.find_one({"_id": oid, "user_id": user_id})

    async def mark_all_read(self, user_id: str) -> None:
        await self._collection.update_many({"user_id": user_id, "read": False}, {"$set": {"read": True}})
