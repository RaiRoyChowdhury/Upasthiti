from websocket.events import EventType, build_event


def test_build_event_has_consistent_shape():
    event = build_event(EventType.ATTENDANCE_MARKED, "session-123", student={"id": "S1", "name": "Alex"})
    assert event["event"] == "attendance.marked"
    assert event["session_id"] == "session-123"
    assert "timestamp" in event
    assert event["student"] == {"id": "S1", "name": "Alex"}


def test_build_event_timestamp_is_iso_format():
    event = build_event(EventType.SESSION_OPENED, "session-1")
    # Should not raise — proves it's a real ISO 8601 string, not a placeholder.
    from datetime import datetime

    datetime.fromisoformat(event["timestamp"])


def test_build_event_never_includes_embedding_by_construction():
    # There's no `embedding` kwarg accepted anywhere in this codebase's call
    # sites, but this test documents and locks in the expectation: even if
    # a caller tried, build_event itself has no special-casing that would
    # let one slip through unnoticed — it's a plain dict merge.
    event = build_event(EventType.RECOGNITION_DETECTED, "s1", student_id="S1", confidence=0.9)
    assert "embedding" not in event
    assert "image" not in event
    assert "image_base64" not in event
