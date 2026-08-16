from database.models.audit_model import AuditLogInDB
from database.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, repo: AuditRepository):
        self._repo = repo

    async def log(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        actor_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        # `details` is caller-provided safe metadata only — enforced by
        # convention (every call site in this codebase passes plain
        # strings/numbers/booleans, never an embedding or password).
        entry = AuditLogInDB(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
        await self._repo.create(entry)
