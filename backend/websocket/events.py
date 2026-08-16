"""
Structured event schema for real-time WebSocket delivery.

This module is pure data shaping — it builds plain dicts with a consistent
shape and never touches the database, the CV pipeline, or business logic.
Routes call build_event() after their existing service calls succeed (or
after a recognition/liveness result comes back) and hand the result to the
connection manager to broadcast. Nothing here decides whether attendance
gets marked — see docs/websocket.md "Business logic rule".

CRITICAL: never put an embedding, raw image bytes, or password/token into
an event payload — these get broadcast to every connected client on a
session, further downstream than a REST response.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    RECOGNITION_DETECTED = "recognition.detected"
    RECOGNITION_UNKNOWN = "recognition.unknown"
    RECOGNITION_LOW_CONFIDENCE = "recognition.low_confidence"

    LIVENESS_STARTED = "liveness.started"
    LIVENESS_PROGRESS = "liveness.progress"
    LIVENESS_PASSED = "liveness.passed"
    LIVENESS_FAILED = "liveness.failed"

    ATTENDANCE_MARKED = "attendance.marked"
    ATTENDANCE_ALREADY_MARKED = "attendance.already_marked"
    ATTENDANCE_REJECTED = "attendance.rejected"

    SESSION_OPENED = "session.opened"
    SESSION_CLOSED = "session.closed"

    SYSTEM_ERROR = "system.error"


def build_event(event_type: EventType, session_id: str, **data: Any) -> dict:
    """
    Every event gets: event type, ISO timestamp, and the session it belongs
    to, plus whatever type-specific fields the caller passes in **data.
    Keep **data to plain JSON-serializable values only (str/int/float/bool/
    dict/list) — this goes straight over the wire.
    """
    return {
        "event": event_type.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        **data,
    }
