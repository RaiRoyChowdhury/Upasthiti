"""
Dependency-injection wiring for Phase 2/3 repositories and services.
Kept separate from auth_dependency.py to keep that file focused on
authentication/RBAC concerns.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Depends

from database.connection import get_database
from database.repositories.attendance_repository import AttendanceRepository
from database.repositories.audit_repository import AuditRepository
from database.repositories.class_repository import ClassRepository, TimetableRepository
from database.repositories.face_profile_repository import FaceProfileRepository
from database.repositories.notification_repository import NotificationRepository
from database.repositories.policy_repository import PolicyRepository
from database.repositories.review_repository import ReviewRepository
from database.repositories.session_repository import SessionRepository
from database.repositories.student_repository import StudentRepository
from services.analytics_service import AnalyticsService
from services.attendance_service import AttendanceService
from services.audit_service import AuditService
from services.class_service import ClassService
from services.enrollment_service import EnrollmentService
from services.face_recognition_service import FaceRecognitionService
from services.liveness_service import LivenessService
from services.notification_service import NotificationService
from services.policy_service import PolicyService
from services.report_service import ReportService
from services.retention_service import RetentionService
from services.review_service import ReviewService
from services.session_service import SessionService
from services.student_service import StudentService


# ---- Repositories ----

def get_student_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> StudentRepository:
    return StudentRepository(db)


def get_face_profile_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> FaceProfileRepository:
    return FaceProfileRepository(db)


def get_session_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> SessionRepository:
    return SessionRepository(db)


def get_attendance_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> AttendanceRepository:
    return AttendanceRepository(db)


def get_review_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> ReviewRepository:
    return ReviewRepository(db)


def get_audit_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> AuditRepository:
    return AuditRepository(db)


def get_policy_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> PolicyRepository:
    return PolicyRepository(db)


def get_class_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> ClassRepository:
    return ClassRepository(db)


def get_timetable_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> TimetableRepository:
    return TimetableRepository(db)


def get_notification_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> NotificationRepository:
    return NotificationRepository(db)


# ---- Services ----

def get_audit_service(repo: AuditRepository = Depends(get_audit_repository)) -> AuditService:
    return AuditService(repo)


def get_student_service(repo: StudentRepository = Depends(get_student_repository)) -> StudentService:
    return StudentService(repo)


def get_enrollment_service(
    student_repo: StudentRepository = Depends(get_student_repository),
    face_profile_repo: FaceProfileRepository = Depends(get_face_profile_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> EnrollmentService:
    return EnrollmentService(student_repo, face_profile_repo, audit_service)


def get_face_recognition_service(
    face_profile_repo: FaceProfileRepository = Depends(get_face_profile_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> FaceRecognitionService:
    return FaceRecognitionService(face_profile_repo, audit_service)


def get_liveness_service() -> LivenessService:
    return LivenessService()


def get_session_service(
    repo: SessionRepository = Depends(get_session_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> SessionService:
    return SessionService(repo, audit_service)


def get_attendance_service(
    attendance_repo: AttendanceRepository = Depends(get_attendance_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> AttendanceService:
    return AttendanceService(attendance_repo, session_repo, audit_service)


def get_review_service(
    repo: ReviewRepository = Depends(get_review_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> ReviewService:
    return ReviewService(repo, audit_service)


def get_policy_service(repo: PolicyRepository = Depends(get_policy_repository)) -> PolicyService:
    return PolicyService(repo)


def get_class_service(
    class_repo: ClassRepository = Depends(get_class_repository),
    timetable_repo: TimetableRepository = Depends(get_timetable_repository),
) -> ClassService:
    return ClassService(class_repo, timetable_repo)


def get_notification_service(
    repo: NotificationRepository = Depends(get_notification_repository),
) -> NotificationService:
    return NotificationService(repo)


def get_analytics_service(
    attendance_repo: AttendanceRepository = Depends(get_attendance_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    student_repo: StudentRepository = Depends(get_student_repository),
    policy_service: PolicyService = Depends(get_policy_service),
) -> AnalyticsService:
    return AnalyticsService(attendance_repo, session_repo, student_repo, policy_service)


def get_report_service(
    attendance_repo: AttendanceRepository = Depends(get_attendance_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    student_repo: StudentRepository = Depends(get_student_repository),
) -> ReportService:
    return ReportService(attendance_repo, session_repo, student_repo)


def get_retention_service(
    policy_repo: PolicyRepository = Depends(get_policy_repository),
    attendance_repo: AttendanceRepository = Depends(get_attendance_repository),
    review_repo: ReviewRepository = Depends(get_review_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
) -> RetentionService:
    return RetentionService(policy_repo, attendance_repo, review_repo, audit_repo)
