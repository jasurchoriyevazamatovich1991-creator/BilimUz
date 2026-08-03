"""Pydantic v2 request/response contracts for the payments module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.payments.validators import (
    validate_amount,
    validate_currency,
    validate_duration_days,
    validate_plan_name,
    validate_provider,
)


class PlanCreateRequest(BaseModel):
    name: str
    price: float
    duration_days: int
    features: dict | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_plan_name(v)

    @field_validator("price")
    @classmethod
    def _price(cls, v: float) -> float:
        return validate_amount(v)

    @field_validator("duration_days")
    @classmethod
    def _duration(cls, v: int) -> int:
        return validate_duration_days(v)


class PlanOut(BaseModel):
    id: uuid.UUID
    name: str
    price: float
    duration_days: int
    features: dict | None
    status: str

    model_config = {"from_attributes": True}


class SubscribeRequest(BaseModel):
    plan_id: uuid.UUID


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    plan_id: uuid.UUID
    start_date: datetime
    end_date: datetime
    status: str

    model_config = {"from_attributes": True}


class InitiatePaymentRequest(BaseModel):
    amount: float
    currency: str = "UZS"
    provider: str
    subscription_id: uuid.UUID | None = None

    @field_validator("amount")
    @classmethod
    def _amount(cls, v: float) -> float:
        return validate_amount(v)

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str) -> str:
        return validate_currency(v)

    @field_validator("provider")
    @classmethod
    def _provider(cls, v: str) -> str:
        return validate_provider(v)


class PaymentOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    subscription_id: uuid.UUID | None
    provider: str
    amount: float
    currency: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionOut(BaseModel):
    id: uuid.UUID
    payment_id: uuid.UUID
    provider_txn_id: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentDetailOut(PaymentOut):
    transactions: list[TransactionOut] = []


class PaymentListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class RefundResponseOut(BaseModel):
    payment_id: uuid.UUID
    status: str
    transaction: TransactionOut
