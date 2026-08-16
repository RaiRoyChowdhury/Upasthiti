"""
One-time bootstrap script: creates the first admin account.

Registration (POST /api/auth/register) is admin-only by design, so there has
to be a way to create the very first admin outside the API. Run this once
after the database is up.

Usage (from the backend/ directory, with the venv active):
    python scripts/create_admin.py
"""

import asyncio
import getpass
import sys
from pathlib import Path

# Allow running this script directly via `python scripts/create_admin.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError  # noqa: E402

from database.connection import connect_to_mongo, close_mongo_connection, get_database  # noqa: E402
from database.models.user_model import UserCreate, UserRole  # noqa: E402
from database.repositories.user_repository import UserRepository  # noqa: E402
from auth.security import hash_password  # noqa: E402


async def main() -> None:
    print("=== SmartAttend AI — Create Admin Account ===")

    while True:
        name = input("Full name: ").strip()
        email = input("Email (e.g. admin@example.com): ").strip()
        password = getpass.getpass("Password (min 8 chars): ")

        try:
            user_create = UserCreate(name=name, email=email, role=UserRole.ADMIN, password=password)
            break
        except ValidationError as exc:
            print("\nThat didn't pass validation:")
            for err in exc.errors():
                field = ".".join(str(p) for p in err["loc"])
                print(f"  - {field}: {err['msg']}")
            print("Let's try again.\n")

    await connect_to_mongo()
    try:
        repo = UserRepository(get_database())
        existing = await repo.get_by_email(user_create.email)
        if existing:
            print(f"A user with email '{user_create.email}' already exists. Aborting.")
            return

        password_hash = hash_password(user_create.password)
        doc = await repo.create(user_create, password_hash)
        print(f"Admin account created: {doc['email']} (id={doc['_id']})")
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(main())
