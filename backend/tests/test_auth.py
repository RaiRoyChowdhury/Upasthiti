import pytest

pytestmark = pytest.mark.asyncio


async def test_login_succeeds_with_correct_credentials(client, admin_user):
    response = await client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "admin@example.com"
    assert body["user"]["role"] == "admin"
    # The password hash must never appear in the response.
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


async def test_login_fails_with_wrong_password(client, admin_user):
    response = await client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "WrongPassword"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_fails_for_unknown_email(client):
    response = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "Whatever123"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_protected_route_requires_token(client):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_protected_route_rejects_garbage_token(client):
    response = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_me_returns_current_user_with_valid_token(client, admin_user):
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123"},
    )
    token = login_resp.json()["access_token"]

    me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@example.com"


async def test_register_requires_admin_role(client, teacher_user):
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "teacher@example.com", "password": "TeacherPass123"},
    )
    token = login_resp.json()["access_token"]

    register_resp = await client.post(
        "/api/auth/register",
        json={
            "name": "New Student",
            "email": "student@example.com",
            "role": "student",
            "password": "StudentPass123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert register_resp.status_code == 403
    assert register_resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"


async def test_admin_can_register_new_user(client, admin_user):
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123"},
    )
    token = login_resp.json()["access_token"]

    register_resp = await client.post(
        "/api/auth/register",
        json={
            "name": "New Teacher",
            "email": "new.teacher@example.com",
            "role": "teacher",
            "password": "TeacherPass123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert register_resp.status_code == 201
    body = register_resp.json()
    assert body["email"] == "new.teacher@example.com"
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_rejects_duplicate_email(client, admin_user):
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123"},
    )
    token = login_resp.json()["access_token"]

    payload = {
        "name": "Duplicate",
        "email": "admin@example.com",  # already exists
        "role": "teacher",
        "password": "SomePass123",
    }
    response = await client.post(
        "/api/auth/register", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"
