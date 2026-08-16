from datetime import datetime, timezone

from config.settings import get_settings
from database.models.session_model import SessionCreate, SessionPublic, SessionStatus
from database.repositories.session_repository import SessionRepository
from services.audit_service import AuditService
from utils.exceptions import ConflictError, NotFoundError, ValidationAppError


class SessionService:
    def __init__(self, repo: SessionRepository, audit_service: AuditService):
        self._repo = repo
        self._audit = audit_service

    async def create_session(self, data: SessionCreate, teacher_id: str) -> SessionPublic:
        doc = await self._repo.create(data, teacher_id)
        return SessionPublic.from_db(doc)

    async def get_session(self, session_id: str) -> SessionPublic:
        doc = await self._repo.get_by_id(session_id)
        if not doc:
            raise NotFoundError("Session not found.", code="SESSION_NOT_FOUND")
        return SessionPublic.from_db(doc)

    async def open_session(self, session_id: str, actor_id: str) -> SessionPublic:
        doc = await self._repo.get_by_id(session_id)
        if not doc:
            raise NotFoundError("Session not found.", code="SESSION_NOT_FOUND")
        if doc["status"] == SessionStatus.CLOSED.value:
            raise ValidationAppError("A closed session cannot be reopened.", code="SESSION_ALREADY_CLOSED")
        if doc["status"] == SessionStatus.ACTIVE.value:
            return SessionPublic.from_db(doc)

        existing_active = await self._repo.get_active_session()
        if existing_active:
            raise ConflictError(
                "Another session is already active. Close it before opening a new one.",
                code="ANOTHER_SESSION_ACTIVE",
            )

        updated = await self._repo.set_status(
            session_id, SessionStatus.ACTIVE, start_time=datetime.now(timezone.utc)
        )
        await self._audit.log(
            action="SESSION_OPENED", entity_type="session", entity_id=session_id, actor_id=actor_id
        )
        return SessionPublic.from_db(updated)

    async def close_session(self, session_id: str, actor_id: str) -> SessionPublic:
        doc = await self._repo.get_by_id(session_id)
        if not doc:
            raise NotFoundError("Session not found.", code="SESSION_NOT_FOUND")
        if doc["status"] == SessionStatus.CLOSED.value:
            return SessionPublic.from_db(doc)

        updated = await self._repo.set_status(
            session_id, SessionStatus.CLOSED, end_time=datetime.now(timezone.utc)
        )
        await self._audit.log(
            action="SESSION_CLOSED", entity_type="session", entity_id=session_id, actor_id=actor_id
        )
        return SessionPublic.from_db(updated)

    async def get_active_session(self) -> SessionPublic | None:
        doc = await self._repo.get_active_session()
        return SessionPublic.from_db(doc) if doc else None

    async def list_sessions(
        self, status: SessionStatus | None = None, skip: int = 0, limit: int = 50
    ) -> tuple[list[SessionPublic], int]:
        docs, total = await self._repo.list_sessions(status=status, skip=skip, limit=limit)
        return [SessionPublic.from_db(d) for d in docs], total

    @staticmethod
    def late_threshold_minutes(session: SessionPublic) -> int:
        if session.late_threshold_minutes is not None:
            return session.late_threshold_minutes
        return get_settings().DEFAULT_LATE_THRESHOLD_MINUTES
