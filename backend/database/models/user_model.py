"""
User model.

Three schema variants, on purpose:
  - UserCreate:  what the API accepts to create a user (plaintext password).
  - UserInDB:    what's actually stored in MongoDB (password_hash, never the
                 plaintext password).
  - UserPublic:  what the API is allowed to return. No password/hash, ever.

This split is the mechanism that prevents credential leakage through API
responses — it's not a convention we have to "remember," a route literally
cannot return a password_hash unless it explicitly bypasses UserPublic.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class UserRole(str, Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    role: UserRole
    student_id: Optional[str] = Field(
        None,
        description="Links a STUDENT-role account to a roster record (Student.student_id). "
        "Optional and independent of the roster — a student-role login can exist unlinked; "
        "see docs/access.md for why these are two separate concepts.",
    )


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserAdminUpdate(BaseModel):
    """Admin-only edits to an existing user — role, active status, student link."""

    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    student_id: Optional[str] = None


class UserInDB(UserBase):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id", default=None)
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

    @staticmethod
    def new_object_id() -> ObjectId:
        return ObjectId()


class UserPublic(UserBase):
    """Safe to return from the API. Never contains password_hash."""

    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    is_active: bool

    @classmethod
    def from_db(cls, doc: dict[str, Any]) -> "UserPublic":
        return cls.model_validate(doc)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
