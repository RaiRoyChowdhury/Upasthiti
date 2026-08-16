from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.dependencies.auth_dependency import require_role
from api.dependencies.service_dependencies import get_review_service
from database.models.review_model import ReviewDecisionRequest, ReviewEventPublic, ReviewStatus
from database.models.user_model import UserPublic, UserRole
from services.review_service import ReviewService

router = APIRouter(prefix="/api/reviews", tags=["Review Center"])


class ReviewListResponse(BaseModel):
    items: list[ReviewEventPublic]
    total: int
    skip: int
    limit: int


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    status_filter: ReviewStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    service: ReviewService = Depends(get_review_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    items, total = await service.list_events(status=status_filter, skip=skip, limit=limit)
    return ReviewListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{review_id}", response_model=ReviewEventPublic)
async def get_review(
    review_id: str,
    service: ReviewService = Depends(get_review_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    return await service.get_event(review_id)


@router.post("/{review_id}/resolve", response_model=ReviewEventPublic)
async def resolve_review(
    review_id: str,
    payload: ReviewDecisionRequest,
    service: ReviewService = Depends(get_review_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    return await service.resolve(review_id, payload, actor_id=user.id)
