import pytest

pytestmark = pytest.mark.asyncio


async def _teacher_token(client, teacher_user):
    resp = await client.post(
        "/api/auth/login", json={"email": "teacher@example.com", "password": "TeacherPass123"}
    )
    return resp.json()["access_token"]


async def test_create_and_list_student(client, teacher_user):
    token = await _teacher_token(client, teacher_user)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/api/students",
        json={
            "name": "Alex Kumar",
            "student_id": "S001",
            "roll_number": "R001",
            "department": "CS",
            "section": "A",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["face_enrolled"] is False
    assert body["status"] == "active"
    assert "embedding" not in body  # never exposed, even accidentally

    list_resp = await client.get("/api/students", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


async def test_duplicate_student_id_rejected(client, teacher_user):
    token = await _teacher_token(client, teacher_user)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "name": "Alex Kumar",
        "student_id": "S001",
        "roll_number": "R001",
        "department": "CS",
        "section": "A",
    }
    first = await client.post("/api/students", json=payload, headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/students", json=payload, headers=headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "STUDENT_ID_TAKEN"


async def test_search_filters_by_name_and_id(client, teacher_user):
    token = await _teacher_token(client, teacher_user)
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(3):
        await client.post(
            "/api/students",
            json={
                "name": f"Student {i}",
                "student_id": f"S00{i}",
                "roll_number": f"R00{i}",
                "department": "CS",
                "section": "A",
            },
            headers=headers,
        )

    resp = await client.get("/api/students?search=S001", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["student_id"] == "S001"


async def test_deactivate_requires_admin(client, teacher_user):
    token = await _teacher_token(client, teacher_user)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/api/students",
        json={"name": "Alex", "student_id": "S001", "roll_number": "R001", "department": "CS", "section": "A"},
        headers=headers,
    )
    mongo_id = create_resp.json()["_id"]

    resp = await client.delete(f"/api/students/{mongo_id}", headers=headers)
    assert resp.status_code == 403
