from database.models.class_model import (
    ClassCreate,
    ClassPublic,
    TimetableEntryCreate,
    TimetableEntryPublic,
)
from database.repositories.class_repository import ClassRepository, TimetableRepository
from utils.exceptions import NotFoundError


class ClassService:
    def __init__(self, class_repo: ClassRepository, timetable_repo: TimetableRepository):
        self._classes = class_repo
        self._timetable = timetable_repo

    async def create_class(self, data: ClassCreate, teacher_id: str) -> ClassPublic:
        doc = await self._classes.create(data, teacher_id)
        return ClassPublic.from_db(doc)

    async def list_classes(self) -> list[ClassPublic]:
        docs = await self._classes.list_all()
        return [ClassPublic.from_db(d) for d in docs]

    async def delete_class(self, class_id: str) -> None:
        deleted = await self._classes.delete(class_id)
        if not deleted:
            raise NotFoundError("Class not found.", code="CLASS_NOT_FOUND")

    async def create_timetable_entry(self, data: TimetableEntryCreate) -> TimetableEntryPublic:
        class_doc = await self._classes.get_by_id(data.class_id)
        if not class_doc:
            raise NotFoundError("Class not found.", code="CLASS_NOT_FOUND")
        doc = await self._timetable.create(data)
        return TimetableEntryPublic.from_db(doc)

    async def list_timetable(self) -> list[TimetableEntryPublic]:
        docs = await self._timetable.list_all()
        return [TimetableEntryPublic.from_db(d) for d in docs]

    async def delete_timetable_entry(self, entry_id: str) -> None:
        deleted = await self._timetable.delete(entry_id)
        if not deleted:
            raise NotFoundError("Timetable entry not found.", code="TIMETABLE_ENTRY_NOT_FOUND")

    async def get_session_defaults_from_timetable_entry(self, entry_id: str) -> dict:
        """
        Used by the "create session from timetable" convenience flow —
        returns the subject/class_name/section a new SessionCreate should
        be pre-filled with. Does not create the session itself; that still
        goes through the existing session_service (no business logic
        duplicated here).
        """
        entry = await self._timetable.get_by_id(entry_id)
        if not entry:
            raise NotFoundError("Timetable entry not found.", code="TIMETABLE_ENTRY_NOT_FOUND")
        class_doc = await self._classes.get_by_id(entry["class_id"])
        if not class_doc:
            raise NotFoundError("Class not found.", code="CLASS_NOT_FOUND")
        return {
            "subject": class_doc["subject"],
            "class_name": class_doc["class_name"],
            "section": class_doc["section"],
        }
