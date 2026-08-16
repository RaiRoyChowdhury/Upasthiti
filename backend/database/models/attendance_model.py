"""
Attendance record model.

Deliberately excludes any biometric vector. `integrity_breakdown` mirrors
the explainable-score structure required by the spec — a decision-support
indicator, not a claimed scientific probability (see docs/attendance-engine.md).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    LATE = "late"
    PENDING_REVIEW = "pending_review"


class VerificationMethod(str, Enum):
    FACE_RECOGNITION = "face_recognition"
    MANUAL_TEACHER_OVERRIDE = "manual_teacher_override"


class IntegrityBreakdown(BaseModel):
    recognition: str  # "high" | "medium" | "low"
    face_quality: str  # "good" | "fair" | "poor"
    liveness: str  # "verified" | "failed" | "skipped"
    session_valid: bool
    duplicate: bool


class AttendanceInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id", default=None)
    student_id: str
    session_id: str
    status: AttendanceStatus
    marked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exit_time: Optional[datetime] = None  # Phase 10 — set via POST .../mark-exit, manual not camera-auto-detected
    recognition_confidence: Optional[float] = None
    liveness_verified: bool = False
    integrity_score: int = Field(..., ge=0, le=100)
    integrity_breakdown: IntegrityBreakdown
    verification_method: VerificationMethod = VerificationMethod.FACE_RECOGNITION
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AttendancePublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    student_id: str
    session_id: str
    status: AttendanceStatus
    marked_at: datetime
    exit_time: Optional[datetime] = None
    recognition_confidence: Optional[float]
    liveness_verified: bool
    integrity_score: int
    integrity_breakdown: IntegrityBreakdown
    verification_method: VerificationMethod

    @classmethod
    def from_db(cls, doc: dict[str, Any]) -> "AttendancePublic":
        return cls.model_validate(doc)


class ManualVerificationRequest(BaseModel):
    decision: AttendanceStatus = Field(..., description="PRESENT or LATE — teacher's manual call")
    reason: str = Field(..., min_length=3, max_length=500)
