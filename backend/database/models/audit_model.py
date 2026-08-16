"""
Audit log model. Append-only by convention (repository exposes no update
method). Never stores biometric data — only IDs, action names, and safe
metadata.
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class AuditLogInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(alias="_id", default=None)
    actor_id: Optional[str] = None  # User._id; None for system-generated events
    action: str  # e.g. "FACE_ENROLLED", "ATTENDANCE_MARKED"
    entity_type: str  # e.g. "student", "attendance", "session"
    entity_id: str
    details: dict[str, Any] = Field(default_factory=dict)  # safe metadata only, never embeddings
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLogPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    actor_id: Optional[str]
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_db(cls, doc: dict[str, Any]) -> "AuditLogPublic":
        return cls.model_validate(doc)
