"""
Face profile — biometric data, stored in its own collection.

CRITICAL: there is deliberately no "FaceProfilePublic" schema. This model
must NEVER be returned from an API route. Only enrollment_service.py and
face_recognition_service.py (via face_profile_repository.py) ever read the
`embedding` field, and neither of them puts it in a response, a log line,
or an error message. See docs/computer-vision.md "Biometric privacy".
"""

from datetime import datetime, timezone
from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class FaceProfileInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, protected_namespaces=())

    id: PyObjectId = Field(alias="_id", default=None)
    student_id: str  # references Student.student_id (institution ID, not Mongo _id)
    embedding: list[float]
    model_version: str  # e.g. "insightface:buffalo_l"
    quality_score: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FaceEnrollmentStatus(BaseModel):
    """
    The ONLY thing about enrollment ever exposed via API — status metadata,
    no vector data. Returned by POST/DELETE .../enrollment endpoints.
    """

    student_id: str
    face_enrolled: bool
    quality_score: Optional[float] = None
    enrolled_at: Optional[datetime] = None
    message: str
