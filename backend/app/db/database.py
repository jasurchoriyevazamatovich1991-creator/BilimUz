"""
SQLAlchemy engine — connection pooling lives here, and only here.
Split out from the old core/database.py (which mixed engine + Base + session
in one file) so each file has exactly one responsibility, per
.cursor/rules/01-coding-standards.md.
"""
from sqlalchemy import create_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # drops dead connections instead of raising mid-request
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)
