"""
Typed threshold accessors.

Every threshold used anywhere in the CV/attendance pipeline is read through
this module, which itself reads from config.settings. This is the single
choke point that makes "no hardcoded thresholds" actually enforceable —
nothing downstream should ever write `if score > 0.6:` with a literal.
"""

from dataclasses import dataclass

from config.settings import get_settings


@dataclass(frozen=True)
class Thresholds:
    face_recognition: float
    low_confidence: float
    liveness: float
    recognition_cooldown_seconds: int

    min_face_quality_score: float
    min_face_size_ratio: float
    max_blur_variance_floor: float
    max_yaw_degrees_for_enrollment: float

    liveness_yaw_delta_degrees: float
    liveness_timeout_seconds: int
    liveness_session_ttl_seconds: int

    default_late_threshold_minutes: int


def get_thresholds() -> Thresholds:
    s = get_settings()
    return Thresholds(
        face_recognition=s.FACE_RECOGNITION_THRESHOLD,
        low_confidence=s.LOW_CONFIDENCE_THRESHOLD,
        liveness=s.LIVENESS_THRESHOLD,
        recognition_cooldown_seconds=s.RECOGNITION_COOLDOWN_SECONDS,
        min_face_quality_score=s.MIN_FACE_QUALITY_SCORE,
        min_face_size_ratio=s.MIN_FACE_SIZE_RATIO,
        max_blur_variance_floor=s.MAX_BLUR_VARIANCE_FLOOR,
        max_yaw_degrees_for_enrollment=s.MAX_YAW_DEGREES_FOR_ENROLLMENT,
        liveness_yaw_delta_degrees=s.LIVENESS_YAW_DELTA_DEGREES,
        liveness_timeout_seconds=s.LIVENESS_TIMEOUT_SECONDS,
        liveness_session_ttl_seconds=s.LIVENESS_SESSION_TTL_SECONDS,
        default_late_threshold_minutes=s.DEFAULT_LATE_THRESHOLD_MINUTES,
    )
