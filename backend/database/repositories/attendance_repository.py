"""
Attendance repository.

IDEMPOTENCY: a unique compound index on (student_id, session_id) is the
authoritative duplicate-prevention mechanism (see docs/attendance-engine.md
"Idempotency"). The service layer also checks before inserting for a fast,
friendly error path, but the index is what actually protects against race
conditions — two concurrent recognition requests for the same student in
the same session can both pass the service-level check, but only one
insert will ever succeed at the database level. The second one raises
DuplicateKeyError, which the service catches and translates into
"ATTENDANCE_ALREADY_MARKED" rather than a 500.
"""

from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from database.models.attendance_model import AttendanceInDB


class AttendanceAlreadyExistsError(Exception):
    pass


class AttendanceRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["attendance_records"]

    async def ensure_indexes(self) -> None:
        await self._collection.create_index(
            [("student_id", 1), ("session_id", 1)], unique=True, name="uniq_student_session"
        )

    async def get_existing(self, student_id: str, session_id: str) -> Optional[dict]:
        return await self._collection.find_one({"student_id": student_id, "session_id": session_id})

    async def create(self, record: AttendanceInDB) -> dict:
        doc = record.model_dump(by_alias=True, exclude={"id"})
        try:
            result = await self._collection.insert_one(doc)
        except DuplicateKeyError:
            raise AttendanceAlreadyExistsError(
                f"Attendance already exists for student={record.student_id} session={record.session_id}"
            )
        doc["_id"] = result.inserted_id
        return doc

    async def get_by_id(self, attendance_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(attendance_id)
        except (InvalidId, TypeError):
            return None
        return await self._collection.find_one({"_id": oid})

    async def update_status(self, attendance_id: str, status: str, verification_method: str) -> Optional[dict]:
        try:
            oid = ObjectId(attendance_id)
        except (InvalidId, TypeError):
            return None
        await self._collection.update_one(
            {"_id": oid},
            {"$set": {"status": status, "verification_method": verification_method}},
        )
        return await self.get_by_id(attendance_id)

    async def set_exit_time(self, attendance_id: str, exit_time) -> Optional[dict]:
        try:
            oid = ObjectId(attendance_id)
        except (InvalidId, TypeError):
            return None
        await self._collection.update_one({"_id": oid}, {"$set": {"exit_time": exit_time}})
        return await self.get_by_id(attendance_id)

    async def count_present_without_exit(self, session_id: str) -> int:
        """Used by the occupancy endpoint — see docs/demo-mode.md."""
        return await self._collection.count_documents(
            {"session_id": session_id, "status": {"$in": ["present", "late"]}, "exit_time": None}
        )

    async def list_records(
        self,
        session_id: Optional[str] = None,
        student_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict], int]:
        query: dict = {}
        if session_id:
            query["session_id"] = session_id
        if student_id:
            query["student_id"] = student_id
        total = await self._collection.count_documents(query)
        cursor = self._collection.find(query).sort("marked_at", -1).skip(skip).limit(limit)
        docs = [doc async for doc in cursor]
        return docs, total

    async def delete_older_than(self, cutoff) -> int:
        """Used only by the retention job (services/retention_service.py) — see docs/retention.md."""
        result = await self._collection.delete_many({"marked_at": {"$lt": cutoff}})
        return result.deleted_count
