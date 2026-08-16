"""
Enrollment service — the only service (besides face_recognition_service)
allowed to touch FaceProfileRepository. Orchestrates:

    decode image -> detect -> quality (frontal required) -> embedding
        -> upsert face_profile -> mark student.face_enrolled -> audit event

Enrollment intentionally requires stricter quality (frontal pose) than
recognition — we want a clean reference embedding, not the most lenient
frame we can get away with.
"""

from config.settings import get_settings
from cv.face_recognizer import extract_single_face
from cv.preprocessing import decode_base64_image
from database.models.face_profile_model import FaceEnrollmentStatus
from database.repositories.face_profile_repository import FaceProfileRepository
from database.repositories.student_repository import StudentRepository
from services.audit_service import AuditService
from utils.exceptions import NotFoundError, ValidationAppError
from utils.logger import get_logger

logger = get_logger(__name__)


class EnrollmentService:
    def __init__(
        self,
        student_repo: StudentRepository,
        face_profile_repo: FaceProfileRepository,
        audit_service: AuditService,
    ):
        self._students = student_repo
        self._face_profiles = face_profile_repo
        self._audit = audit_service

    async def enroll_face(self, student_id: str, image_base64: str, actor_id: str) -> FaceEnrollmentStatus:
        student = await self._students.get_by_student_id(student_id)
        if not student:
            raise NotFoundError("Student not found.", code="STUDENT_NOT_FOUND")

        frame = decode_base64_image(image_base64)
        extraction = extract_single_face(frame, require_frontal=True)

        if not extraction.quality.passed:
            # Deliberately NOT persisting anything on a failed attempt —
            # per "no fake functionality", a rejected enrollment attempt
            # produces no embedding and no misleading success state.
            raise ValidationAppError(extraction.quality.message, code="ENROLLMENT_QUALITY_REJECTED")

        if extraction.face is None or extraction.face.embedding is None:
            raise ValidationAppError(
                "Could not extract a usable face embedding. Please try again.",
                code="ENROLLMENT_EXTRACTION_FAILED",
            )

        settings = get_settings()
        model_version = f"insightface:{settings.INSIGHTFACE_MODEL_PACK}"

        await self._face_profiles.upsert(
            student_id=student_id,
            embedding=extraction.face.embedding,
            model_version=model_version,
            quality_score=extraction.quality.score,
        )
        await self._students.set_face_enrolled(student_id, True)

        await self._audit.log(
            action="FACE_ENROLLED",
            entity_type="student",
            entity_id=student_id,
            actor_id=actor_id,
            details={"quality_score": round(extraction.quality.score, 3), "model_version": model_version},
        )

        logger.info("Face enrolled for student %s (quality=%.2f)", student_id, extraction.quality.score)

        return FaceEnrollmentStatus(
            student_id=student_id,
            face_enrolled=True,
            quality_score=extraction.quality.score,
            enrolled_at=None,  # set by the DB layer; not re-fetched here to keep this call cheap
            message="Enrollment successful.",
        )

    async def delete_enrollment(self, student_id: str, actor_id: str) -> FaceEnrollmentStatus:
        student = await self._students.get_by_student_id(student_id)
        if not student:
            raise NotFoundError("Student not found.", code="STUDENT_NOT_FOUND")

        deleted = await self._face_profiles.delete(student_id)
        await self._students.set_face_enrolled(student_id, False)

        if deleted:
            await self._audit.log(
                action="FACE_ENROLLMENT_DELETED",
                entity_type="student",
                entity_id=student_id,
                actor_id=actor_id,
            )

        return FaceEnrollmentStatus(
            student_id=student_id,
            face_enrolled=False,
            message="Enrollment removed." if deleted else "No enrollment existed to remove.",
        )
