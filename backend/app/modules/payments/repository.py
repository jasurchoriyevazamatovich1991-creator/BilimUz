"""Data-access layer for Plan, Subscription, Payment, Transaction — four
repositories in one file, same cohesive-module reasoning as
questions/repository.py."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.payments.models import Payment, Plan, Subscription, Transaction


class PlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, plan_id: uuid.UUID) -> Plan | None:
        stmt = select(Plan).where(Plan.id == plan_id, Plan.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active(self) -> list[Plan]:
        stmt = select(Plan).where(Plan.status == "active", Plan.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def create(self, plan: Plan) -> Plan:
        self.db.add(plan)
        self.db.flush()
        return plan

    def commit(self) -> None:
        self.db.commit()


class SubscriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, subscription_id: uuid.UUID) -> Subscription | None:
        stmt = select(Subscription).where(Subscription.id == subscription_id, Subscription.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID) -> list[Subscription]:
        stmt = select(Subscription).where(Subscription.user_id == user_id, Subscription.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def create(self, subscription: Subscription) -> Subscription:
        self.db.add(subscription)
        self.db.flush()
        return subscription

    def commit(self) -> None:
        self.db.commit()


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        stmt = select(Payment).where(Payment.id == payment_id, Payment.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID, page: int, per_page: int) -> tuple[list[Payment], int]:
        stmt = select(Payment).where(Payment.user_id == user_id, Payment.deleted_at.is_(None))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Payment.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def create(self, payment: Payment) -> Payment:
        self.db.add(payment)
        self.db.flush()
        return payment

    def update_status(self, payment: Payment, status: str) -> None:
        payment.status = status
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()


class TransactionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_provider_txn_id(self, provider_txn_id: str) -> Transaction | None:
        """The service-layer half of idempotency (approved decision:
        BOTH this check AND a DB-level UNIQUE constraint — see migration
        0003). This check alone prevents the common case; the DB
        constraint closes the race-condition gap this check alone
        cannot (see providers.py / service.py docstrings)."""
        stmt = select(Transaction).where(Transaction.provider_txn_id == provider_txn_id, Transaction.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_payment(self, payment_id: uuid.UUID) -> list[Transaction]:
        stmt = select(Transaction).where(Transaction.payment_id == payment_id, Transaction.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def create(self, transaction: Transaction) -> Transaction:
        self.db.add(transaction)
        self.db.flush()
        return transaction

    def commit(self) -> None:
        self.db.commit()
