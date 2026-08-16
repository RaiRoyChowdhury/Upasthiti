"""
Institution attendance policy — admin-editable, stored in the database
(unlike CV/recognition thresholds, which stay in .env — see the note below
for why that split exists).

WHY THIS IS SEPARATE FROM config/settings.py:
FACE_RECOGNITION_THRESHOLD, LIVENESS_THRESHOLD, and similar CV thresholds
deliberately stay in .env, not here. Those need real recalibration against
actual enrollment data any time they change (see docs/computer-vision.md
"Calibration") — letting an admin casually edit them from a settings page
risks silently degrading recognition accuracy with no warning. Policy
values here (required attendance %, late threshold) are pure business
rules with no model-calibration risk, so they're safe to expose for
self-service editing.

Singleton by convention: exactly one policy document exists, upserted in
place rather than allowing multiple. See policy_repository.py.
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(str)]


class PolicyUpdate(BaseModel):
    required_attendance_percent: Optional[float] = Field(None, ge=0, le=100)
    default_late_threshold_minutes: Optional[int] = Field(None, ge=0, le=180)
    # Retention settings — see docs/retention.md for the full enforcement
    # design (Phase 10). Setting a day-count alone does nothing; deletion
    # only runs when retention_enforcement_enabled is explicitly True too.
    attendance_retention_days: Optional[int] = Field(None, ge=0, le=3650)
    recognition_log_retention_days: Optional[int] = Field(None, ge=0, le=3650)
    # Explicit, separate authorization gate — a retention_days value alone
    # never triggers deletion. Defaults False. See docs/retention.md.
    retention_enforcement_enabled: Optional[bool] = None


class PolicyPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    required_attendance_percent: float
    default_late_threshold_minutes: int
    attendance_retention_days: Optional[int]
    recognition_log_retention_days: Optional[int]
    retention_enforcement_enabled: bool = False
    updated_at: datetime
    updated_by: Optional[str]

    @classmethod
    def from_db(cls, doc: dict[str, Any]) -> "PolicyPublic":
        return cls.model_validate(doc)


DEFAULT_POLICY_DOC = {
    "required_attendance_percent": 75.0,
    "default_late_threshold_minutes": 10,
    "attendance_retention_days": None,
    "recognition_log_retention_days": None,
    "retention_enforcement_enabled": False,
    "updated_at": datetime.now(timezone.utc),
    "updated_by": None,
}
