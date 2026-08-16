from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from api.dependencies.auth_dependency import get_current_user, require_role
from api.dependencies.service_dependencies import (
    get_attendance_service,
    get_session_service,
    get_student_service,
)
from database.models.session_model import SessionCreate, SessionPublic, SessionStatus
from database.models.user_model import UserPublic, UserRole
from services.attendance_service import AttendanceService
from services.session_service import SessionService
from services.student_service import StudentService
from websocket.connection_manager import manager
from websocket.events import EventType, build_event

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


class SessionListResponse(BaseModel):
    items: list[SessionPublic]
    total: int
    skip: int
    limit: int


@router.post("", response_model=SessionPublic, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    service: SessionService = Depends(get_session_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    return await service.create_session(payload, teacher_id=user.id)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    status_filter: SessionStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    service: SessionService = Depends(get_session_service),
    _user: UserPublic = Depends(get_current_user),
):
    items, total = await service.list_sessions(status=status_filter, skip=skip, limit=limit)
    return SessionListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/active", response_model=SessionPublic | None)
async def get_active_session(
    service: SessionService = Depends(get_session_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.get_active_session()


@router.get("/{session_id}", response_model=SessionPublic)
async def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.get_session(session_id)


@router.post("/{session_id}/open", response_model=SessionPublic)
async def open_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    result = await service.open_session(session_id, actor_id=user.id)
    await manager.broadcast_to_session(
        session_id,
        build_event(EventType.SESSION_OPENED, session_id, subject=result.subject, class_name=result.class_name),
    )
    return result


@router.post("/{session_id}/close", response_model=SessionPublic)
async def close_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    result = await service.close_session(session_id, actor_id=user.id)
    await manager.broadcast_to_session(session_id, build_event(EventType.SESSION_CLOSED, session_id))
    return result


@router.get("/{session_id}/occupancy")
async def get_session_occupancy(
    session_id: str,
    attendance_service: AttendanceService = Depends(get_attendance_service),
    student_service: StudentService = Depends(get_student_service),
    _user: UserPublic = Depends(get_current_user),
):
    """
    Phase 10 — live classroom occupancy: how many currently-present
    students haven't had an exit marked yet. Real computation from real
    attendance/exit data — see docs/demo-mode.md.
    """
    _, total_students = await student_service.list_students(limit=1)
    return await attendance_service.session_occupancy(session_id, total_enrolled=total_students)
