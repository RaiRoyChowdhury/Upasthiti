"""
End-to-end tests for /ws/attendance/{session_id} — real auth, real RBAC,
real session lookup, run through the actual FastAPI app (not mocked out).

Uses FastAPI's synchronous TestClient rather than the async httpx client
the rest of the suite uses, because TestClient is what provides
websocket_connect(). The app's lifespan (which would try a REAL MongoDB
connection) is deliberately never triggered here — TestClient only runs
startup/shutdown when used as `with TestClient(app) as client:`, and this
file avoids that context-manager form specifically so the mocked
mongo_manager set up below stays in effect instead of being overwritten.
"""

import asyncio

from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from auth.security import create_access_token, hash_password
from database import connection as db_connection
from database.models.session_model import SessionCreate
from database.models.user_model import UserCreate, UserRole
from database.repositories.session_repository import SessionRepository
from database.repositories.user_repository import UserRepository


def _setup_mock_db():
    client = AsyncMongoMockClient()
    db = client["smartattend_ai_ws_test"]
    db_connection.mongo_manager.client = client
    db_connection.mongo_manager.db = db
    return db


def _teardown_mock_db():
    db_connection.mongo_manager.client = None
    db_connection.mongo_manager.db = None


def _make_app():
    from main import create_app

    return create_app()


def test_websocket_rejects_missing_token():
    db = _setup_mock_db()
    try:
        app = _make_app()
        client = TestClient(app)  # no `with` — lifespan (real Mongo connect) never runs

        async def setup():
            repo = SessionRepository(db)
            session_doc = await repo.create(
                SessionCreate(subject="Math", class_name="C1", section="A"), teacher_id="t1"
            )
            return str(session_doc["_id"])

        session_id = asyncio.run(setup())

        try:
            with client.websocket_connect(f"/ws/attendance/{session_id}") as ws:
                ws.receive_text()
            assert False, "expected the connection to be rejected"
        except Exception:
            pass  # connection refused/closed — expected, no token provided
    finally:
        _teardown_mock_db()


def test_websocket_accepts_valid_teacher_with_existing_session():
    db = _setup_mock_db()
    try:
        app = _make_app()
        client = TestClient(app)

        async def setup():
            user_repo = UserRepository(db)
            teacher = UserCreate(name="T", email="t@example.com", role=UserRole.TEACHER, password="Pass1234")
            doc = await user_repo.create(teacher, hash_password(teacher.password))

            session_repo = SessionRepository(db)
            session_doc = await session_repo.create(
                SessionCreate(subject="Math", class_name="C1", section="A"), teacher_id=str(doc["_id"])
            )
            return str(doc["_id"]), str(session_doc["_id"])

        user_id, session_id = asyncio.run(setup())
        token = create_access_token(subject=user_id, extra_claims={"role": "teacher"})

        with client.websocket_connect(f"/ws/attendance/{session_id}?token={token}") as ws:
            # Connection accepted and stays open — proves auth + RBAC +
            # session-existence checks all passed for a valid teacher token.
            ws.close()
    finally:
        _teardown_mock_db()


def test_websocket_rejects_student_role():
    db = _setup_mock_db()
    try:
        app = _make_app()
        client = TestClient(app)

        async def setup():
            user_repo = UserRepository(db)
            student_user = UserCreate(name="S", email="s@example.com", role=UserRole.STUDENT, password="Pass1234")
            doc = await user_repo.create(student_user, hash_password(student_user.password))

            session_repo = SessionRepository(db)
            session_doc = await session_repo.create(
                SessionCreate(subject="Math", class_name="C1", section="A"), teacher_id="someone"
            )
            return str(doc["_id"]), str(session_doc["_id"])

        user_id, session_id = asyncio.run(setup())
        token = create_access_token(subject=user_id, extra_claims={"role": "student"})

        try:
            with client.websocket_connect(f"/ws/attendance/{session_id}?token={token}") as ws:
                ws.receive_text()
            assert False, "expected student role to be rejected"
        except Exception:
            pass  # closed with 4403 — expected
    finally:
        _teardown_mock_db()


def test_websocket_rejects_nonexistent_session():
    db = _setup_mock_db()
    try:
        app = _make_app()
        client = TestClient(app)

        async def setup():
            user_repo = UserRepository(db)
            teacher = UserCreate(name="T", email="t2@example.com", role=UserRole.TEACHER, password="Pass1234")
            doc = await user_repo.create(teacher, hash_password(teacher.password))
            return str(doc["_id"])

        user_id = asyncio.run(setup())
        token = create_access_token(subject=user_id, extra_claims={"role": "teacher"})

        try:
            with client.websocket_connect(f"/ws/attendance/000000000000000000000000?token={token}") as ws:
                ws.receive_text()
            assert False, "expected nonexistent session to be rejected"
        except Exception:
            pass  # closed with 4404 — expected
    finally:
        _teardown_mock_db()
