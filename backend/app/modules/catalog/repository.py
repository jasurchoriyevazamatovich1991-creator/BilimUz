"""Data-access layer. Only SQLAlchemy here — no business rules.

Grade/Subject existence checks import those modules' ORM models
directly (read-only, single EXISTS-style query) — the same
one-directional cross-module pattern the roles module already uses
against users (roles/repository.py's own docstring: "a deliberate,
one-directional dependency... not a violation of module isolation,
since it doesn't import the other module's service or repository, only
its ORM model").
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.catalog.models import CatalogProduct
from app.modules.catalog.schemas import CatalogProductListParams
from app.modules.grades.models import Grade
from app.modules.subjects.models import Subject
from app.core.sorting import sortable_column


class CatalogProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, product_id: uuid.UUID) -> CatalogProduct | None:
        stmt = select(CatalogProduct).where(CatalogProduct.id == product_id, CatalogProduct.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_grade_id(self, grade_id: uuid.UUID) -> CatalogProduct | None:
        stmt = select(CatalogProduct).where(CatalogProduct.grade_id == grade_id, CatalogProduct.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_subject_id(self, subject_id: uuid.UUID) -> CatalogProduct | None:
        stmt = select(CatalogProduct).where(CatalogProduct.subject_id == subject_id, CatalogProduct.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def grade_exists(self, grade_id: uuid.UUID) -> bool:
        stmt = select(Grade.id).where(Grade.id == grade_id, Grade.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none() is not None

    def subject_exists(self, subject_id: uuid.UUID) -> bool:
        stmt = select(Subject.id).where(Subject.id == subject_id, Subject.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none() is not None

    def list(self, params: CatalogProductListParams) -> tuple[list[CatalogProduct], int]:
        stmt = select(CatalogProduct).where(CatalogProduct.deleted_at.is_(None))
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = self._apply_sort(stmt, params.sort)
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: CatalogProductListParams):
        if params.search:
            stmt = stmt.where(CatalogProduct.name.ilike(f"%{params.search}%"))
        if params.product_type:
            stmt = stmt.where(CatalogProduct.product_type == params.product_type)
        if params.status:
            stmt = stmt.where(CatalogProduct.status == params.status)
        return stmt

    def _apply_sort(self, stmt, sort: str):
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = sortable_column(CatalogProduct, field_name, CatalogProduct.created_at)
        return stmt.order_by(column.desc() if descending else column.asc())

    def create(self, product: CatalogProduct) -> CatalogProduct:
        self.db.add(product)
        self.db.flush()
        return product

    def update(self, product: CatalogProduct, data: dict) -> CatalogProduct:
        for field, value in data.items():
            setattr(product, field, value)
        self.db.flush()
        return product

    def commit(self) -> None:
        self.db.commit()
