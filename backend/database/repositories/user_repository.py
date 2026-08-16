"""
User repository.

Services never issue Mongo queries directly — they go through repositories.
This mirrors the same boundary we'll use for face embeddings in Phase 2+
(architectural decision: recognition service must not be coupled to MongoDB
queries directly, so a future vector-search backend can be swapped in here).
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models.user_model import UserCreate, UserRole


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["users"]

    async def get_by_email(self, email: str) -> Optional[dict]:
        return await self._collection.find_one({"email": email.lower()})

    async def get_by_id(self, user_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None
        return await self._collection.find_one({"_id": oid})

    async def create(self, user_create: UserCreate, password_hash: str) -> dict:
        doc = {
            "name": user_create.name,
            "email": user_create.email.lower(),
            "role": user_create.role.value,
            "student_id": user_create.student_id,
            "password_hash": password_hash,
            "created_at": datetime.now(timezone.utc),
            "is_active": True,
        }
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def count_by_role(self, role: UserRole) -> int:
        return await self._collection.count_documents({"role": role.value})

    async def list_all(self, limit: int = 100) -> list[dict]:
        cursor = self._collection.find().limit(limit)
        return [doc async for doc in cursor]

    async def list_users(self, skip: int = 0, limit: int = 100) -> tuple[list[dict], int]:
        total = await self._collection.count_documents({})
        cursor = self._collection.find().sort("created_at", 1).skip(skip).limit(limit)
        docs = [doc async for doc in cursor]
        return docs, total

    async def update_admin_fields(self, user_id: str, updates: dict) -> Optional[dict]:
        try:
            oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None
        updates = {k: v for k, v in updates.items() if v is not None}
        if updates:
            await self._collection.update_one({"_id": oid}, {"$set": updates})
        return await self.get_by_id(user_id)
