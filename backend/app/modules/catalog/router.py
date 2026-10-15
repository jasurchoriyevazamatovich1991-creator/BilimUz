"""
HTTP layer for /api/v1/catalog/products/*. ADMIN-ONLY for this phase —
deliberately. Public catalog browsing (spec §1 — "display all published
services... showing a catalog item does not grant access to its
protected content") and student-facing checkout are later phases; this
phase only needs admins to be able to configure products at all, which
is a prerequisite for everything after it. See module README.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.catalog.dependencies import get_catalog_product_service
from app.modules.catalog.schemas import (
    CatalogProductCreateRequest,
    CatalogProductListParams,
    CatalogProductOut,
    CatalogProductUpdateRequest,
)
from app.modules.catalog.service import CatalogProductService
from app.modules.users.models import User

router = APIRouter(prefix="/catalog/products", tags=["Catalog Products"])


@router.get(
    "",
    summary="List catalog products (Admin)",
    description="Paginated, searchable, filterable (by product_type, status) list. "
                "Admin/Super Admin only this phase — public catalog browsing is a later phase.",
)
def list_products(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    product_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="-created_at"),
    service: CatalogProductService = Depends(get_catalog_product_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    params = CatalogProductListParams(
        page=page, per_page=per_page, search=search, product_type=product_type, status=status_filter, sort=sort,
    )
    items, total = service.list_products(params)
    data = {
        "items": [CatalogProductOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Mahsulotlar ro'yxati.")


@router.get(
    "/{product_id}",
    summary="Get a catalog product (Admin)",
)
def get_product(
    product_id: uuid.UUID,
    service: CatalogProductService = Depends(get_catalog_product_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    product = service.get_product(product_id)
    return success_response(CatalogProductOut.model_validate(product), "Mahsulot topildi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a catalog product (Admin)",
    description="product_type determines which single ref field (grade_id for "
                "grade_subscription, subject_id for mock_test — the subject or exam "
                "direction, e.g. Physics or IELTS — neither for course) must be set — "
                "422 if the combination is inconsistent, 409 if that grade/subject "
                "already has a product.",
)
def create_product(
    data: CatalogProductCreateRequest,
    service: CatalogProductService = Depends(get_catalog_product_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    product = service.create_product(data, actor_id=admin.id)
    return success_response(CatalogProductOut.model_validate(product), "Mahsulot yaratildi.")


@router.patch(
    "/{product_id}",
    summary="Update a catalog product (Admin)",
    description="Updates name/price/duration_days/status. product_type and the grade/test "
                "reference are immutable after creation — changing what a product IS is a "
                "create-new operation, same rule as grades/subjects/roles.",
)
def update_product(
    product_id: uuid.UUID,
    data: CatalogProductUpdateRequest,
    service: CatalogProductService = Depends(get_catalog_product_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    product = service.update_product(product_id, data, actor_id=admin.id)
    return success_response(CatalogProductOut.model_validate(product), "Mahsulot yangilandi.")
