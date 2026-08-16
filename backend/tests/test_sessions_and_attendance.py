import pytest

from cv.liveness import LivenessManager
from cv.types import FacePose, LivenessState

pytestmark = pytest.mark.asyncio


async def _teacher_headers(client, teacher_user):
    resp = await client.post(
        "/api/auth/login", json={"email": "teacher@example.com", "password": "TeacherPass123"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_student(client, headers, student_id="S001"):
    resp = await client.post(
        "/api/students",
        json={
            "name": "Alex Kumar",
            "student_id": student_id,
            "roll_number": "R001",
            "department": "CS",
            "section": "A",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_and_open_session(client, headers):
    create_resp = await client.post(
        "/api/sessions",
        json={"subject": "Data Structures", "class_name": "CS101", "section": "A"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["_id"]

    open_resp = await client.post(f"/api/sessions/{session_id}/open", headers=headers)
    assert open_resp.status_code == 200
    assert open_resp.json()["status"] == "active"
    return session_id


def _make_verified_liveness_session(student_id: str) -> str:
    """
    Bypasses the actual webcam/CV pipeline to create a VERIFIED liveness
    session directly — this lets us test the attendance pipeline's
    session/duplicate/scoring logic without needing InsightFace installed.
    The liveness state machine itself is tested separately and thoroughly
    in test_liveness_state_machine.py using the same real code path.
    """
    manager = LivenessManager()
    session = manager.start_challenge(student_id, FacePose(yaw=0.0, pitch=0.0, roll=0.0))
    session.state = LivenessState.VERIFIED
    return session.session_id


async def test_only_one_session_can_be_active_at_a_time(client, teacher_user):
    headers = await _teacher_headers(client, teacher_user)
    await _create_and_open_session(client, headers)

    create_resp = await client.post(
        "/api/sessions", json={"subject": "Databases", "class_name": "CS102", "section": "A"}, headers=headers
    )
    second_id = create_resp.json()["_id"]

    open_resp = await client.post(f"/api/sessions/{second_id}/open", headers=headers)
    assert open_resp.status_code == 409
    assert open_resp.json()["error"]["code"] == "ANOTHER_SESSION_ACTIVE"


async def test_closed_session_cannot_be_reopened(client, teacher_user):
    headers = await _teacher_headers(client, teacher_user)
    session_id = await _create_and_open_session(client, headers)

    close_resp = await client.post(f"/api/sessions/{session_id}/close", headers=headers)
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "closed"

    reopen_resp = await client.post(f"/api/sessions/{session_id}/open", headers=headers)
    assert reopen_resp.status_code == 422
    assert reopen_resp.json()["error"]["code"] == "SESSION_ALREADY_CLOSED"


async def test_mark_attendance_success_then_duplicate_is_blocked(client, teacher_user):
    headers = await _teacher_headers(client, teacher_user)
    student = await _create_student(client, headers)
    session_id = await _create_and_open_session(client, headers)

    liveness_session_id = _make_verified_liveness_session(student["student_id"])

    first = await client.post(
        "/api/attendance/mark",
        json={
            "student_id": student["student_id"],
            "session_id": session_id,
            "liveness_session_id": liveness_session_id,
            "recognition_confidence": 0.91,
            "face_quality_score": 0.85,
        },
        headers=headers,
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["outcome"] == "marked"
    assert first_body["attendance"]["status"] == "present"
    assert 0 <= first_body["attendance"]["integrity_score"] <= 100
    assert "embedding" not in first_body["attendance"]

    # Second attempt for the SAME student+session must NOT create a new record.
    second_liveness_id = _make_verified_liveness_session(student["student_id"])
    second = await client.post(
        "/api/attendance/mark",
        json={
            "student_id": student["student_id"],
            "session_id": session_id,
            "liveness_session_id": second_liveness_id,
            "recognition_confidence": 0.91,
            "face_quality_score": 0.85,
        },
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["outcome"] == "already_marked"

    list_resp = await client.get(f"/api/attendance?session_id={session_id}", headers=headers)
    assert list_resp.json()["total"] == 1  # still only one record


async def test_mark_attendance_rejected_when_session_not_active(client, teacher_user):
    headers = await _teacher_headers(client, teacher_user)
    student = await _create_student(client, headers)

    create_resp = await client.post(
        "/api/sessions", json={"subject": "Physics", "class_name": "PHY101", "section": "B"}, headers=headers
    )
    session_id = create_resp.json()["_id"]  # created but never opened -> still SCHEDULED

    liveness_session_id = _make_verified_liveness_session(student["student_id"])
    resp = await client.post(
        "/api/attendance/mark",
        json={
            "student_id": student["student_id"],
            "session_id": session_id,
            "liveness_session_id": liveness_session_id,
            "recognition_confidence": 0.9,
            "face_quality_score": 0.9,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "session_not_active"


async def test_mark_attendance_rejected_without_verified_liveness(client, teacher_user):
    headers = await _teacher_headers(client, teacher_user)
    student = await _create_student(client, headers)
    session_id = await _create_and_open_session(client, headers)

    # Liveness session exists but was never verified (still WAITING_FOR_ACTION).
    manager = LivenessManager()
    session = manager.start_challenge(student["student_id"], FacePose(yaw=0.0, pitch=0.0, roll=0.0))

    resp = await client.post(
        "/api/attendance/mark",
        json={
            "student_id": student["student_id"],
            "session_id": session_id,
            "liveness_session_id": session.session_id,
            "recognition_confidence": 0.9,
            "face_quality_score": 0.9,
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "LIVENESS_NOT_VERIFIED"
