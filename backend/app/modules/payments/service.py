"""
Business logic for plans, subscriptions, payment initiation, webhook
handling, and refunds. Idempotency is enforced at TWO layers (approved
decision): a check-then-insert lookup here (handles the common case
cheaply) AND the database's UNIQUE constraint on
transactions.provider_txn_id (migration 0003, closes the race-condition
gap a check-then-insert alone cannot — two concurrent webhook deliveries
could both pass the check before either commits; the DB constraint makes
the second one fail atomically instead of silently duplicating).
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.core.audit import log_action
from app.modules.payments.exceptions import (
    PaymentAlreadyRefundedException,
    PaymentNotFoundException,
    PaymentNotRefundableException,
    PlanNotFoundException,
)
from app.modules.payments.models import Payment, Plan, Subscription, Transaction
from app.modules.payments.providers import PaymentProviderRegistry
from app.modules.payments.repository import PaymentRepository, PlanRepository, SubscriptionRepository, TransactionRepository
from app.modules.payments.schemas import InitiatePaymentRequest, PlanCreateRequest


class PlanService:
    def __init__(self, repository: PlanRepository):
        self.repo = repository

    def create(self, data: PlanCreateRequest, actor_id: uuid.UUID) -> Plan:
        plan = Plan(name=data.name, price=data.price, duration_days=data.duration_days, features=data.features, created_by=actor_id)
        self.repo.create(plan)
        self.repo.commit()
        return plan

    def list_active(self) -> list[Plan]:
        return self.repo.list_active()

    def get(self, plan_id: uuid.UUID) -> Plan:
        plan = self.repo.get_by_id(plan_id)
        if plan is None:
            raise PlanNotFoundException("Reja topilmadi")
        return plan


class SubscriptionService:
    def __init__(self, repository: SubscriptionRepository, plan_repository: PlanRepository):
        self.repo = repository
        self.plan_repo = plan_repository

    def subscribe(self, plan_id: uuid.UUID, user_id: uuid.UUID) -> Subscription:
        plan = self.plan_repo.get_by_id(plan_id)
        if plan is None:
            raise PlanNotFoundException("Reja topilmadi")

        now = datetime.now(timezone.utc)
        subscription = Subscription(
            user_id=user_id, plan_id=plan_id, start_date=now,
            end_date=now + timedelta(days=plan.duration_days), status="active",
        )
        self.repo.create(subscription)
        log_action(self.repo.db, action="subscription.created", user_id=user_id, entity_type="subscription", entity_id=subscription.id)
        self.repo.commit()
        return subscription

    def list_mine(self, user_id: uuid.UUID) -> list[Subscription]:
        return self.repo.list_for_user(user_id)


class PaymentService:
    def __init__(
        self,
        payment_repository: PaymentRepository,
        transaction_repository: TransactionRepository,
        provider_registry: PaymentProviderRegistry,
    ):
        self.payment_repo = payment_repository
        self.txn_repo = transaction_repository
        self.registry = provider_registry

    def initiate(self, data: InitiatePaymentRequest, user_id: uuid.UUID):
        payment = Payment(
            user_id=user_id, subscription_id=data.subscription_id,
            provider=data.provider, amount=data.amount, currency=data.currency, status="pending",
        )
        self.payment_repo.create(payment)
        log_action(self.payment_repo.db, action="payment.initiated", user_id=user_id, entity_type="payment", entity_id=payment.id)
        self.payment_repo.commit()

        provider = self.registry.get(data.provider)
        return payment, provider.initiate(data.amount, data.currency, str(payment.id))  # raises if not configured

    def get(self, payment_id: uuid.UUID, user_id: uuid.UUID) -> Payment:
        payment = self.payment_repo.get_by_id(payment_id)
        if payment is None or payment.user_id != user_id:
            raise PaymentNotFoundException("To'lov topilmadi")
        return payment

    def list_mine(self, user_id: uuid.UUID, page: int, per_page: int) -> tuple[list[Payment], int]:
        return self.payment_repo.list_for_user(user_id, page, per_page)

    def list_transactions(self, payment_id: uuid.UUID) -> list[Transaction]:
        return self.txn_repo.list_for_payment(payment_id)

    def handle_webhook(self, provider_name: str, raw_body: bytes, headers: dict) -> Transaction:
        provider = self.registry.get(provider_name)
        result = provider.verify_webhook(raw_body, headers)  # raises if not configured/invalid

        existing = self.txn_repo.get_by_provider_txn_id(result.provider_txn_id)
        if existing:
            return existing  # idempotent acknowledgment — no duplicate processing

        payment = self.payment_repo.get_by_id(uuid.UUID(result.payment_id))
        if payment is None:
            raise PaymentNotFoundException("Webhook'da ko'rsatilgan to'lov topilmadi")

        try:
            transaction = self.txn_repo.create(Transaction(
                payment_id=payment.id, provider_txn_id=result.provider_txn_id,
                raw_response=result.raw_payload, status="recorded",
            ))
            self.payment_repo.update_status(payment, "success" if result.is_success else "failed")
            log_action(self.payment_repo.db, action="payment.webhook_received", entity_type="payment", entity_id=payment.id)
            self.txn_repo.commit()
            return transaction
        except IntegrityError:
            # DB-level UNIQUE constraint (migration 0003) caught a race
            # the check-then-insert above couldn't — another concurrent
            # webhook delivery won. Acknowledge idempotently, don't crash.
            self.txn_repo.db.rollback()
            return self.txn_repo.get_by_provider_txn_id(result.provider_txn_id)

    def refund(self, payment_id: uuid.UUID, actor_id: uuid.UUID) -> Transaction:
        payment = self.payment_repo.get_by_id(payment_id)
        if payment is None:
            raise PaymentNotFoundException("To'lov topilmadi")
        if payment.status == "refunded":
            raise PaymentAlreadyRefundedException("Bu to'lov allaqachon qaytarilgan")
        if payment.status != "success":
            raise PaymentNotRefundableException("Faqat muvaffaqiyatli to'lovni qaytarish mumkin")

        provider = self.registry.get(payment.provider)
        existing_txn = self._latest_provider_txn_id(payment.id)
        result = provider.refund(existing_txn, float(payment.amount))  # raises if not configured

        transaction = self.txn_repo.create(Transaction(
            payment_id=payment.id, provider_txn_id=result.provider_refund_reference,
            raw_response=result.raw_payload, status="refund_recorded",
        ))
        self.payment_repo.update_status(payment, "refunded")
        log_action(self.payment_repo.db, action="payment.refunded", user_id=actor_id, entity_type="payment", entity_id=payment.id)
        self.txn_repo.commit()
        return transaction

    def _latest_provider_txn_id(self, payment_id: uuid.UUID) -> str:
        transactions = self.txn_repo.list_for_payment(payment_id)
        recorded = [t for t in transactions if t.status == "recorded" and t.provider_txn_id]
        return recorded[-1].provider_txn_id if recorded else ""
