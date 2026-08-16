from fastapi import APIRouter, Depends, Query

from api.dependencies.auth_dependency import get_current_user
from api.dependencies.service_dependencies import get_analytics_service
from database.models.user_model import UserPublic
from services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/overview")
async def get_overview(
    service: AnalyticsService = Depends(get_analytics_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.overview()


@router.get("/student/{student_id}")
async def get_student_stats(
    student_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.student_stats(student_id)


@router.get("/student/{student_id}/forecast")
async def get_student_forecast(
    student_id: str,
    additional_classes: int = Query(5, ge=0, le=100),
    service: AnalyticsService = Depends(get_analytics_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.forecast_for_student(student_id, additional_classes)


@router.get("/student/{student_id}/heatmap")
async def get_student_heatmap(
    student_id: str,
    days: int = Query(90, ge=1, le=365),
    service: AnalyticsService = Depends(get_analytics_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.student_heatmap(student_id, days=days)


@router.get("/session/{session_id}/summary")
async def get_session_summary(
    session_id: str,
    service: AnalyticsService = Depends(get_analytics_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.session_summary(session_id)


@router.get("/class")
async def get_class_stats(
    class_name: str = Query(...),
    section: str = Query(...),
    service: AnalyticsService = Depends(get_analytics_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.class_stats(class_name, section)
