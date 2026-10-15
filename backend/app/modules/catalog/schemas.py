"""Pydantic v2 request/response contracts for the catalog module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.catalog.constants import (
    ALLOWED_PRODUCT_STATUS_VALUES,
    ALLOWED_PRODUCT_TYPES,
    DEFAULT_SORT_FIELD,
    PRODUCT_TYPE_GRADE_SUBSCRIPTION,
    PRODUCT_TYPE_MOCK_TEST,
)
from app.modules.catalog.validators import validate_duration_days, validate_price, validate_product_name


class CatalogProductCreateRequest(BaseModel):
    product_type: str = Field(..., examples=["grade_subscription"])
    grade_id: uuid.UUID | None = Field(default=None, description="Required when product_type='grade_subscription'")
    subject_id: uuid.UUID | None = Field(
        default=None,
        description="Required when product_type='mock_test' — the subject or exam direction "
                    "(e.g. Physics, or IELTS) this product grants access to every published mock test under.",
    )
    name: str = Field(..., examples=["3-sinf obunasi"])
    price: float = Field(..., examples=[150000])
    duration_days: int | None = Field(default=None, description="NULL = no expiry (lifetime unlock)")

    @field_validator("product_type")
    @classmethod
    def _product_type(cls, v: str) -> str:
        if v not in ALLOWED_PRODUCT_TYPES:
            raise ValueError(f"product_type quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_PRODUCT_TYPES)}")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_product_name(v)

    @field_validator("price")
    @classmethod
    def _price(cls, v: float) -> float:
        return validate_price(v)

    @field_validator("duration_days")
    @classmethod
    def _duration_days(cls, v: int | None) -> int | None:
        return validate_duration_days(v)

    @model_validator(mode="after")
    def _ref_matches_type(self) -> "CatalogProductCreateRequest":
        """Mirrors the DB CHECK constraint (ck_catalog_products_ref_matches_type)
        so a malformed request fails fast with a clear 422 instead of
        falling through to a raw IntegrityError."""
        if self.product_type == PRODUCT_TYPE_GRADE_SUBSCRIPTION:
            if self.grade_id is None or self.subject_id is not None:
                raise ValueError("grade_subscription uchun faqat grade_id ko'rsatilishi kerak")
        elif self.product_type == PRODUCT_TYPE_MOCK_TEST:
            if self.subject_id is None or self.grade_id is not None:
                raise ValueError("mock_test uchun faqat subject_id (fan/yo'nalish) ko'rsatilishi kerak")
        else:  # course
            if self.grade_id is not None or self.subject_id is not None:
                raise ValueError("course uchun grade_id yoki subject_id ko'rsatilmasligi kerak")
        return self


class CatalogProductUpdateRequest(BaseModel):
    """product_type/grade_id/test_id are intentionally NOT updatable —
    same immutability rule grades/subjects/roles already apply to their
    own identity-defining fields. Changing what a product IS (rather
    than its price/name/status) is a create-new operation."""
    name: str | None = None
    price: float | None = None
    duration_days: int | None = None
    status: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return validate_product_name(v) if v is not None else v

    @field_validator("price")
    @classmethod
    def _price(cls, v: float | None) -> float | None:
        return validate_price(v) if v is not None else v

    @field_validator("duration_days")
    @classmethod
    def _duration_days(cls, v: int | None) -> int | None:
        return validate_duration_days(v)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_PRODUCT_STATUS_VALUES:
            raise ValueError(f"status quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_PRODUCT_STATUS_VALUES)}")
        return v


class CatalogProductOut(BaseModel):
    id: uuid.UUID
    product_type: str
    grade_id: uuid.UUID | None
    subject_id: uuid.UUID | None
    name: str
    price: float
    duration_days: int | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CatalogProductListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: str | None = None
    product_type: str | None = None
    status: str | None = None
    sort: str = DEFAULT_SORT_FIELD
