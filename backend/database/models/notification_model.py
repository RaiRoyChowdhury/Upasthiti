from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class NotificationType(str, Enum):
    LOW_CONFIDENCE_REVIEW = "low_confidence_review"
    UNKNOWN_PERSON_REVIEW = "unknown_person_review"
    SESSION_OPENED = "session_opened"
    SESSION_CLOSED = "session_closed"
    LOW_ATTENDANCE = "low_attendance"
    MANUAL_CORRECTION = "manual_correction"


class NotificationInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id", default=None)
    user_id: str  # recipient — a specific teacher/admin User._id
    type: NotificationType
    message: str
    read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    type: NotificationType
    message: str
    read: bool
    created_at: datetime

    @classmethod
    def from_db(cls, doc: dict[str, Any]) -> "NotificationPublic":
        return cls.model_validate(doc)
