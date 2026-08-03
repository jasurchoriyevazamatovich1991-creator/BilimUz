"""
Plan, Subscription, Payment, Transaction ORM models — mirror `plans`,
`subscriptions`, `payments`, `transactions` tables in schema_v2.sql
(Module 18).

Only Plan has created_by/updated_by (verified against schema_v2.sql) —
AuditMixin used selectively. `StatusMixin` is used ONLY for Plan
(generic 'active' status) — Subscription/Payment/Transaction each have
their OWN domain-specific status (subscription_status enum,
payment_status enum, transactions' own 'recorded'/etc. status), so per
StatusMixin's own documented rule, none of the three use it — same
lesson already applied correctly in the notifications module this sprint.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class Plan(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    duration_days: Mapped[int] = mapped_column(nullable=False)
    features: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Subscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """No StatusMixin — `status` is the domain-specific subscription_status
    enum (active/expired/cancelled), not the generic lifecycle status."""
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """No StatusMixin — `status` is the domain-specific payment_status
    enum (pending/success/failed/refunded/cancelled)."""
    __tablename__ = "payments"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="UZS")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")


class Transaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """No StatusMixin — `status` is transactions' own event-record status
    (e.g. 'recorded', 'refund_recorded'), a different vocabulary from
    Payment.status."""
    __tablename__ = "transactions"

    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False)
    provider_txn_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="recorded")
