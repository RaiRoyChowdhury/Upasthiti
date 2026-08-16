"""
Shared FastAPI dependencies for authentication and authorization.

require_role(...) is the single mechanism every protected route uses to
enforce RBAC — this keeps "who is allowed to do this" declared at the route
signature instead of scattered through business logic.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from auth.security import JWTError, decode_access_token
from database.connection import get_database
from database.models.user_model import UserPublic, UserRole
from database.repositories.user_repository import UserRepository
from services.auth_service import AuthService
from utils.exceptions import ForbiddenError, UnauthorizedError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_user_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> UserRepository:
    return UserRepository(db)


def get_auth_service(repo: UserRepository = Depends(get_user_repository)) -> AuthService:
    return AuthService(repo)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserPublic:
    if not token:
        raise UnauthorizedError("Not authenticated.", code="NOT_AUTHENTICATED")

    try:
        payload = decode_access_token(token)
    except JWTError:
        raise UnauthorizedError("Invalid or expired token.", code="INVALID_TOKEN")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload.", code="INVALID_TOKEN")

    user = await auth_service.get_public_user(user_id)
    if not user:
        raise UnauthorizedError("User no longer exists.", code="USER_NOT_FOUND")
    if not user.is_active:
        raise UnauthorizedError("This account has been deactivated.", code="ACCOUNT_INACTIVE")

    return user


def require_role(*allowed_roles: UserRole):
    """
    Usage: current_user: UserPublic = Depends(require_role(UserRole.ADMIN))

    All attendance-relevant *decisions* (recognition result, liveness pass/fail,
    attendance allowed/duplicate/status) are made server-side in later phases —
    this dependency is the same principle applied to authorization: the
    frontend never decides who is allowed to do what, the server does.
    """

    async def _check(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if current_user.role not in allowed_roles:
            raise ForbiddenError(
                f"This action requires one of the following roles: "
                f"{', '.join(r.value for r in allowed_roles)}.",
                code="INSUFFICIENT_ROLE",
            )
        return current_user

    return _check


async def get_current_user_ws(token: str | None, auth_service: AuthService) -> UserPublic | None:
    """
    WebSocket variant of get_current_user.

    Browsers cannot set custom headers on a native WebSocket handshake, so
    the JWT travels as a query parameter (?token=...) instead of an
    Authorization header. This is the standard, documented workaround for
    browser WebSocket auth — see docs/websocket.md "Authentication".

    Returns None instead of raising, so the caller (the WS route) can
    close the connection with a proper WebSocket close code rather than an
    HTTP exception, which doesn't apply once the handshake is in progress.
    """
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except JWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = await auth_service.get_public_user(user_id)
    if not user or not user.is_active:
        return None
    return user
