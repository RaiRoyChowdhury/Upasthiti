from database.models.notification_model import NotificationInDB, NotificationPublic, NotificationType
from database.repositories.notification_repository import NotificationRepository


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self._repo = repo

    async def notify(self, user_id: str, notification_type: NotificationType, message: str) -> None:
        entry = NotificationInDB(user_id=user_id, type=notification_type, message=message)
        await self._repo.create(entry)

    async def list_for_user(self, user_id: str, unread_only: bool = False) -> list[NotificationPublic]:
        docs = await self._repo.list_for_user(user_id, unread_only=unread_only)
        return [NotificationPublic.from_db(d) for d in docs]

    async def unread_count(self, user_id: str) -> int:
        return await self._repo.unread_count(user_id)

    async def mark_read(self, notification_id: str, user_id: str) -> NotificationPublic | None:
        doc = await self._repo.mark_read(notification_id, user_id)
        return NotificationPublic.from_db(doc) if doc else None

    async def mark_all_read(self, user_id: str) -> None:
        await self._repo.mark_all_read(user_id)
