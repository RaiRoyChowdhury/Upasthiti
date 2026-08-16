"""
Review event model — created whenever the attendance pipeline can't make a
confident automatic decision (low confidence, unknown person, liveness
failure) and needs a human to look at it.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class ReviewEventType(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    UNKNOWN_PERSON = "unknown_person"
    LIVENESS_FAILED = "liveness_failed"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewEventInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id", default=None)
    event_type: ReviewEventType
    session_id: Optional[str] = None
    candidate_student_id: Optional[str] = None  # best-guess match, if any (LOW_CONFIDENCE only)
    confidence: Optional[float] = None
    status: ReviewStatus = ReviewStatus.PENDING
    reviewed_by: Optional[str] = None  # User._id of the teacher/admin who resolved it
    reviewed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewEventPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    event_type: ReviewEventType
    session_id: Optional[str]
    candidate_student_id: Optional[str]
    confidence: Optional[float]
    status: ReviewStatus
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime

    @classmethod
    def from_db(cls, doc: dict[str, Any]) -> "ReviewEventPublic":
        return cls.model_validate(doc)


class ReviewDecisionRequest(BaseModel):
    status: ReviewStatus = Field(..., description="APPROVED or REJECTED")
