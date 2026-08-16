"""
/api/attendance — marking and querying attendance records.

SECURITY NOTE: the client never gets to assert "liveness passed" directly.
POST /mark takes a liveness_session_id, and this route looks up that
session server-side (via LivenessService) to confirm it actually reached
the VERIFIED state for this student before calling into AttendanceService.
A client sending a fabricated liveness_verified=true boolean would have no
effect — there is no such field on the request.
"""

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from api.dependencies.auth_dependency import get_current_user, require_role
from api.dependencies.service_dependencies import (
    get_attendance_service,
    get_liveness_service,
    get_student_repository,
)
from cv.types import LivenessState
from database.models.attendance_model import AttendancePublic, ManualVerificationRequest
from database.models.user_model import UserPublic, UserRole
from database.repositories.student_repository import StudentRepository
from services.attendance_service import AttendanceDecisionOutcome, AttendanceService
from services.liveness_service import LivenessService
from utils.exceptions import ValidationAppError
from websocket.connection_manager import manager
from websocket.events import EventType, build_event

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


class MarkAttendanceRequest(BaseModel):
    student_id: str
    session_id: str
    liveness_session_id: str
    recognition_confidence: float = Field(..., ge=0.0, le=1.0)
    face_quality_score: float = Field(..., ge=0.0, le=1.0)


class AttendanceDecisionResponse(BaseModel):
    outcome: AttendanceDecisionOutcome
    message: str
    attendance: AttendancePublic | None = None
    cooldown_seconds: int = 0


class AttendanceListResponse(BaseModel):
    items: list[AttendancePublic]
    total: int
    skip: int
    limit: int


_DECISION_EVENT_MAP = {
    AttendanceDecisionOutcome.MARKED: EventType.ATTENDANCE_MARKED,
    AttendanceDecisionOutcome.ALREADY_MARKED: EventType.ATTENDANCE_ALREADY_MARKED,
    AttendanceDecisionOutcome.SESSION_NOT_ACTIVE: EventType.ATTENDANCE_REJECTED,
}


@router.post("/mark", response_model=AttendanceDecisionResponse)
async def mark_attendance(
    payload: MarkAttendanceRequest,
    attendance_service: AttendanceService = Depends(get_attendance_service),
    liveness_service: LivenessService = Depends(get_liveness_service),
    student_repo: StudentRepository = Depends(get_student_repository),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    liveness_session = liveness_service.get(payload.liveness_session_id)
    if liveness_session is None:
        raise ValidationAppError("Liveness session not found or expired.", code="LIVENESS_SESSION_NOT_FOUND")
    if liveness_session.student_id != payload.student_id:
        raise ValidationAppError("Liveness session does not match this student.", code="LIVENESS_STUDENT_MISMATCH")

    liveness_verified = liveness_session.state == LivenessState.VERIFIED

    decision = await attendance_service.mark_attendance(
        student_id=payload.student_id,
        session_id=payload.session_id,
        recognition_confidence=payload.recognition_confidence,
        face_quality_score=payload.face_quality_score,
        liveness_verified=liveness_verified,
        actor_id=user.id,
    )

    # Real-time event — published AFTER the existing attendance engine has
    # already made and persisted its decision. The WebSocket layer cannot
    # influence student_id/status/score; it only reports what already
    # happened (architecture rule — see docs/websocket.md).
    event_type = _DECISION_EVENT_MAP.get(decision.outcome)
    if event_type:
        student_doc = await student_repo.get_by_student_id(payload.student_id)
        student_name = student_doc["name"] if student_doc else payload.student_id
        await manager.broadcast_to_session(
            payload.session_id,
            build_event(
                event_type,
                payload.session_id,
                student={"id": payload.student_id, "name": student_name},
                status=decision.attendance.status.value if decision.attendance else None,
                integrity_score=decision.attendance.integrity_score if decision.attendance else None,
                message=decision.message,
            ),
        )

    return AttendanceDecisionResponse(
        outcome=decision.outcome,
        message=decision.message,
        attendance=decision.attendance,
        cooldown_seconds=decision.cooldown_seconds,
    )


@router.get("", response_model=AttendanceListResponse)
async def list_attendance(
    session_id: str | None = Query(None),
    student_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: AttendanceService = Depends(get_attendance_service),
    _user: UserPublic = Depends(get_current_user),
):
    items, total = await service.list_records(session_id=session_id, student_id=student_id, skip=skip, limit=limit)
    return AttendanceListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{attendance_id}", response_model=AttendancePublic)
async def get_attendance(
    attendance_id: str,
    service: AttendanceService = Depends(get_attendance_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.get_record(attendance_id)


@router.post("/{attendance_id}/verify", response_model=AttendancePublic)
async def verify_attendance(
    attendance_id: str,
    payload: ManualVerificationRequest,
    service: AttendanceService = Depends(get_attendance_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    return await service.manual_override(
        attendance_id, status=payload.decision, actor_id=user.id, reason=payload.reason
    )


@router.post("/{attendance_id}/mark-exit", response_model=AttendancePublic)
async def mark_exit(
    attendance_id: str,
    service: AttendanceService = Depends(get_attendance_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    """Phase 10 — manual exit marking. See docs/demo-mode.md for why this isn't camera-automatic."""
    return await service.mark_exit(attendance_id, actor_id=user.id)
