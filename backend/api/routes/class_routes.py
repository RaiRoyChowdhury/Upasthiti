from fastapi import APIRouter, Depends, status

from api.dependencies.auth_dependency import get_current_user, require_role
from api.dependencies.service_dependencies import get_class_service
from database.models.class_model import (
    ClassCreate,
    ClassPublic,
    TimetableEntryCreate,
    TimetableEntryPublic,
)
from database.models.user_model import UserPublic, UserRole
from services.class_service import ClassService

router = APIRouter(prefix="/api/classes", tags=["Classes & Timetable"])


@router.post("", response_model=ClassPublic, status_code=status.HTTP_201_CREATED)
async def create_class(
    payload: ClassCreate,
    service: ClassService = Depends(get_class_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    return await service.create_class(payload, teacher_id=user.id)


@router.get("", response_model=list[ClassPublic])
async def list_classes(
    service: ClassService = Depends(get_class_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.list_classes()


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: str,
    service: ClassService = Depends(get_class_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN)),
):
    await service.delete_class(class_id)


@router.post("/timetable", response_model=TimetableEntryPublic, status_code=status.HTTP_201_CREATED)
async def create_timetable_entry(
    payload: TimetableEntryCreate,
    service: ClassService = Depends(get_class_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    return await service.create_timetable_entry(payload)


@router.get("/timetable", response_model=list[TimetableEntryPublic])
async def list_timetable(
    service: ClassService = Depends(get_class_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.list_timetable()


@router.delete("/timetable/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timetable_entry(
    entry_id: str,
    service: ClassService = Depends(get_class_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    await service.delete_timetable_entry(entry_id)


@router.get("/timetable/{entry_id}/session-defaults")
async def get_session_defaults(
    entry_id: str,
    service: ClassService = Depends(get_class_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    """Pre-fill values for the existing session-creation form — does not create a session itself."""
    return await service.get_session_defaults_from_timetable_entry(entry_id)
