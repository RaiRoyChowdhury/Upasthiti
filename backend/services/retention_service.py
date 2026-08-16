"""
Retention enforcement - Phase 10.

The original spec explicitly warns: "Do not implement automatic deletion
without clear configuration and authorization." Two independent gates
enforce that, both required before a single document is ever deleted:

  1. A retention_days value must be explicitly set (config).
  2. policy.retention_enforcement_enabled must be explicitly True
     (authorization) - a separate checkbox an admin must deliberately
     check, not implied by merely entering a number of days.

Neither alone triggers anything. See docs/retention.md for the full
design and how to test it without waiting for the scheduled interval.
"""

from datetime import datetime, timedelta, timezone

from database.models.audit_model import AuditLogInDB
from database.repositories.attendance_repository import AttendanceRepository
from database.repositories.audit_repository import AuditRepository
from database.repositories.policy_repository import PolicyRepository
from database.repositories.review_repository import ReviewRepository
from utils.logger import get_logger

logger = get_logger(__name__)


class RetentionService:
    def __init__(
        self,
        policy_repo: PolicyRepository,
        attendance_repo: AttendanceRepository,
        review_repo: ReviewRepository,
        audit_repo: AuditRepository,
    ):
        self._policy = policy_repo
        self._attendance = attendance_repo
        self._reviews = review_repo
        self._audit = audit_repo

    async def run_purge_cycle(self) -> dict:
        """
        Returns a summary dict either way (enabled or not) so callers
        (the background loop, or the manual admin-triggered endpoint) can
        report exactly what happened - never a silent no-op.
        """
        policy = await self._policy.get_or_create()

        if not policy.get("retention_enforcement_enabled"):
            logger.info("Retention purge skipped: enforcement not enabled in policy.")
            return {"ran": False, "reason": "retention_enforcement_enabled is False", "deleted": {}}

        now = datetime.now(timezone.utc)
        deleted: dict[str, int] = {}

        attendance_days = policy.get("attendance_retention_days")
        if attendance_days:
            cutoff = now - timedelta(days=attendance_days)
            deleted["attendance_records"] = await self._attendance.delete_older_than(cutoff)

        recognition_days = policy.get("recognition_log_retention_days")
        if recognition_days:
            cutoff = now - timedelta(days=recognition_days)
            deleted["review_events"] = await self._reviews.delete_older_than(cutoff)

        total_deleted = sum(deleted.values())
        logger.info("Retention purge completed: %s", deleted)

        await self._audit.create(
            AuditLogInDB(
                actor_id=None,
                action="RETENTION_PURGE_EXECUTED",
                entity_type="system",
                entity_id="retention_job",
                details={"deleted": deleted, "total_deleted": total_deleted},
            )
        )

        return {"ran": True, "deleted": deleted, "total_deleted": total_deleted}
