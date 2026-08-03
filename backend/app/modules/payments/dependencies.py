"""FastAPI dependency wiring for the payments module."""
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.payments.constants import ALLOWED_PROVIDERS
from app.modules.payments.providers import PaymentProvider, PaymentProviderRegistry, UnconfiguredPaymentProvider
from app.modules.payments.repository import PaymentRepository, PlanRepository, SubscriptionRepository, TransactionRepository
from app.modules.payments.service import PaymentService, PlanService, SubscriptionService


@lru_cache
def get_payment_provider_registry() -> PaymentProviderRegistry:
    """Every provider name resolves to the same UnconfiguredPaymentProvider
    this sprint — a future sprint replaces individual entries with real
    implementations, e.g. {'click': ClickProvider(), 'payme': UnconfiguredPaymentProvider()}."""
    unconfigured: PaymentProvider = UnconfiguredPaymentProvider()
    return PaymentProviderRegistry({name: unconfigured for name in ALLOWED_PROVIDERS})


def get_plan_repository(db: Session = Depends(get_db)) -> PlanRepository:
    return PlanRepository(db)


def get_plan_service(repo: PlanRepository = Depends(get_plan_repository)) -> PlanService:
    return PlanService(repo)


def get_subscription_repository(db: Session = Depends(get_db)) -> SubscriptionRepository:
    return SubscriptionRepository(db)


def get_subscription_service(
    repo: SubscriptionRepository = Depends(get_subscription_repository),
    plan_repo: PlanRepository = Depends(get_plan_repository),
) -> SubscriptionService:
    return SubscriptionService(repo, plan_repo)


def get_payment_repository(db: Session = Depends(get_db)) -> PaymentRepository:
    return PaymentRepository(db)


def get_transaction_repository(db: Session = Depends(get_db)) -> TransactionRepository:
    return TransactionRepository(db)


def get_payment_service(
    payment_repo: PaymentRepository = Depends(get_payment_repository),
    txn_repo: TransactionRepository = Depends(get_transaction_repository),
    registry: PaymentProviderRegistry = Depends(get_payment_provider_registry),
) -> PaymentService:
    return PaymentService(payment_repo, txn_repo, registry)
