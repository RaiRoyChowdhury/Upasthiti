from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase


class DemoRepository:
    """
    Every method here touches ONLY demo_* collections. No method in this
    class ever reads from or writes to `students`, `attendance_sessions`,
    or `attendance_records` - the real collections every other repository
    in this codebase uses. That separation is what makes Demo Mode safe.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self._students = db["demo_students"]
        self._sessions = db["demo_sessions"]
        self._attendance = db["demo_attendance"]
        self._meta = db["demo_meta"]

    async def clear_all(self) -> None:
        await self._students.delete_many({})
        await self._sessions.delete_many({})
        await self._attendance.delete_many({})
        await self._meta.delete_many({})

    async def insert_students(self, docs: list[dict]) -> None:
        if docs:
            await self._students.insert_many(docs)

    async def insert_sessions(self, docs: list[dict]) -> None:
        if docs:
            await self._sessions.insert_many(docs)

    async def insert_attendance(self, docs: list[dict]) -> None:
        if docs:
            await self._attendance.insert_many(docs)

    async def set_generated_at(self, when: datetime) -> None:
        await self._meta.update_one({"_key": "demo_meta"}, {"$set": {"generated_at": when}}, upsert=True)

    async def summary(self) -> dict:
        students = await self._students.count_documents({})
        sessions = await self._sessions.count_documents({})
        attendance = await self._attendance.count_documents({})
        meta = await self._meta.find_one({"_key": "demo_meta"})
        return {
            "students": students,
            "sessions": sessions,
            "attendance_records": attendance,
            "generated_at": meta.get("generated_at") if meta else None,
        }

    async def list_students(self) -> list[dict]:
        return [doc async for doc in self._students.find()]

    async def list_sessions(self) -> list[dict]:
        return [doc async for doc in self._sessions.find()]

    async def list_attendance(self) -> list[dict]:
        return [doc async for doc in self._attendance.find()]
