"""Business logic for catalog product management.

Scope for this phase (deliberately narrow — see module README): admin
create/update/list/get for CatalogProduct only. No public catalog
listing, no checkout, no provider integration here — those are later
phases.
"""
import uuid

from app.core.audit import log_action
from app.modules.catalog.exceptions import (
    CatalogProductAlreadyExistsException,
    CatalogProductNotFoundException,
    InvalidGradeReferenceException,
    InvalidSubjectReferenceException,
)
from app.modules.catalog.models import CatalogProduct
from app.modules.catalog.repository import CatalogProductRepository
from app.modules.catalog.schemas import CatalogProductCreateRequest, CatalogProductListParams, CatalogProductUpdateRequest
from app.modules.catalog.constants import PRODUCT_TYPE_GRADE_SUBSCRIPTION, PRODUCT_TYPE_MOCK_TEST


class CatalogProductService:
    def __init__(self, repository: CatalogProductRepository):
        self.repo = repository

    def get_product(self, product_id: uuid.UUID) -> CatalogProduct:
        product = self.repo.get_by_id(product_id)
        if product is None:
            raise CatalogProductNotFoundException("Mahsulot topilmadi")
        return product

    def list_products(self, params: CatalogProductListParams) -> tuple[list[CatalogProduct], int]:
        return self.repo.list(params)

    def create_product(self, data: CatalogProductCreateRequest, actor_id: uuid.UUID) -> CatalogProduct:
        # Schema-level model_validator already rejected an inconsistent
        # ref/product_type combination; these checks confirm the ref
        # actually POINTS AT something real before we insert (the plain
        # UNIQUE constraint on grade_id/test_id — see models.py — is
        # the DB-level backstop for the duplicate-product check below).
        if data.product_type == PRODUCT_TYPE_GRADE_SUBSCRIPTION:
            if not self.repo.grade_exists(data.grade_id):
                raise InvalidGradeReferenceException("Ko'rsatilgan sinf/daraja mavjud emas")
            if self.repo.get_by_grade_id(data.grade_id) is not None:
                raise CatalogProductAlreadyExistsException("Bu sinf uchun mahsulot allaqachon mavjud")
        elif data.product_type == PRODUCT_TYPE_MOCK_TEST:
            if not self.repo.subject_exists(data.subject_id):
                raise InvalidSubjectReferenceException("Ko'rsatilgan fan/yo'nalish mavjud emas")
            if self.repo.get_by_subject_id(data.subject_id) is not None:
                raise CatalogProductAlreadyExistsException("Bu fan/yo'nalish uchun mahsulot allaqachon mavjud")

        product = CatalogProduct(
            product_type=data.product_type,
            grade_id=data.grade_id,
            subject_id=data.subject_id,
            name=data.name,
            price=data.price,
            duration_days=data.duration_days,
            created_by=actor_id,
        )
        self.repo.create(product)
        log_action(
            self.repo.db, action="catalog_product.created", user_id=actor_id,
            entity_type="catalog_product", entity_id=product.id,
            metadata={"product_type": product.product_type},
        )
        self.repo.commit()
        return product

    def update_product(self, product_id: uuid.UUID, data: CatalogProductUpdateRequest, actor_id: uuid.UUID) -> CatalogProduct:
        product = self.get_product(product_id)
        updates = data.model_dump(exclude_unset=True)
        updates["updated_by"] = actor_id
        self.repo.update(product, updates)
        log_action(
            self.repo.db, action="catalog_product.updated", user_id=actor_id,
            entity_type="catalog_product", entity_id=product_id,
            metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return product
