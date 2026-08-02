"""
DailyStatistics, MonthlyStatistics ORM models — mirror `daily_statistics`,
`monthly_statistics` tables in schema_v2.sql (Module 20).

Neither table has created_by/updated_by (verified against schema_v2.sql)
— no AuditMixin.
"""
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class DailyStatistics(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "daily_statistics"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    tests_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wrong_answers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class MonthlyStatistics(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "monthly_statistics"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tests_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
