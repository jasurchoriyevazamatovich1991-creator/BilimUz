"""
HTTP layer for /api/v1/payments/*. The webhook endpoint is deliberately
public (no Bearer token) — trust comes from provider signature
verification inside PaymentProvider.verify_webhook(), not from a user
session. This is why UnconfiguredPaymentProvider (which refuses
everything) is the SAFE default: it never accepts an unverified webhook.
"""
import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.payments.dependencies import get_payment_service, get_plan_service, get_subscription_service
from app.modules.payments.schemas import (
    InitiatePaymentRequest,
    PaymentDetailOut,
    PaymentOut,
    PlanCreateRequest,
    PlanOut,
    RefundResponseOut,
    SubscribeRequest,
    SubscriptionOut,
    TransactionOut,
)
from app.modules.payments.service import PaymentService, PlanService, SubscriptionService
from app.modules.users.models import User

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("/plans", summary="List active subscription plans")
def list_plans(service: PlanService = Depends(get_plan_service)):
    plans = service.list_active()
    return success_response([PlanOut.model_validate(p) for p in plans], "Rejalar.")


@router.post("/plans", status_code=status.HTTP_201_CREATED, summary="Create a subscription plan")
def create_plan(
    data: PlanCreateRequest,
    service: PlanService = Depends(get_plan_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    plan = service.create(data, actor_id=admin.id)
    return success_response(PlanOut.model_validate(plan), "Reja yaratildi.")


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED, summary="Subscribe to a plan")
def subscribe(
    data: SubscribeRequest,
    service: SubscriptionService = Depends(get_subscription_service),
    user: User = Depends(get_current_user),
):
    subscription = service.subscribe(data.plan_id, user.id)
    return success_response(SubscriptionOut.model_validate(subscription), "Obuna yaratildi.")


@router.get("/subscriptions/me", summary="My subscriptions")
def list_my_subscriptions(
    service: SubscriptionService = Depends(get_subscription_service),
    user: User = Depends(get_current_user),
):
    items = service.list_mine(user.id)
    return success_response([SubscriptionOut.model_validate(i) for i in items], "Mening obunalarim.")


@router.post(
    "/initiate",
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a payment",
    description="Creates a 'pending' payment, then calls the provider to start the flow. "
                "501 Not Implemented — no real payment provider is configured this sprint "
                "(approved scope boundary: provider abstraction only). The payment row is still created.",
)
def initiate_payment(
    data: InitiatePaymentRequest,
    service: PaymentService = Depends(get_payment_service),
    user: User = Depends(get_current_user),
):
    payment, _init_result = service.initiate(data, user.id)
    return success_response(PaymentOut.model_validate(payment), "To'lov boshlandi.")


@router.get("/me", summary="My payment history")
def list_my_payments(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    service: PaymentService = Depends(get_payment_service),
    user: User = Depends(get_current_user),
):
    items, total = service.list_mine(user.id, page, per_page)
    data = {
        "items": [PaymentOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "To'lovlarim.")


@router.get("/{payment_id}", summary="Get a payment with its transactions")
def get_payment(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service),
    user: User = Depends(get_current_user),
):
    payment = service.get(payment_id, user.id)
    transactions = service.list_transactions(payment_id)
    detail = PaymentDetailOut(**PaymentOut.model_validate(payment).model_dump(), transactions=[TransactionOut.model_validate(t) for t in transactions])
    return success_response(detail, "To'lov.")


@router.post(
    "/webhook/{provider}",
    summary="Provider webhook callback",
    description="PUBLIC — no Bearer token. Trust comes from provider signature verification inside "
                "PaymentProvider.verify_webhook(). Idempotent: a duplicate provider_txn_id is "
                "acknowledged without reprocessing. 501 this sprint (no real provider configured).",
)
async def payment_webhook(
    provider: str,
    request: Request,
    service: PaymentService = Depends(get_payment_service),
):
    raw_body = await request.body()
    transaction = service.handle_webhook(provider, raw_body, dict(request.headers))
    return success_response(TransactionOut.model_validate(transaction), "Webhook qabul qilindi.")


@router.post(
    "/{payment_id}/refund",
    summary="Refund a payment",
    description="Full-amount refunds only (approved scope). 409 if not a 'success' payment or "
                "already refunded. 501 this sprint (no real provider configured).",
)
def refund_payment(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    transaction = service.refund(payment_id, actor_id=admin.id)
    response = RefundResponseOut(payment_id=payment_id, status="refunded", transaction=TransactionOut.model_validate(transaction))
    return success_response(response, "To'lov qaytarildi.")
