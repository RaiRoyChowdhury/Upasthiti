"""
Attendance service — orchestrates the full marking pipeline. This is the
"AttendanceDecision" domain object described in the spec: a plain dataclass,
not tightly coupled to any FastAPI response model, so it stays testable
without spinning up the API layer.

PIPELINE (mirrors the spec's numbered steps 1-10):
    1-2. Caller (the API route) has already established identity + liveness
         before calling this service — mark_attendance() assumes both are
         settled and focuses on session/duplicate/policy/scoring/persistence.
    3. Find session, validate it's ACTIVE.
    4. Validate attendance policy (session must be active).
    5. Check duplicate attendance (student_id + session_id).
    6. Determine PRESENT vs LATE from session.start_time + late threshold.
    7. Calculate integrity score.
    8. Create attendance record (idempotent — see attendance_repository.py).
    9. Create audit event.
    10. Return a safe result object.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from config.settings import get_settings
from database.models.attendance_model import (
    AttendanceInDB,
    AttendancePublic,
    AttendanceStatus,
    VerificationMethod,
)
from database.models.session_model import SessionStatus
from database.repositories.attendance_repository import AttendanceAlreadyExistsError, AttendanceRepository
from database.repositories.session_repository import SessionRepository
from services.audit_service import AuditService
from services.integrity_service import compute_integrity_score
from utils.exceptions import NotFoundError, ValidationAppError
from utils.logger import get_logger

logger = get_logger(__name__)


class AttendanceDecisionOutcome(str, Enum):
    MARKED = "marked"
    ALREADY_MARKED = "already_marked"
    SESSION_NOT_ACTIVE = "session_not_active"


@dataclass
class AttendanceDecision:
    outcome: AttendanceDecisionOutcome
    message: str
    attendance: AttendancePublic | None = None
    cooldown_seconds: int = 0


class AttendanceService:
    def __init__(
        self,
        attendance_repo: AttendanceRepository,
        session_repo: SessionRepository,
        audit_service: AuditService,
    ):
        self._attendance = attendance_repo
        self._sessions = session_repo
        self._audit = audit_service

    async def mark_attendance(
        self,
        student_id: str,
        session_id: str,
        recognition_confidence: float,
        face_quality_score: float,
        liveness_verified: bool,
        actor_id: str | None = None,
    ) -> AttendanceDecision:
        settings = get_settings()

        session_doc = await self._sessions.get_by_id(session_id)
        if not session_doc:
            raise NotFoundError("Session not found.", code="SESSION_NOT_FOUND")

        if session_doc["status"] != SessionStatus.ACTIVE.value:
            return AttendanceDecision(
                outcome=AttendanceDecisionOutcome.SESSION_NOT_ACTIVE,
                message="This session is not currently active. Attendance cannot be marked.",
            )

        # STEP 5 — duplicate check (fast path; the unique index is the
        # authoritative guarantee against races, this just avoids an
        # unnecessary insert attempt in the common case).
        existing = await self._attendance.get_existing(student_id, session_id)
        if existing:
            await self._audit.log(
                action="ATTENDANCE_DUPLICATE_ATTEMPT",
                entity_type="attendance",
                entity_id=str(existing["_id"]),
                actor_id=actor_id,
                details={"student_id": student_id, "session_id": session_id},
            )
            return AttendanceDecision(
                outcome=AttendanceDecisionOutcome.ALREADY_MARKED,
                message="Attendance was already marked for this session.",
                attendance=AttendancePublic.from_db(existing),
                cooldown_seconds=settings.RECOGNITION_COOLDOWN_SECONDS,
            )

        if not liveness_verified:
            raise ValidationAppError(
                "Liveness must be verified before attendance can be marked.", code="LIVENESS_NOT_VERIFIED"
            )

        # STEP 6 — present vs late
        status = self._determine_status(session_doc)

        # STEP 7 — integrity score
        integrity_score, breakdown = compute_integrity_score(
            recognition_confidence=recognition_confidence,
            face_quality_score=face_quality_score,
            liveness_verified=liveness_verified,
            session_valid=True,
            duplicate=False,
        )

        record = AttendanceInDB(
            student_id=student_id,
            session_id=session_id,
            status=status,
            recognition_confidence=recognition_confidence,
            liveness_verified=liveness_verified,
            integrity_score=integrity_score,
            integrity_breakdown=breakdown,
            verification_method=VerificationMethod.FACE_RECOGNITION,
        )

        # STEP 8 — create (idempotent: DB unique index is authoritative)
        try:
            doc = await self._attendance.create(record)
        except AttendanceAlreadyExistsError:
            # Lost a race to a concurrent request for the same student+session.
            existing = await self._attendance.get_existing(student_id, session_id)
            return AttendanceDecision(
                outcome=AttendanceDecisionOutcome.ALREADY_MARKED,
                message="Attendance was already marked for this session.",
                attendance=AttendancePublic.from_db(existing) if existing else None,
                cooldown_seconds=settings.RECOGNITION_COOLDOWN_SECONDS,
            )

        # STEP 9 — audit event
        await self._audit.log(
            action="ATTENDANCE_MARKED",
            entity_type="attendance",
            entity_id=str(doc["_id"]),
            actor_id=actor_id,
            details={"student_id": student_id, "session_id": session_id, "status": status.value},
        )

        logger.info("Attendance marked: student=%s session=%s status=%s", student_id, session_id, status.value)

        # STEP 10 — safe result
        return AttendanceDecision(
            outcome=AttendanceDecisionOutcome.MARKED,
            message="Attendance marked.",
            attendance=AttendancePublic.from_db(doc),
            cooldown_seconds=settings.RECOGNITION_COOLDOWN_SECONDS,
        )

    @staticmethod
    def _determine_status(session_doc: dict) -> AttendanceStatus:
        start_time = session_doc.get("start_time")
        if start_time is None:
            return AttendanceStatus.PRESENT

        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        late_threshold_minutes = session_doc.get("late_threshold_minutes")
        if late_threshold_minutes is None:
            late_threshold_minutes = get_settings().DEFAULT_LATE_THRESHOLD_MINUTES

        elapsed_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60
        return AttendanceStatus.LATE if elapsed_minutes > late_threshold_minutes else AttendanceStatus.PRESENT

    async def manual_override(
        self, attendance_id: str, status: AttendanceStatus, actor_id: str, reason: str
    ) -> AttendancePublic:
        doc = await self._attendance.get_by_id(attendance_id)
        if not doc:
            raise NotFoundError("Attendance record not found.", code="ATTENDANCE_NOT_FOUND")

        updated = await self._attendance.update_status(
            attendance_id, status.value, VerificationMethod.MANUAL_TEACHER_OVERRIDE.value
        )
        await self._audit.log(
            action="MANUAL_ATTENDANCE_VERIFICATION",
            entity_type="attendance",
            entity_id=attendance_id,
            actor_id=actor_id,
            details={"new_status": status.value, "reason": reason},
        )
        return AttendancePublic.from_db(updated)

    async def list_records(
        self, session_id: str | None = None, student_id: str | None = None, skip: int = 0, limit: int = 100
    ) -> tuple[list[AttendancePublic], int]:
        docs, total = await self._attendance.list_records(
            session_id=session_id, student_id=student_id, skip=skip, limit=limit
        )
        return [AttendancePublic.from_db(d) for d in docs], total

    async def get_record(self, attendance_id: str) -> AttendancePublic:
        doc = await self._attendance.get_by_id(attendance_id)
        if not doc:
            raise NotFoundError("Attendance record not found.", code="ATTENDANCE_NOT_FOUND")
        return AttendancePublic.from_db(doc)

    async def mark_exit(self, attendance_id: str, actor_id: str) -> AttendancePublic:
        """
        Phase 10 — manual exit marking (teacher/admin action), NOT
        automatic camera-based exit detection. See docs/demo-mode.md for
        why automatic detection was deliberately left out: distinguishing
        "student left" from "student briefly out of frame" without a
        second explicit signal is genuinely ambiguous, and a wrong
        auto-exit would corrupt duration data silently.
        """
        doc = await self._attendance.get_by_id(attendance_id)
        if not doc:
            raise NotFoundError("Attendance record not found.", code="ATTENDANCE_NOT_FOUND")
        if doc.get("exit_time") is not None:
            raise ValidationAppError("Exit time already recorded for this record.", code="EXIT_ALREADY_MARKED")

        exit_time = datetime.now(timezone.utc)
        updated = await self._attendance.set_exit_time(attendance_id, exit_time)
        await self._audit.log(
            action="ATTENDANCE_EXIT_MARKED",
            entity_type="attendance",
            entity_id=attendance_id,
            actor_id=actor_id,
        )
        return AttendancePublic.from_db(updated)

    async def session_occupancy(self, session_id: str, total_enrolled: int) -> dict:
        """Real count from real attendance records — see docs/demo-mode.md."""
        currently_present = await self._attendance.count_present_without_exit(session_id)
        occupancy_percent = round(currently_present / total_enrolled * 100, 1) if total_enrolled else 0.0
        return {
            "session_id": session_id,
            "currently_present": currently_present,
            "total_enrolled": total_enrolled,
            "occupancy_percent": occupancy_percent,
        }
