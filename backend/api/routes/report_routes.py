from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from api.dependencies.auth_dependency import require_role
from api.dependencies.service_dependencies import get_report_service
from database.models.user_model import UserPublic, UserRole
from services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def _csv_response(content: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _pdf_response(content: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/session/{session_id}")
async def session_report(
    session_id: str,
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    service: ReportService = Depends(get_report_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    if format == "pdf":
        content = await service.session_report_pdf(session_id)
        return _pdf_response(content, f"session_{session_id}_report.pdf")
    csv_content = await service.session_report_csv(session_id)
    return _csv_response(csv_content, f"session_{session_id}_report.csv")


@router.get("/student/{student_id}")
async def student_report(
    student_id: str,
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    service: ReportService = Depends(get_report_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    if format == "pdf":
        content = await service.student_report_pdf(student_id)
        return _pdf_response(content, f"student_{student_id}_report.pdf")
    csv_content = await service.student_report_csv(student_id)
    return _csv_response(csv_content, f"student_{student_id}_report.csv")


@router.get("/class")
async def class_report(
    class_name: str = Query(...),
    section: str = Query(...),
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    service: ReportService = Depends(get_report_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    if format == "pdf":
        content = await service.class_report_pdf(class_name, section)
        return _pdf_response(content, f"class_{class_name}_{section}_report.pdf")
    csv_content = await service.class_report_csv(class_name, section)
    return _csv_response(csv_content, f"class_{class_name}_{section}_report.csv")
