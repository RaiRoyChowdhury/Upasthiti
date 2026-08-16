"""
Shared CV domain types.

Kept separate from FastAPI/Pydantic API schemas on purpose (per architecture
decision in docs/architecture.md): these are internal CV pipeline objects,
not wire formats. Routes translate them into API response models — they
never get returned as-is.
"""

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class FacePose:
    """Head orientation in degrees. Used for frontal-ness checks and liveness."""

    yaw: float
    pitch: float
    roll: float


@dataclass
class DetectedFace:
    """One detected face in a frame, before any quality/recognition decision."""

    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels
    det_score: float  # detector confidence, 0-1
    pose: FacePose | None
    embedding: list[float] | None = None  # populated only when recognition is requested


class QualityIssue(str, Enum):
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"
    FACE_TOO_SMALL = "face_too_small"
    TOO_BLURRY = "too_blurry"
    TOO_DARK = "too_dark"
    TOO_BRIGHT = "too_bright"
    NOT_FRONTAL = "not_frontal"


@dataclass
class QualityResult:
    passed: bool
    score: float  # 0-1 composite quality score
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def message(self) -> str:
        """Human-readable guidance for the frontend — never a raw code."""
        messages = {
            QualityIssue.NO_FACE: "No face detected. Please face the camera.",
            QualityIssue.MULTIPLE_FACES: "More than one face detected. Only one person should be in frame.",
            QualityIssue.FACE_TOO_SMALL: "Move closer to the camera.",
            QualityIssue.TOO_BLURRY: "Image is too blurry. Hold still.",
            QualityIssue.TOO_DARK: "Lighting is too low. Move to a brighter area.",
            QualityIssue.TOO_BRIGHT: "Lighting is too strong. Reduce glare.",
            QualityIssue.NOT_FRONTAL: "Please face the camera directly.",
        }
        if not self.issues:
            return "Good quality."
        return messages.get(self.issues[0], "Face quality is insufficient.")


class RecognitionOutcome(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    LOW_CONFIDENCE = "low_confidence"
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"
    POOR_QUALITY = "poor_quality"


@dataclass
class RecognitionResult:
    outcome: RecognitionOutcome
    student_id: str | None = None
    confidence: float | None = None  # cosine similarity, 0-1
    quality: QualityResult | None = None
    pose: FacePose | None = None
    bbox: tuple[float, float, float, float] | None = None


class LivenessState(str, Enum):
    NOT_STARTED = "not_started"
    CHALLENGE_CREATED = "challenge_created"
    WAITING_FOR_ACTION = "waiting_for_action"
    ACTION_DETECTED = "action_detected"
    VERIFIED = "verified"
    FAILED = "failed"
    TIMEOUT = "timeout"


class LivenessChallengeType(str, Enum):
    TURN_HEAD_RIGHT = "turn_head_right"
    TURN_HEAD_LEFT = "turn_head_left"


LIVENESS_CHALLENGE_PROMPTS = {
    LivenessChallengeType.TURN_HEAD_RIGHT: "Please turn your head slightly to the right.",
    LivenessChallengeType.TURN_HEAD_LEFT: "Please turn your head slightly to the left.",
}
