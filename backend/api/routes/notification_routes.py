from fastapi import APIRouter, Depends, Query

from api.dependencies.auth_dependency import get_current_user
from api.dependencies.service_dependencies import get_notification_service
from database.models.notification_model import NotificationPublic
from database.models.user_model import UserPublic
from services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationPublic])
async def list_notifications(
    unread_only: bool = Query(False),
    service: NotificationService = Depends(get_notification_service),
    user: UserPublic = Depends(get_current_user),
):
    return await service.list_for_user(user.id, unread_only=unread_only)


@router.get("/unread-count")
async def unread_count(
    service: NotificationService = Depends(get_notification_service),
    user: UserPublic = Depends(get_current_user),
):
    count = await service.unread_count(user.id)
    return {"unread_count": count}


@router.post("/{notification_id}/read", response_model=NotificationPublic)
async def mark_read(
    notification_id: str,
    service: NotificationService = Depends(get_notification_service),
    user: UserPublic = Depends(get_current_user),
):
    return await service.mark_read(notification_id, user.id)


@router.post("/read-all")
async def mark_all_read(
    service: NotificationService = Depends(get_notification_service),
    user: UserPublic = Depends(get_current_user),
):
    await service.mark_all_read(user.id)
    return {"message": "All notifications marked as read."}
