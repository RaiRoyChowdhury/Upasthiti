"""
Shared pytest fixtures.

Tests never touch a real MongoDB instance — they use mongomock-motor, an
in-memory async-compatible mock of the Motor client. This keeps the test
suite fast and independent of any running database, while still exercising
the real repository/service/route code paths.
"""

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from database import connection as db_connection
from database.models.user_model import UserCreate, UserRole
from database.repositories.user_repository import UserRepository
from auth.security import hash_password


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_db(monkeypatch):
    """Replaces the real Mongo connection with an in-memory mock for the test."""
    client = AsyncMongoMockClient()
    db = client["smartattend_ai_test"]

    db_connection.mongo_manager.client = client
    db_connection.mongo_manager.db = db

    yield db

    db_connection.mongo_manager.client = None
    db_connection.mongo_manager.db = None


@pytest_asyncio.fixture
async def app(mock_db):
    # Imported here so the app is built AFTER mongo_manager.db is patched,
    # and so the real lifespan (which calls the real connect_to_mongo) is
    # bypassed entirely for tests.
    from main import create_app

    fastapi_app = create_app()
    yield fastapi_app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_user(mock_db):
    repo = UserRepository(mock_db)
    user_create = UserCreate(
        name="Admin User",
        email="admin@example.com",
        role=UserRole.ADMIN,
        password="AdminPass123",
    )
    doc = await repo.create(user_create, hash_password(user_create.password))
    return doc


@pytest_asyncio.fixture
async def teacher_user(mock_db):
    repo = UserRepository(mock_db)
    user_create = UserCreate(
        name="Teacher User",
        email="teacher@example.com",
        role=UserRole.TEACHER,
        password="TeacherPass123",
    )
    doc = await repo.create(user_create, hash_password(user_create.password))
    return doc
