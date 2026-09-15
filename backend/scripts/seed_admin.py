#!/usr/bin/env python3
"""
Sprint 39 — First Super Admin seed.

Idempotent CLI script: creates the platform's first Super Admin user
ONLY if no user already exists with the given identifier. Running it
twice never creates a duplicate — the second run is a no-op that exits
successfully.

Reuses the existing architecture entirely — no new DB connection
pattern, no new password hashing, no new role. This script only wires
together things that already exist: SessionLocal (app/db/session.py),
PasswordService (app/core/security/password_service.py),
AuthRepository.get_user_by_identifier()/create_user()
(app/modules/auth/repository.py), and RoleRepository.get_by_name()
(app/modules/roles/repository.py).

USAGE
-----
Run from the `backend/` directory, with a working DATABASE_URL (real
PostgreSQL — never run against a production database without first
confirming the target environment):

    SUPERADMIN_EMAIL=admin@example.com \
    SUPERADMIN_PASSWORD=YOUR_STRONG_PASSWORD \
    python scripts/seed_admin.py

Optional:
    SUPERADMIN_FIRST_NAME (default: "Super")
    SUPERADMIN_LAST_NAME  (default: "Admin")

SAFETY
------
- Never deletes or modifies any existing user, role, or permission.
- Runs no migrations — `alembic upgrade head` must already have been
  applied separately (this script does not do it for you).
- Credentials are read from environment variables ONLY. Never
  hardcoded here, never printed, never logged — only a success/failure
  message and the identifier (email) are ever written to stdout/stderr.
- Reuses the EXISTING "Super Admin" system role. If that role does not
  exist yet in the target database, this script refuses to run rather
  than inventing one — the role must already have been created through
  the normal roles/permissions setup path.
- On any error, the transaction is rolled back before exiting; no
  partial user row is ever left committed.
"""
import os
import sys

from app.core.security.password_service import PasswordService
from app.db.session import SessionLocal
from app.modules.auth.repository import AuthRepository
from app.modules.roles.repository import RoleRepository
from app.modules.users.models import User, UserStatus

SUPER_ADMIN_ROLE_NAME = "Super Admin"


def seed_super_admin(db, email: str, password: str, first_name: str, last_name: str) -> tuple[bool, str]:
    """Core logic, separated from main() so it can be exercised with a
    mocked `db`/repositories in tests without a real database connection.
    Returns (success, message) — never raises for expected conditions
    (missing role, already exists); only a genuinely unexpected DB error
    propagates, which main() catches and rolls back."""
    password_service = PasswordService()
    validation = password_service.validate_password_strength(password)
    if not validation.is_valid:
        reasons = "; ".join(e.message for e in validation.errors)
        return False, f"SUPERADMIN_PASSWORD platformaning parol talablariga javob bermaydi: {reasons}"

    auth_repo = AuthRepository(db)
    role_repo = RoleRepository(db)

    role = role_repo.get_by_name(SUPER_ADMIN_ROLE_NAME)
    if role is None:
        return False, (
            f"'{SUPER_ADMIN_ROLE_NAME}' roli bazada topilmadi. Avval mavjud rol/permission "
            "sozlash jarayonini bajaring — bu skript yangi rol yaratmaydi."
        )

    existing = auth_repo.get_user_by_identifier(email)
    if existing is not None:
        return True, f"Super Admin allaqachon mavjud (email: {email}) — hech narsa o'zgartirilmadi."

    user = User(
        role_id=role.id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=password_service.hash_password(password),
        # PENDING_VERIFICATION (the model's own default) would block
        # login through the normal auth flow — the first Super Admin
        # must be able to sign in immediately.
        status=UserStatus.ACTIVE,
    )
    auth_repo.create_user(user)
    db.commit()
    return True, f"✅ Super Admin muvaffaqiyatli yaratildi (email: {email})."


def main() -> int:
    email = os.environ.get("SUPERADMIN_EMAIL")
    password = os.environ.get("SUPERADMIN_PASSWORD")
    first_name = os.environ.get("SUPERADMIN_FIRST_NAME", "Super")
    last_name = os.environ.get("SUPERADMIN_LAST_NAME", "Admin")

    if not email or not password:
        print(
            "XATO: SUPERADMIN_EMAIL va SUPERADMIN_PASSWORD environment "
            "o'zgaruvchilari o'rnatilishi shart.",
            file=sys.stderr,
        )
        return 1

    db = SessionLocal()
    try:
        success, message = seed_super_admin(db, email, password, first_name, last_name)
        print(message if success else message, file=sys.stdout if success else sys.stderr)
        return 0 if success else 1
    except Exception as exc:  # noqa: BLE001 — this is a CLI entrypoint; any failure must roll back and exit cleanly, not crash with a raw traceback
        db.rollback()
        print(f"XATO: seed muvaffaqiyatsiz tugadi — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
