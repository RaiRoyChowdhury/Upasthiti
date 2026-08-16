"""
/api/students — student management. Teacher/admin only for writes; any
authenticated role can list/read (a student viewing their own record is a
Phase 7+ concern — for now, any authenticated user can read, matching
Phase 1's precedent of "authenticated" being the baseline bar).

Never returns biometric data — StudentPublic has no embedding field, full
stop, so there's no accidental-leak surface here even before RBAC applies.
"""

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from api.dependencies.auth_dependency import get_current_user, require_role
from api.dependencies.service_dependencies import get_student_service
from database.models.student_model import StudentCreate, StudentPublic, StudentStatus, StudentUpdate
from database.models.user_model import UserPublic, UserRole
from services.student_service import StudentService

router = APIRouter(prefix="/api/students", tags=["Students"])


class StudentListResponse(BaseModel):
    items: list[StudentPublic]
    total: int
    skip: int
    limit: int


@router.post("", response_model=StudentPublic, status_code=status.HTTP_201_CREATED)
async def create_student(
    payload: StudentCreate,
    service: StudentService = Depends(get_student_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    return await service.create_student(payload)


@router.get("", response_model=StudentListResponse)
async def list_students(
    search: str | None = Query(None),
    department: str | None = Query(None),
    section: str | None = Query(None),
    status_filter: StudentStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    service: StudentService = Depends(get_student_service),
    _user: UserPublic = Depends(get_current_user),
):
    items, total = await service.list_students(
        search=search, department=department, section=section, status=status_filter, skip=skip, limit=limit
    )
    return StudentListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{mongo_id}", response_model=StudentPublic)
async def get_student(
    mongo_id: str,
    service: StudentService = Depends(get_student_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.get_student(mongo_id)


@router.patch("/{mongo_id}", response_model=StudentPublic)
async def update_student(
    mongo_id: str,
    payload: StudentUpdate,
    service: StudentService = Depends(get_student_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    return await service.update_student(mongo_id, payload)


@router.delete("/{mongo_id}", response_model=StudentPublic)
async def deactivate_student(
    mongo_id: str,
    service: StudentService = Depends(get_student_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN)),
):
    # "Delete" = deactivate, not a hard delete — preserves attendance
    # history integrity for records that reference this student_id.
    return await service.deactivate_student(mongo_id)
