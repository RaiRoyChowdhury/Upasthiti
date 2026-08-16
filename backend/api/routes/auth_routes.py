"""
/api/auth routes.

Registration is admin-only (a teacher/student account shouldn't be able to
create arbitrary accounts). The very first admin account is created via
scripts/create_admin.py, not through the API — see README "First run".

User <-> Student linking (see docs/access.md): a STUDENT-role login account
and a Student roster record are two separate concepts. `student_id` on
UserCreate/UserAdminUpdate optionally links them; this route validates the
referenced Student actually exists before allowing the link.
"""

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from api.dependencies.auth_dependency import get_auth_service, get_current_user, require_role
from api.dependencies.service_dependencies import get_student_repository
from database.models.user_model import (
    LoginRequest,
    TokenResponse,
    UserAdminUpdate,
    UserCreate,
    UserPublic,
    UserRole,
)
from database.repositories.student_repository import StudentRepository
from services.auth_service import AuthService
from utils.exceptions import NotFoundError

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class UserListResponse(BaseModel):
    items: list[UserPublic]
    total: int
    skip: int
    limit: int


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    token, user = await auth_service.authenticate(payload.email, payload.password)
    return TokenResponse(access_token=token, user=user)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(current_user: UserPublic = Depends(get_current_user)):
    # JWTs are stateless in Phase 1 — there is no server-side session to
    # invalidate. The client is responsible for discarding the token.
    # (A revocation/blacklist store is a documented future improvement,
    # see docs/security.md.)
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: UserPublic = Depends(get_current_user)):
    return current_user


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    payload: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
    student_repo: StudentRepository = Depends(get_student_repository),
    _admin: UserPublic = Depends(require_role(UserRole.ADMIN)),
):
    if payload.student_id:
        student = await student_repo.get_by_student_id(payload.student_id)
        if not student:
            raise NotFoundError(
                f"No student roster record with student_id '{payload.student_id}'.", code="STUDENT_NOT_FOUND"
            )
    return await auth_service.register_user(payload)


@router.get("/users", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    auth_service: AuthService = Depends(get_auth_service),
    _admin: UserPublic = Depends(require_role(UserRole.ADMIN)),
):
    items, total = await auth_service.list_users(skip=skip, limit=limit)
    return UserListResponse(items=items, total=total, skip=skip, limit=limit)


@router.patch("/users/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: str,
    payload: UserAdminUpdate,
    auth_service: AuthService = Depends(get_auth_service),
    student_repo: StudentRepository = Depends(get_student_repository),
    admin: UserPublic = Depends(require_role(UserRole.ADMIN)),
):
    if payload.student_id:
        student = await student_repo.get_by_student_id(payload.student_id)
        if not student:
            raise NotFoundError(
                f"No student roster record with student_id '{payload.student_id}'.", code="STUDENT_NOT_FOUND"
            )
    return await auth_service.admin_update_user(user_id, payload, actor_id=admin.id)
