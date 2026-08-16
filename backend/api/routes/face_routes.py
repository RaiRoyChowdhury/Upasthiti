"""
/api/students/{student_id}/enrollment and /api/face/* — enrollment and
recognition. Restricted to teacher/admin: these are the roles that operate
the classroom camera, per spec section 32.

CRITICAL: no response model in this file ever includes an embedding.
FaceEnrollmentStatus and the recognition response below are hand-built
schemas with no vector field, not passthroughs of the DB document.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from api.dependencies.auth_dependency import get_current_user, require_role
from api.dependencies.service_dependencies import (
    get_enrollment_service,
    get_face_recognition_service,
    get_liveness_service,
    get_notification_service,
    get_review_service,
)
from cv.thresholds import get_thresholds
from cv.types import RecognitionOutcome
from database.models.face_profile_model import FaceEnrollmentStatus
from database.models.notification_model import NotificationType
from database.models.review_model import ReviewEventType
from database.models.user_model import UserPublic, UserRole
from services.enrollment_service import EnrollmentService
from services.face_recognition_service import FaceRecognitionService
from services.liveness_service import LivenessService
from services.notification_service import NotificationService
from services.review_dedup import ReviewDedupTracker
from services.review_service import ReviewService
from websocket.connection_manager import manager
from websocket.events import EventType, build_event

router = APIRouter(prefix="/api", tags=["Face Recognition"])


class ImageRequest(BaseModel):
    image_base64: str = Field(..., description="A single frame, base64-encoded (JPEG/PNG), optionally a data URL.")
    session_id: str | None = Field(
        None,
        description="Attendance session, used ONLY to route a real-time WebSocket event to "
        "listeners on /ws/attendance/{session_id}. Never affects the recognition/liveness "
        "result itself — omit it and this endpoint behaves exactly as it did before Phase 4.",
    )


class LivenessStartRequest(ImageRequest):
    student_id: str


class LivenessCheckRequest(BaseModel):
    image_base64: str = Field(..., description="A single frame, base64-encoded (JPEG/PNG), optionally a data URL.")
    session_id: str = Field(..., description="The liveness challenge session id returned by /face/liveness/start.")
    attendance_session_id: str | None = Field(
        None,
        description="Attendance session, used ONLY to route a real-time WebSocket event. "
        "Deliberately a different field name from `session_id` above (which means the "
        "liveness challenge session) to avoid ambiguity — never affects the liveness result.",
    )


class RecognitionResponse(BaseModel):
    outcome: RecognitionOutcome
    student_id: str | None = None
    confidence: float | None = None
    quality_score: float | None = None
    quality_message: str | None = None
    bbox: tuple[float, float, float, float] | None = Field(
        None, description="Face bounding box in the ORIGINAL captured frame's pixel coordinates (x1, y1, x2, y2)."
    )
    message: str


class LivenessResponse(BaseModel):
    session_id: str
    state: str
    prompt: str | None = None
    message: str


class MultiFaceEntryResponse(BaseModel):
    outcome: RecognitionOutcome
    student_id: str | None = None
    confidence: float | None = None
    bbox: tuple[float, float, float, float] | None = None


class MultiFaceResponse(BaseModel):
    faces: list[MultiFaceEntryResponse]


class CalibrationScoreEntry(BaseModel):
    student_id: str
    similarity: float


class CalibrationResponse(BaseModel):
    scores: list[CalibrationScoreEntry]
    configured_threshold: float
    configured_low_confidence_threshold: float


_OUTCOME_MESSAGES = {
    RecognitionOutcome.NO_FACE: "No face detected. Please face the camera.",
    RecognitionOutcome.MULTIPLE_FACES: "Multiple people detected. Please ensure only one person is in frame.",
    RecognitionOutcome.POOR_QUALITY: "Face quality is insufficient.",
    RecognitionOutcome.UNKNOWN: "Unknown person. Attendance not recorded.",
    RecognitionOutcome.LOW_CONFIDENCE: "Low confidence. Teacher verification required.",
    RecognitionOutcome.KNOWN: "Identity verified.",
}


@router.post(
    "/students/{student_id}/enrollment",
    response_model=FaceEnrollmentStatus,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_face(
    student_id: str,
    payload: ImageRequest,
    service: EnrollmentService = Depends(get_enrollment_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    return await service.enroll_face(student_id, payload.image_base64, actor_id=user.id)


@router.delete("/students/{student_id}/enrollment", response_model=FaceEnrollmentStatus)
async def delete_enrollment(
    student_id: str,
    service: EnrollmentService = Depends(get_enrollment_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    return await service.delete_enrollment(student_id, actor_id=user.id)


@router.post("/face/recognize", response_model=RecognitionResponse)
async def recognize_face(
    payload: ImageRequest,
    service: FaceRecognitionService = Depends(get_face_recognition_service),
    review_service: ReviewService = Depends(get_review_service),
    notification_service: NotificationService = Depends(get_notification_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    result = await service.recognize(payload.image_base64)

    quality_message = None
    if result.quality and not result.quality.passed:
        quality_message = result.quality.message

    response = RecognitionResponse(
        outcome=result.outcome,
        student_id=result.student_id,
        confidence=result.confidence,
        quality_score=result.quality.score if result.quality else None,
        quality_message=quality_message,
        bbox=result.bbox,
        message=quality_message or _OUTCOME_MESSAGES[result.outcome],
    )

    # Resolves a documented Phase 3 limitation: LOW_CONFIDENCE and UNKNOWN
    # outcomes now create a real review event, deduplicated so a lingering
    # face polled every ~1.3s doesn't spam one event per tick (see
    # services/review_dedup.py). A notification is sent to the acting
    # teacher only for LOW_CONFIDENCE, since that's the case that actually
    # needs a human judgment call on a candidate identity — UNKNOWN gets a
    # review event (for the audit/review-center record) but not a
    # notification per attempt, to avoid over-notifying on every stranger
    # who walks past the camera.
    if payload.session_id and result.outcome in (RecognitionOutcome.LOW_CONFIDENCE, RecognitionOutcome.UNKNOWN):
        dedup_key = f"{payload.session_id}:{result.outcome.value}:{result.student_id or 'unknown'}"
        if ReviewDedupTracker().should_create(dedup_key):
            event_type = (
                ReviewEventType.LOW_CONFIDENCE
                if result.outcome == RecognitionOutcome.LOW_CONFIDENCE
                else ReviewEventType.UNKNOWN_PERSON
            )
            await review_service.create_event(
                event_type=event_type,
                session_id=payload.session_id,
                candidate_student_id=result.student_id,
                confidence=result.confidence,
            )
            if result.outcome == RecognitionOutcome.LOW_CONFIDENCE:
                await notification_service.notify(
                    user_id=user.id,
                    notification_type=NotificationType.LOW_CONFIDENCE_REVIEW,
                    message=f"Low-confidence recognition for candidate {result.student_id} "
                    f"({round((result.confidence or 0) * 100)}%). Review required.",
                )

    # Real-time event — additive only. Skipped entirely if the caller
    # didn't send session_id (the existing HTTP-only flow keeps working
    # unchanged), and skipped for noisy/no-signal outcomes (NO_FACE,
    # MULTIPLE_FACES, POOR_QUALITY) per spec section 24 (no event spam for
    # non-meaningful frames). The recognition/attendance decision above is
    # already final by the time this runs — publishing can never change it.
    if payload.session_id:
        event_map = {
            RecognitionOutcome.KNOWN: EventType.RECOGNITION_DETECTED,
            RecognitionOutcome.LOW_CONFIDENCE: EventType.RECOGNITION_LOW_CONFIDENCE,
            RecognitionOutcome.UNKNOWN: EventType.RECOGNITION_UNKNOWN,
        }
        event_type = event_map.get(result.outcome)
        if event_type:
            await manager.broadcast_to_session(
                payload.session_id,
                build_event(
                    event_type,
                    payload.session_id,
                    student_id=result.student_id,
                    confidence=result.confidence,
                    bbox=result.bbox,
                ),
            )

    return response


@router.post("/face/liveness/start", response_model=LivenessResponse)
async def start_liveness(
    payload: LivenessStartRequest,
    service: LivenessService = Depends(get_liveness_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    session = await service.start(payload.student_id, payload.image_base64)

    if payload.session_id:
        await manager.broadcast_to_session(
            payload.session_id,
            build_event(
                EventType.LIVENESS_STARTED,
                payload.session_id,
                student_id=payload.student_id,
                liveness_session_id=session.session_id,
                prompt=session.prompt,
            ),
        )

    return LivenessResponse(session_id=session.session_id, state=session.state.value, prompt=session.prompt, message=session.prompt)


@router.post("/face/liveness/check", response_model=LivenessResponse)
async def check_liveness(
    payload: LivenessCheckRequest,
    service: LivenessService = Depends(get_liveness_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    session = await service.check(payload.session_id, payload.image_base64)

    messages = {
        "verified": "Liveness verified.",
        "timeout": "Liveness check timed out. Please try again.",
        "waiting_for_action": session.prompt,
    }

    if payload.attendance_session_id:
        event_map = {
            "verified": EventType.LIVENESS_PASSED,
            "timeout": EventType.LIVENESS_FAILED,
            "waiting_for_action": EventType.LIVENESS_PROGRESS,
        }
        event_type = event_map.get(session.state.value)
        if event_type:
            await manager.broadcast_to_session(
                payload.attendance_session_id,
                build_event(
                    event_type,
                    payload.attendance_session_id,
                    student_id=session.student_id,
                    liveness_session_id=session.session_id,
                    state=session.state.value,
                ),
            )

    return LivenessResponse(
        session_id=session.session_id,
        state=session.state.value,
        prompt=session.prompt if session.state.value == "waiting_for_action" else None,
        message=messages.get(session.state.value, session.prompt),
    )


@router.post("/face/recognize-multi", response_model=MultiFaceResponse)
async def recognize_all_faces(
    payload: ImageRequest,
    service: FaceRecognitionService = Depends(get_face_recognition_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER)),
):
    """
    Phase 9 — informational multi-face scanning ("who's currently in the
    room"). Deliberately separate from /face/recognize: this endpoint
    never feeds into attendance marking, which still requires the
    single-face + liveness-verified flow. See docs/multi-face.md.
    """
    results = await service.recognize_all_faces(payload.image_base64)
    return MultiFaceResponse(
        faces=[
            MultiFaceEntryResponse(
                outcome=r.outcome, student_id=r.student_id, confidence=r.confidence, bbox=r.bbox
            )
            for r in results
        ]
    )


@router.post("/face/calibration-test", response_model=CalibrationResponse)
async def calibration_test(
    payload: ImageRequest,
    service: FaceRecognitionService = Depends(get_face_recognition_service),
    _user: UserPublic = Depends(require_role(UserRole.ADMIN)),
):
    """
    Phase 9 calibration tooling (admin-only) — returns the top-5 raw
    similarity scores against every enrolled student for one captured
    frame, plus the currently configured thresholds, so an admin can see
    how well-separated a genuine match is from the next-closest score
    before deciding whether FACE_RECOGNITION_THRESHOLD needs adjusting.
    Never used by the live attendance flow.
    """
    scores = await service.calibration_scores(payload.image_base64, top_n=5)
    thresholds = get_thresholds()
    return CalibrationResponse(
        scores=[CalibrationScoreEntry(**s) for s in scores],
        configured_threshold=thresholds.face_recognition,
        configured_low_confidence_threshold=thresholds.low_confidence,
    )
