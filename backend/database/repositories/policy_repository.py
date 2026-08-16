from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models.policy_model import DEFAULT_POLICY_DOC


class PolicyRepository:
    """
    Singleton document: exactly one policy row ever exists, at a fixed key.
    get_or_create() guarantees callers always get a document back, even on
    a totally fresh database, without a separate seed script.
    """

    _SINGLETON_KEY = "institution_policy"

    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["policy"]

    async def get_or_create(self) -> dict:
        doc = await self._collection.find_one({"_key": self._SINGLETON_KEY})
        if doc:
            return doc
        new_doc = {"_key": self._SINGLETON_KEY, **DEFAULT_POLICY_DOC}
        result = await self._collection.insert_one(new_doc)
        new_doc["_id"] = result.inserted_id
        return new_doc

    async def update(self, updates: dict, updated_by: str) -> dict:
        await self.get_or_create()  # ensure it exists first
        updates = {k: v for k, v in updates.items() if v is not None}
        updates["updated_at"] = datetime.now(timezone.utc)
        updates["updated_by"] = updated_by
        await self._collection.update_one({"_key": self._SINGLETON_KEY}, {"$set": updates})
        return await self._collection.find_one({"_key": self._SINGLETON_KEY})
