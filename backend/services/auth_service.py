"""
Auth service: business logic for authentication.

Routes call this. This calls the repository. This never touches Mongo
directly and never returns a password_hash to its caller.
"""

from database.models.user_model import UserAdminUpdate, UserCreate, UserInDB, UserPublic
from database.repositories.user_repository import UserRepository
from auth.security import create_access_token, hash_password, verify_password
from utils.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationAppError
from utils.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self._users = user_repository

    async def register_user(self, user_create: UserCreate) -> UserPublic:
        existing = await self._users.get_by_email(user_create.email)
        if existing:
            raise ConflictError("A user with this email already exists.", code="EMAIL_TAKEN")

        password_hash = hash_password(user_create.password)
        doc = await self._users.create(user_create, password_hash)
        logger.info("User created: %s (role=%s)", doc["email"], doc["role"])
        return UserPublic.from_db(doc)

    async def authenticate(self, email: str, password: str) -> tuple[str, UserPublic]:
        doc = await self._users.get_by_email(email)
        if not doc or not verify_password(password, doc["password_hash"]):
            # Deliberately identical error for "no such user" and "wrong password"
            # so the API doesn't leak which emails are registered.
            raise UnauthorizedError("Invalid email or password.", code="INVALID_CREDENTIALS")

        if not doc.get("is_active", True):
            raise UnauthorizedError("This account has been deactivated.", code="ACCOUNT_INACTIVE")

        token = create_access_token(subject=str(doc["_id"]), extra_claims={"role": doc["role"]})
        return token, UserPublic.from_db(doc)

    async def get_public_user(self, user_id: str) -> UserPublic | None:
        doc = await self._users.get_by_id(user_id)
        if not doc:
            return None
        return UserPublic.from_db(doc)

    async def list_users(self, skip: int = 0, limit: int = 100) -> tuple[list[UserPublic], int]:
        docs, total = await self._users.list_users(skip=skip, limit=limit)
        return [UserPublic.from_db(d) for d in docs], total

    async def admin_update_user(
        self, user_id: str, updates: UserAdminUpdate, actor_id: str
    ) -> UserPublic:
        if user_id == actor_id and updates.is_active is False:
            raise ValidationAppError("You cannot deactivate your own account.", code="CANNOT_DEACTIVATE_SELF")

        target = await self._users.get_by_id(user_id)
        if not target:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")

        update_dict = updates.model_dump(exclude_unset=True)
        if "role" in update_dict and update_dict["role"] is not None:
            update_dict["role"] = update_dict["role"].value

        doc = await self._users.update_admin_fields(user_id, update_dict)
        logger.info("User %s updated by admin %s: %s", user_id, actor_id, list(update_dict.keys()))
        return UserPublic.from_db(doc)
