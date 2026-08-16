"""
Student model.

Deliberately contains NO biometric data. Face embeddings live in
FaceProfile (face_profile_model.py), a separate collection accessed only
through its own repository — see docs/computer-vision.md "Biometric
privacy boundary". `face_enrolled` is a plain boolean flag here so the UI
can show enrollment status without ever touching the embedding collection.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class StudentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class StudentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    student_id: str = Field(..., min_length=1, max_length=40)  # institution-issued ID, not Mongo _id
    roll_number: str = Field(..., min_length=1, max_length=40)
    email: Optional[EmailStr] = None
    department: str = Field(..., min_length=1, max_length=80)
    section: str = Field(..., min_length=1, max_length=20)


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    roll_number: Optional[str] = Field(None, min_length=1, max_length=40)
    email: Optional[EmailStr] = None
    department: Optional[str] = Field(None, min_length=1, max_length=80)
    section: Optional[str] = Field(None, min_length=1, max_length=20)
    status: Optional[StudentStatus] = None


class StudentInDB(StudentBase):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id", default=None)
    status: StudentStatus = StudentStatus.ACTIVE
    face_enrolled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StudentPublic(StudentBase):
    """Safe to return from the API. Never contains embeddings."""

    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    status: StudentStatus
    face_enrolled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db(cls, doc: dict[str, Any]) -> "StudentPublic":
        return cls.model_validate(doc)
