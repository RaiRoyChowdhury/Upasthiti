from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models.audit_model import AuditLogInDB


class AuditRepository:
    """Append-only by convention — no update/delete methods exposed."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["audit_logs"]

    async def create(self, entry: AuditLogInDB) -> dict:
        doc = entry.model_dump(by_alias=True, exclude={"id"})
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def list_for_entity(
        self, entity_type: str, entity_id: str, limit: int = 50
    ) -> list[dict]:
        cursor = (
            self._collection.find({"entity_type": entity_type, "entity_id": entity_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def list_recent(self, limit: int = 100) -> list[dict]:
        cursor = self._collection.find({}).sort("created_at", -1).limit(limit)
        return [doc async for doc in cursor]
