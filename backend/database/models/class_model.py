from datetime import datetime, time, timezone
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class DayOfWeek(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class ClassCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=120)
    class_name: str = Field(..., min_length=1, max_length=80)
    section: str = Field(..., min_length=1, max_length=20)


class ClassInDB(ClassCreate):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id", default=None)
    teacher_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClassPublic(ClassCreate):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    teacher_id: str
    created_at: datetime

    @classmethod
    def from_db(cls, doc: dict[str, Any]) -> "ClassPublic":
        return cls.model_validate(doc)


class TimetableEntryCreate(BaseModel):
    class_id: str
    day_of_week: DayOfWeek
    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="24h HH:MM")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="24h HH:MM")


class TimetableEntryInDB(TimetableEntryCreate):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id", default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TimetableEntryPublic(TimetableEntryCreate):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    created_at: datetime

    @classmethod
    def from_db(cls, doc: dict[str, Any]) -> "TimetableEntryPublic":
        return cls.model_validate(doc)
