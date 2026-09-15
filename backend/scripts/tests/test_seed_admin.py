"""Sprint 39 — seed_admin.py tests.

seed_super_admin() takes `db` as a plain parameter specifically so it
can be exercised here with a mocked session — no real PostgreSQL
connection needed, matching this project's existing MagicMock-based
service test pattern. AuthRepository/RoleRepository are patched at the
scripts.seed_admin import site (not reimplemented) — this exercises
the real seed_super_admin() logic while replacing only the two
repository classes it constructs internally.

NOTE: this deliberately does NOT attempt a real PostgreSQL integration
test (out of Phase 2's explicit scope) — see the Sprint 39 Phase 2
report's "Tests" section for why.
"""
import uuid
from unittest.mock import MagicMock, patch

from scripts.seed_admin import seed_super_admin


def _strong_password() -> str:
    # Satisfies password_service.validate_password_strength(): 12+
    # chars, upper, lower, digit, special char, not a common weak password.
    return "Correct-Horse9!"


@patch("scripts.seed_admin.RoleRepository")
@patch("scripts.seed_admin.AuthRepository")
def test_creates_super_admin_when_none_exists(mock_auth_repo_cls, mock_role_repo_cls):
    mock_auth_repo = MagicMock()
    mock_role_repo = MagicMock()
    mock_auth_repo_cls.return_value = mock_auth_repo
    mock_role_repo_cls.return_value = mock_role_repo

    role_id = uuid.uuid4()
    mock_role_repo.get_by_name.return_value = MagicMock(id=role_id)
    mock_auth_repo.get_user_by_identifier.return_value = None
    db = MagicMock()

    success, message = seed_super_admin(db, "admin@example.com", _strong_password(), "Super", "Admin")

    assert success is True
    mock_auth_repo.create_user.assert_called_once()
    created_user = mock_auth_repo.create_user.call_args[0][0]
    assert created_user.email == "admin@example.com"
    assert created_user.role_id == role_id
    db.commit.assert_called_once()


def test_password_is_hashed_via_the_existing_password_service():
    """The created User's password_hash must never equal the plain
    password — confirms PasswordService.hash_password() was actually
    used, not a bypass."""
    with patch("scripts.seed_admin.RoleRepository") as mock_role_repo_cls, \
         patch("scripts.seed_admin.AuthRepository") as mock_auth_repo_cls:
        mock_auth_repo = MagicMock()
        mock_role_repo = MagicMock()
        mock_auth_repo_cls.return_value = mock_auth_repo
        mock_role_repo_cls.return_value = mock_role_repo
        mock_role_repo.get_by_name.return_value = MagicMock(id=uuid.uuid4())
        mock_auth_repo.get_user_by_identifier.return_value = None

        plain_password = _strong_password()
        seed_super_admin(MagicMock(), "admin@example.com", plain_password, "Super", "Admin")

        created_user = mock_auth_repo.create_user.call_args[0][0]
        assert created_user.password_hash != plain_password
        # Argon2 hashes always start with this prefix — confirms the
        # REAL PasswordService.hash_password() ran, not a stub.
        assert created_user.password_hash.startswith("$argon2")


@patch("scripts.seed_admin.RoleRepository")
@patch("scripts.seed_admin.AuthRepository")
def test_second_run_is_idempotent_no_duplicate_created(mock_auth_repo_cls, mock_role_repo_cls):
    mock_auth_repo = MagicMock()
    mock_role_repo = MagicMock()
    mock_auth_repo_cls.return_value = mock_auth_repo
    mock_role_repo_cls.return_value = mock_role_repo
    mock_role_repo.get_by_name.return_value = MagicMock(id=uuid.uuid4())
    # Simulates the second run — a Super Admin with this email already exists.
    mock_auth_repo.get_user_by_identifier.return_value = MagicMock(id=uuid.uuid4())

    success, message = seed_super_admin(MagicMock(), "admin@example.com", _strong_password(), "Super", "Admin")

    assert success is True
    assert "allaqachon mavjud" in message
    mock_auth_repo.create_user.assert_not_called()


@patch("scripts.seed_admin.RoleRepository")
@patch("scripts.seed_admin.AuthRepository")
def test_missing_super_admin_role_fails_without_creating_one(mock_auth_repo_cls, mock_role_repo_cls):
    """This script must never invent a new role — if 'Super Admin'
    doesn't exist in the target DB, it refuses and exits cleanly."""
    mock_auth_repo = MagicMock()
    mock_role_repo = MagicMock()
    mock_auth_repo_cls.return_value = mock_auth_repo
    mock_role_repo_cls.return_value = mock_role_repo
    mock_role_repo.get_by_name.return_value = None

    success, message = seed_super_admin(MagicMock(), "admin@example.com", _strong_password(), "Super", "Admin")

    assert success is False
    assert "roli" in message
    mock_auth_repo.create_user.assert_not_called()


@patch("scripts.seed_admin.RoleRepository")
@patch("scripts.seed_admin.AuthRepository")
def test_weak_password_is_rejected_before_any_db_write(mock_auth_repo_cls, mock_role_repo_cls):
    mock_auth_repo = MagicMock()
    mock_role_repo_cls.return_value = MagicMock()
    mock_auth_repo_cls.return_value = mock_auth_repo

    success, message = seed_super_admin(MagicMock(), "admin@example.com", "weak", "Super", "Admin")

    assert success is False
    mock_auth_repo.create_user.assert_not_called()


def test_credentials_come_from_environment_not_hardcoded():
    """main() reads SUPERADMIN_EMAIL/SUPERADMIN_PASSWORD from os.environ
    — this test confirms main() returns a clean failure (not a crash)
    when they're absent, which is only possible if it's actually
    reading from the environment rather than a hardcoded fallback."""
    import os
    from scripts.seed_admin import main

    env_backup = {k: os.environ.pop(k, None) for k in ("SUPERADMIN_EMAIL", "SUPERADMIN_PASSWORD")}
    try:
        exit_code = main()
        assert exit_code == 1
    finally:
        for k, v in env_backup.items():
            if v is not None:
                os.environ[k] = v
