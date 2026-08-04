"""
Alembic environment. Reads DATABASE_URL from app.core.config (the same
Settings the FastAPI app uses) instead of alembic.ini, so there is one
source of truth.

IMPORTANT: target_metadata currently only reflects models that exist
(users, roles, auth, subjects — see docs/CHANGELOG.md for what's built).
Running --autogenerate today would propose DROPping every table that
has a real model missing (the other 21 modules, schema-only for now).
Do not run --autogenerate until a module's models.py is written — until
then, write migrations by hand (see 0001_initial_schema.py for the
pattern: wrapping raw SQL for tables without ORM models yet).
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base

# Import every module's models so Base.metadata knows about their tables.
# Add a line here EVERY TIME a new module gets a models.py — otherwise
# autogenerate silently ignores it.
from app.modules.ai import models as ai_models  # noqa: F401
from app.modules.analytics import models as analytics_models  # noqa: F401
from app.modules.attempts import models as attempts_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.certificates import models as certificates_models  # noqa: F401
from app.modules.grades import models as grades_models  # noqa: F401
from app.modules.learning_centers import models as learning_centers_models  # noqa: F401
from app.modules.lessons import models as lessons_models  # noqa: F401
from app.modules.notifications import models as notifications_models  # noqa: F401
from app.modules.payments import models as payments_models  # noqa: F401
from app.modules.permissions import models as permissions_models  # noqa: F401
from app.modules.profiles import models as profiles_models  # noqa: F401
from app.modules.questions import models as questions_models  # noqa: F401
from app.modules.results import models as results_models  # noqa: F401
from app.modules.roles import models as roles_models  # noqa: F401
from app.modules.schools import models as schools_models  # noqa: F401
from app.modules.settings import models as settings_models  # noqa: F401
from app.modules.subjects import models as subjects_models  # noqa: F401
from app.modules.tests import models as tests_models  # noqa: F401
from app.modules.topics import models as topics_models  # noqa: F401
from app.modules.uploads import models as uploads_models  # noqa: F401
from app.modules.users import models as users_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generates SQL scripts without a live DB connection (`alembic upgrade --sql`)."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Normal path: connects to the real database and applies migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
