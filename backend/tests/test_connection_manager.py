"""
Tests the connection manager in isolation with fake WebSocket-like objects
(anything with async accept()/send_json() methods) — no real network, no
FastAPI app, no browser required. Full end-to-end WebSocket auth/session
behavior is covered separately in test_websocket_auth.py.
"""

import pytest

from websocket.connection_manager import ConnectionManager

pytestmark = pytest.mark.asyncio


class FakeWebSocket:
    def __init__(self, fail_on_send: bool = False):
        self.accepted = False
        self.sent: list[dict] = []
        self.fail_on_send = fail_on_send

    async def accept(self):
        self.accepted = True

    async def send_json(self, data: dict):
        if self.fail_on_send:
            raise ConnectionError("simulated dead socket")
        self.sent.append(data)


async def test_connect_registers_and_accepts():
    manager = ConnectionManager()
    ws = FakeWebSocket()
    await manager.connect(ws, "session-A")
    assert ws.accepted is True
    assert manager.connection_count("session-A") == 1


async def test_broadcast_delivers_to_all_sockets_on_session():
    manager = ConnectionManager()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(ws1, "session-A")
    await manager.connect(ws2, "session-A")

    await manager.broadcast_to_session("session-A", {"event": "test.event"})

    assert ws1.sent == [{"event": "test.event"}]
    assert ws2.sent == [{"event": "test.event"}]


async def test_broadcast_is_scoped_to_session_id():
    manager = ConnectionManager()
    ws_a, ws_b = FakeWebSocket(), FakeWebSocket()
    await manager.connect(ws_a, "session-A")
    await manager.connect(ws_b, "session-B")

    await manager.broadcast_to_session("session-A", {"event": "test.event"})

    assert ws_a.sent == [{"event": "test.event"}]
    assert ws_b.sent == []  # session isolation — session B must not receive session A's events


async def test_broadcast_to_session_with_no_listeners_does_not_raise():
    manager = ConnectionManager()
    await manager.broadcast_to_session("nobody-here", {"event": "test.event"})  # should just no-op


async def test_disconnect_removes_socket():
    manager = ConnectionManager()
    ws = FakeWebSocket()
    await manager.connect(ws, "session-A")
    await manager.disconnect(ws, "session-A")
    assert manager.connection_count("session-A") == 0


async def test_broadcast_skips_dead_socket_without_breaking_others():
    manager = ConnectionManager()
    dead = FakeWebSocket(fail_on_send=True)
    alive = FakeWebSocket()
    await manager.connect(dead, "session-A")
    await manager.connect(alive, "session-A")

    await manager.broadcast_to_session("session-A", {"event": "test.event"})

    assert alive.sent == [{"event": "test.event"}]  # still received despite the other socket failing
    assert manager.connection_count("session-A") == 1  # dead socket was cleaned up
