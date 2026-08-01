"""Grade ORM model — mirrors `grades` table in schema_v2.sql (Module 8).
Represents a curriculum level (e.g. '5-sinf', 'Attestatsiya', 'Abituriyent')
that Topics and Tests can optionally be scoped to."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class Grade(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "grades"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
