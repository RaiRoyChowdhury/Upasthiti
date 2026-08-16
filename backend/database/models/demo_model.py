"""
Demo Mode models - Phase 10.

DELIBERATELY SEPARATE from student_model.py/session_model.py/
attendance_model.py, stored in entirely different collections
(demo_students/demo_sessions/demo_attendance, see demo_repository.py).
This is the actual isolation mechanism: a demo record is a different
Python type in a different MongoDB collection, not a flag on a real
record - there is no code path by which demo data can appear in a real
students/sessions/attendance API response, because those routes never
query these collections at all.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DemoDatasetSummary(BaseModel):
    students: int
    sessions: int
    attendance_records: int
    generated_at: Optional[datetime] = None


class DemoGenerateRequest(BaseModel):
    student_count: int = Field(15, ge=1, le=100)
    session_count: int = Field(5, ge=1, le=50)
