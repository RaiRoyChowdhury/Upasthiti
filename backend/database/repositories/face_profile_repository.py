"""
Face profile repository — the ONLY code path that reads or writes the
`face_profiles` collection (embeddings). Per the biometric privacy
boundary (docs/computer-vision.md), only enrollment_service.py and
face_recognition_service.py are allowed to import this.
"""

from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class FaceProfileRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["face_profiles"]

    async def upsert(
        self, student_id: str, embedding: list[float], model_version: str, quality_score: float
    ) -> dict:
        now = datetime.now(timezone.utc)
        doc = {
            "student_id": student_id,
            "embedding": embedding,
            "model_version": model_version,
            "quality_score": quality_score,
            "updated_at": now,
        }
        await self._collection.update_one(
            {"student_id": student_id},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return await self._collection.find_one({"student_id": student_id})

    async def get_by_student_id(self, student_id: str) -> Optional[dict]:
        return await self._collection.find_one({"student_id": student_id})

    async def delete(self, student_id: str) -> bool:
        result = await self._collection.delete_one({"student_id": student_id})
        return result.deleted_count > 0

    async def list_all_embeddings(self) -> list[tuple[str, list[float]]]:
        """
        Used only by face_recognition_service to build the in-memory
        comparison set for a recognition attempt. Never returned to a route.
        """
        cursor = self._collection.find({}, {"student_id": 1, "embedding": 1})
        return [(doc["student_id"], doc["embedding"]) async for doc in cursor]
