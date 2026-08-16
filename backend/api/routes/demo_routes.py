from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from api.dependencies.auth_dependency import get_current_user, require_role
from database.connection import get_database
from database.models.demo_model import DemoDatasetSummary, DemoGenerateRequest
from database.models.user_model import UserPublic, UserRole
from database.repositories.demo_repository import DemoRepository
from services.demo_service import DemoService

router = APIRouter(prefix="/api/demo", tags=["Demo Mode"])


def get_demo_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> DemoService:
    return DemoService(DemoRepository(db))


@router.post("/generate", response_model=DemoDatasetSummary)
async def generate_demo_data(
    payload: DemoGenerateRequest,
    service: DemoService = Depends(get_demo_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    """Replaces any existing demo dataset. Never touches real students/sessions/attendance."""
    return await service.generate(payload.student_count, payload.session_count)


@router.delete("/clear")
async def clear_demo_data(
    service: DemoService = Depends(get_demo_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    await service.clear()
    return {"message": "Demo dataset cleared."}


@router.get("/summary", response_model=DemoDatasetSummary)
async def demo_summary(
    service: DemoService = Depends(get_demo_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.get_summary()


@router.get("/dashboard")
async def demo_dashboard(
    service: DemoService = Depends(get_demo_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.get_dashboard_data()
