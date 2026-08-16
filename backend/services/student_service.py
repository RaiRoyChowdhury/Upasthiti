from database.models.student_model import StudentCreate, StudentPublic, StudentStatus, StudentUpdate
from database.repositories.student_repository import StudentRepository
from utils.exceptions import ConflictError, NotFoundError
from utils.logger import get_logger

logger = get_logger(__name__)


class StudentService:
    def __init__(self, repo: StudentRepository):
        self._repo = repo

    async def create_student(self, data: StudentCreate) -> StudentPublic:
        existing = await self._repo.get_by_student_id(data.student_id)
        if existing:
            raise ConflictError(
                f"A student with student_id '{data.student_id}' already exists.", code="STUDENT_ID_TAKEN"
            )
        doc = await self._repo.create(data)
        logger.info("Student created: %s (%s)", doc["name"], doc["student_id"])
        return StudentPublic.from_db(doc)

    async def get_student(self, mongo_id: str) -> StudentPublic:
        doc = await self._repo.get_by_mongo_id(mongo_id)
        if not doc:
            raise NotFoundError("Student not found.", code="STUDENT_NOT_FOUND")
        return StudentPublic.from_db(doc)

    async def get_student_by_student_id(self, student_id: str) -> StudentPublic:
        doc = await self._repo.get_by_student_id(student_id)
        if not doc:
            raise NotFoundError("Student not found.", code="STUDENT_NOT_FOUND")
        return StudentPublic.from_db(doc)

    async def update_student(self, mongo_id: str, data: StudentUpdate) -> StudentPublic:
        doc = await self._repo.update(mongo_id, data)
        if not doc:
            raise NotFoundError("Student not found.", code="STUDENT_NOT_FOUND")
        return StudentPublic.from_db(doc)

    async def deactivate_student(self, mongo_id: str) -> StudentPublic:
        doc = await self._repo.deactivate(mongo_id)
        if not doc:
            raise NotFoundError("Student not found.", code="STUDENT_NOT_FOUND")
        logger.info("Student deactivated: %s", doc.get("student_id"))
        return StudentPublic.from_db(doc)

    async def list_students(
        self,
        search: str | None = None,
        department: str | None = None,
        section: str | None = None,
        status: StudentStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[StudentPublic], int]:
        docs, total = await self._repo.list_students(
            search=search, department=department, section=section, status=status, skip=skip, limit=limit
        )
        return [StudentPublic.from_db(d) for d in docs], total
