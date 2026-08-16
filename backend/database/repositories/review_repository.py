from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models.review_model import ReviewEventInDB, ReviewStatus


class ReviewRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["review_events"]

    async def create(self, event: ReviewEventInDB) -> dict:
        doc = event.model_dump(by_alias=True, exclude={"id"})
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def get_by_id(self, review_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(review_id)
        except (InvalidId, TypeError):
            return None
        return await self._collection.find_one({"_id": oid})

    async def list_events(
        self, status: Optional[ReviewStatus] = None, skip: int = 0, limit: int = 50
    ) -> tuple[list[dict], int]:
        query: dict = {}
        if status:
            query["status"] = status.value
        total = await self._collection.count_documents(query)
        cursor = self._collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = [doc async for doc in cursor]
        return docs, total

    async def resolve(self, review_id: str, status: ReviewStatus, reviewed_by: str) -> Optional[dict]:
        try:
            oid = ObjectId(review_id)
        except (InvalidId, TypeError):
            return None
        await self._collection.update_one(
            {"_id": oid},
            {
                "$set": {
                    "status": status.value,
                    "reviewed_by": reviewed_by,
                    "reviewed_at": datetime.now(timezone.utc),
                }
            },
        )
        return await self.get_by_id(review_id)

    async def delete_older_than(self, cutoff) -> int:
        """
        Used only by the retention job (services/retention_service.py).
        Review events are this schema's closest analog to "recognition
        logs" — see docs/retention.md for that interpretation.
        """
        result = await self._collection.delete_many({"created_at": {"$lt": cutoff}})
        return result.deleted_count
