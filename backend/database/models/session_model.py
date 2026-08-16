"""
Attendance session model — a scheduled/active/closed window during which
attendance can be marked for a class.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class SessionStatus(str, Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    CLOSED = "closed"


class SessionBase(BaseModel):
    subject: str = Field(..., min_length=1, max_length=120)
    class_name: str = Field(..., min_length=1, max_length=80)
    section: str = Field(..., min_length=1, max_length=20)
    late_threshold_minutes: Optional[int] = Field(
        None, ge=0, le=180, description="Minutes after start before LATE. Falls back to DEFAULT_LATE_THRESHOLD_MINUTES if unset."
    )


class SessionCreate(SessionBase):
    pass


class SessionInDB(SessionBase):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id", default=None)
    teacher_id: str  # User._id (string) of the teacher who created it
    status: SessionStatus = SessionStatus.SCHEDULED
    start_time: Optional[datetime] = None  # set when opened
    end_time: Optional[datetime] = None  # set when closed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionPublic(SessionBase):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    teacher_id: str
    status: SessionStatus
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db(cls, doc: dict[str, Any]) -> "SessionPublic":
        return cls.model_validate(doc)
