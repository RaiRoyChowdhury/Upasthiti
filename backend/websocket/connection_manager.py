"""
WebSocket connection manager.

Responsible ONLY for: tracking which sockets are connected to which
session, broadcasting a JSON-serializable event to all sockets on a
session, and cleaning up dead connections. It knows nothing about
attendance, recognition, or liveness — those are just dicts it forwards.
This is deliberate (spec: "keep this component independent of attendance
business logic").

Session-scoped, per architecture requirement: broadcasting to session A
must never reach a client connected to session B (see
tests/test_connection_manager.py for the isolation test).
"""

import asyncio

from fastapi import WebSocket

from utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self):
        # session_id -> set of connected websockets
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(session_id, set()).add(websocket)
        logger.info("WebSocket connected to session %s (total: %d)", session_id, len(self._connections[session_id]))

    async def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        async with self._lock:
            sockets = self._connections.get(session_id)
            if sockets and websocket in sockets:
                sockets.discard(websocket)
                if not sockets:
                    del self._connections[session_id]
        logger.info("WebSocket disconnected from session %s", session_id)

    async def broadcast_to_session(self, session_id: str, event: dict) -> None:
        """
        Sends `event` (a plain JSON-serializable dict) to every socket
        currently connected to `session_id`. Silently skips sessions with
        no listeners — publishing an event when nobody's watching is a
        normal, expected case, not an error.
        """
        sockets = self._connections.get(session_id)
        if not sockets:
            return

        stale: list[WebSocket] = []
        for socket in list(sockets):
            try:
                await socket.send_json(event)
            except Exception as exc:  # noqa: BLE001 — a dead socket must not break the broadcast for others
                logger.warning("Failed to send event to a socket on session %s: %s", session_id, exc)
                stale.append(socket)

        if stale:
            async with self._lock:
                for socket in stale:
                    self._connections.get(session_id, set()).discard(socket)

    def connection_count(self, session_id: str) -> int:
        return len(self._connections.get(session_id, set()))


# Process-wide singleton — same rationale as the FaceModelSingleton and
# LivenessManager in cv/: one shared instance, imported wherever needed,
# rather than re-instantiated per request.
manager = ConnectionManager()
