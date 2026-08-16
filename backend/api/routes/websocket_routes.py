"""
/ws/attendance/{session_id} — real-time event stream for a single
attendance session.

This endpoint does NOT make attendance decisions. It:
  1. Authenticates the connecting user (JWT via query param — see
     get_current_user_ws in auth_dependency.py for why).
  2. Enforces the same RBAC as the rest of the live-attendance flow
     (teacher/admin only — see docs/websocket.md "Authentication").
  3. Confirms the session actually exists.
  4. Registers the connection with the connection manager, scoped to
     this session_id.
  5. Waits (does nothing) until the client disconnects.

Every actual event on this socket is published by REST routes (face_routes,
attendance_routes, session_routes) AFTER their existing service calls
succeed — this file has no knowledge of recognition, liveness, or
attendance logic, per the architecture rule in docs/websocket.md.
"""

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from api.dependencies.auth_dependency import get_auth_service, get_current_user_ws
from database.connection import get_database
from database.models.user_model import UserRole
from database.repositories.session_repository import SessionRepository
from database.repositories.user_repository import UserRepository
from services.auth_service import AuthService
from utils.logger import get_logger
from websocket.connection_manager import manager

logger = get_logger(__name__)

router = APIRouter(tags=["Real-Time"])


@router.websocket("/ws/attendance/{session_id}")
async def attendance_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
):
    # Dependencies aren't auto-injected on websocket routes the way they
    # are on HTTP routes when constructed manually like this, so we build
    # them directly from the same building blocks the HTTP dependencies use
    # (get_database, UserRepository, AuthService) — no duplicated logic,
    # just wired without Depends() since we need to reject BEFORE accept().
    db = get_database()
    auth_service: AuthService = get_auth_service(UserRepository(db))

    user = await get_current_user_ws(token, auth_service)
    if user is None:
        await websocket.close(code=4401)  # 4401: custom app code, mirrors HTTP 401
        return
    if user.role not in (UserRole.ADMIN, UserRole.TEACHER):
        # Students must not gain teacher-only attendance monitoring
        # privileges (spec section 5) — reject before accept().
        await websocket.close(code=4403)  # mirrors HTTP 403
        return

    session_repo = SessionRepository(db)
    session_doc = await session_repo.get_by_id(session_id)
    if session_doc is None:
        await websocket.close(code=4404)  # mirrors HTTP 404
        return

    await manager.connect(websocket, session_id)
    try:
        while True:
            # This endpoint is publish-only from the server's perspective —
            # we still need to await something to detect disconnects and
            # to allow the client to send lightweight pings if it wants to.
            # Any inbound message is simply ignored; nothing the client
            # sends here can affect attendance state (see architecture rule).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 — never let a socket error take down the manager
        logger.warning("WebSocket error on session %s: %s", session_id, exc)
    finally:
        await manager.disconnect(websocket, session_id)
        if websocket.application_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except Exception:  # noqa: BLE001
                pass
