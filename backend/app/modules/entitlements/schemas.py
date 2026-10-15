"""Pydantic v2 contracts for the entitlements module.

Grant/extend/revoke/admin-list/me now have a real HTTP router (Admin
Management of Mock Test Entitlements, Task D) — see router.py.
"""
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field, model_validator

from app.modules.entitlements.constants import MAX_DURATION_DAYS, MAX_REASON_LENGTH


class EntitlementOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    product_id: uuid.UUID
    source: str
    granted_by: uuid.UUID | None
    payment_id: uuid.UUID | None
    status: str
    start_date: datetime
    end_date: datetime | None
    reason: str | None
    created_at: datetime
    updated_at: datetime

    # --- Denormalized display fields (Task D) ---
    # Populated by the service, not by SQLAlchemy's from_attributes —
    # the ORM Entitlement row has no relationship() to CatalogProduct/
    # Subject/User (this module deliberately has no relationships; see
    # repository.py's enrichment query), so these are set explicitly in
    # service.py before the response leaves the service layer. This is
    # what satisfies spec §6 "avoid relying on frontend-only expiration
    # checks" together with `effective_status` below: the client never
    # has to compute or join anything to show a meaningful row.
    product_name: str
    product_type: str
    subject_id: uuid.UUID | None
    subject_name: str | None
    granted_by_name: str | None

    # Computed, not stored — see constants.py's EFFECTIVE_STATUS_*
    # docstring for why "scheduled" is never written to the DB.
    effective_status: str

    model_config = {"from_attributes": True}


class EntitlementGrantRequest(BaseModel):
    """Admin grants a Mock Test entitlement for one user + one
    subject/exam-direction catalog product (spec §2.3-5). Exactly one of
    `end_date` / `duration_days` may be given; neither means "no
    expiry" (mirrors CatalogProduct.duration_days=NULL semantics)."""

    user_id: uuid.UUID
    product_id: uuid.UUID
    start_date: datetime | None = Field(default=None, description="Defaults to now if omitted")
    end_date: datetime | None = None
    duration_days: int | None = Field(default=None, gt=0, le=MAX_DURATION_DAYS)
    reason: str | None = Field(default=None, max_length=MAX_REASON_LENGTH)

    @model_validator(mode="after")
    def _one_of_end_date_or_duration(self) -> "EntitlementGrantRequest":
        if self.end_date is not None and self.duration_days is not None:
            raise ValueError("end_date va duration_days bir vaqtda berilishi mumkin emas — faqat bittasini tanlang")
        effective_start = self.start_date or datetime.now(timezone.utc)
        if self.end_date is not None and self.end_date <= effective_start:
            raise ValueError("end_date start_date'dan keyin bo'lishi kerak")
        return self

    def resolve_end_date(self, effective_start: datetime) -> datetime | None:
        """duration_days is relative to the entitlement's own
        start_date (not "now") so a future-dated grant's validity
        window is exactly `duration_days` long starting when it
        actually begins, not shorter because days already elapsed
        between the grant call and the start date."""
        if self.duration_days is not None:
            return effective_start + timedelta(days=self.duration_days)
        return self.end_date


class EntitlementExtendRequest(BaseModel):
    """Extends (or reactivates, if the target row is expired/revoked)
    an existing entitlement's validity window (spec §2.6, §3 "safe
    extension/reactivation workflow"). Exactly one of `end_date` /
    `duration_days` must be given — unlike the grant request, "give
    neither" is not a valid extend (there is nothing to change)."""

    end_date: datetime | None = None
    duration_days: int | None = Field(default=None, gt=0, le=MAX_DURATION_DAYS)
    reason: str | None = Field(default=None, max_length=MAX_REASON_LENGTH)

    @model_validator(mode="after")
    def _exactly_one_of_end_date_or_duration(self) -> "EntitlementExtendRequest":
        if (self.end_date is None) == (self.duration_days is None):
            raise ValueError("end_date yoki duration_days'dan aynan bittasi berilishi shart")
        return self

    def resolve_end_date(self, from_date: datetime) -> datetime:
        if self.duration_days is not None:
            return from_date + timedelta(days=self.duration_days)
        assert self.end_date is not None
        return self.end_date


class EntitlementRevokeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=MAX_REASON_LENGTH)
