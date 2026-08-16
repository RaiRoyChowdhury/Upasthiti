"""
Student repository — the only place that runs Mongo queries against the
`students` collection. Never touches embeddings (that's face_profile_repository.py).
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models.student_model import StudentCreate, StudentStatus, StudentUpdate


class StudentRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["students"]

    async def get_by_mongo_id(self, mongo_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(mongo_id)
        except (InvalidId, TypeError):
            return None
        return await self._collection.find_one({"_id": oid})

    async def get_by_student_id(self, student_id: str) -> Optional[dict]:
        return await self._collection.find_one({"student_id": student_id})

    async def create(self, data: StudentCreate) -> dict:
        now = datetime.now(timezone.utc)
        doc = {
            **data.model_dump(),
            "status": StudentStatus.ACTIVE.value,
            "face_enrolled": False,
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def update(self, mongo_id: str, data: StudentUpdate) -> Optional[dict]:
        try:
            oid = ObjectId(mongo_id)
        except (InvalidId, TypeError):
            return None

        updates = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        if not updates:
            return await self.get_by_mongo_id(mongo_id)

        updates["updated_at"] = datetime.now(timezone.utc)
        await self._collection.update_one({"_id": oid}, {"$set": updates})
        return await self.get_by_mongo_id(mongo_id)

    async def set_face_enrolled(self, student_id: str, enrolled: bool) -> None:
        await self._collection.update_one(
            {"student_id": student_id},
            {"$set": {"face_enrolled": enrolled, "updated_at": datetime.now(timezone.utc)}},
        )

    async def deactivate(self, mongo_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(mongo_id)
        except (InvalidId, TypeError):
            return None
        await self._collection.update_one(
            {"_id": oid},
            {"$set": {"status": StudentStatus.INACTIVE.value, "updated_at": datetime.now(timezone.utc)}},
        )
        return await self.get_by_mongo_id(mongo_id)

    async def list_students(
        self,
        search: Optional[str] = None,
        department: Optional[str] = None,
        section: Optional[str] = None,
        status: Optional[StudentStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        query: dict = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"student_id": {"$regex": search, "$options": "i"}},
                {"roll_number": {"$regex": search, "$options": "i"}},
            ]
        if department:
            query["department"] = department
        if section:
            query["section"] = section
        if status:
            query["status"] = status.value

        total = await self._collection.count_documents(query)
        cursor = self._collection.find(query).sort("name", 1).skip(skip).limit(limit)
        docs = [doc async for doc in cursor]
        return docs, total
