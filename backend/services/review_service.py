from database.models.review_model import (
    ReviewDecisionRequest,
    ReviewEventInDB,
    ReviewEventPublic,
    ReviewEventType,
    ReviewStatus,
)
from database.repositories.review_repository import ReviewRepository
from services.audit_service import AuditService
from utils.exceptions import NotFoundError, ValidationAppError


class ReviewService:
    def __init__(self, repo: ReviewRepository, audit_service: AuditService):
        self._repo = repo
        self._audit = audit_service

    async def create_event(
        self,
        event_type: ReviewEventType,
        session_id: str | None,
        candidate_student_id: str | None,
        confidence: float | None,
    ) -> ReviewEventPublic:
        entry = ReviewEventInDB(
            event_type=event_type,
            session_id=session_id,
            candidate_student_id=candidate_student_id,
            confidence=confidence,
        )
        doc = await self._repo.create(entry)
        return ReviewEventPublic.from_db(doc)

    async def list_events(
        self, status: ReviewStatus | None = None, skip: int = 0, limit: int = 50
    ) -> tuple[list[ReviewEventPublic], int]:
        docs, total = await self._repo.list_events(status=status, skip=skip, limit=limit)
        return [ReviewEventPublic.from_db(d) for d in docs], total

    async def get_event(self, review_id: str) -> ReviewEventPublic:
        doc = await self._repo.get_by_id(review_id)
        if not doc:
            raise NotFoundError("Review event not found.", code="REVIEW_NOT_FOUND")
        return ReviewEventPublic.from_db(doc)

    async def resolve(
        self, review_id: str, decision: ReviewDecisionRequest, actor_id: str
    ) -> ReviewEventPublic:
        doc = await self._repo.get_by_id(review_id)
        if not doc:
            raise NotFoundError("Review event not found.", code="REVIEW_NOT_FOUND")
        if doc["status"] != ReviewStatus.PENDING.value:
            raise ValidationAppError("This review event has already been resolved.", code="REVIEW_ALREADY_RESOLVED")

        updated = await self._repo.resolve(review_id, decision.status, actor_id)
        await self._audit.log(
            action="REVIEW_RESOLVED",
            entity_type="review_event",
            entity_id=review_id,
            actor_id=actor_id,
            details={"decision": decision.status.value},
        )
        return ReviewEventPublic.from_db(updated)
