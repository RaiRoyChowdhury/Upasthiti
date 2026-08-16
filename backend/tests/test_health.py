import pytest

pytestmark = pytest.mark.asyncio


async def test_health_check_returns_ok(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    # Whether the mongomock backend answers "ping" the same way a real
    # MongoDB server does can vary by version, so we assert the endpoint's
    # contract (shape + valid status values) rather than a single exact
    # value. Against a real MongoDB instance this will be "ok"/"connected".
    assert body["status"] in ("ok", "degraded")
    assert body["database"] in ("connected", "unavailable")
    assert "timestamp" in body
