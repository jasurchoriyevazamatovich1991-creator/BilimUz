"""
The shared SQLAlchemy declarative base. Every module's models.py imports
Base from here — nowhere else. alembic/env.py imports Base.metadata from
here too, so ORM models and migrations always agree on what "the schema"
means.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
