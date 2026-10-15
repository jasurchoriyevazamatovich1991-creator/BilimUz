"""Data-access layer. Only SQLAlchemy here — no business rules.

Admin Management of Mock Test Entitlements (Task D) adds read-side
joins against CatalogProduct/Subject/User — read-only, one-directional
cross-module ORM-model imports, same already-established precedent as
roles/repository.py's User import and this module's own pre-existing
CatalogProduct import above (not a module-isolation violation — see
those files' own docstrings)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.catalog.constants import PRODUCT_TYPE_GRADE_SUBSCRIPTION, PRODUCT_TYPE_MOCK_TEST
from app.modules.catalog.models import CatalogProduct
from app.modules.entitlements.constants import STATUS_ACTIVE, STATUS_EXPIRED
from app.modules.entitlements.models import Entitlement
from app.modules.subjects.models import Subject
from app.modules.users.models import User


class EntitlementRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, entitlement_id: uuid.UUID) -> Entitlement | None:
        stmt = select(Entitlement).where(Entitlement.id == entitlement_id, Entitlement.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_for_user_product(self, user_id: uuid.UUID, product_id: uuid.UUID) -> Entitlement | None:
        stmt = select(Entitlement).where(
            Entitlement.user_id == user_id,
            Entitlement.product_id == product_id,
            Entitlement.status == STATUS_ACTIVE,
            Entitlement.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID) -> list[Entitlement]:
        stmt = select(Entitlement).where(Entitlement.user_id == user_id, Entitlement.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    # --- Admin Management of Mock Test Entitlements (Task D) ---

    def list_for_user_with_display(self, user_id: uuid.UUID) -> list[tuple[Entitlement, CatalogProduct, Subject | None, User | None]]:
        """Used by both the admin list view and the student `/me` view
        (same rows, the router decides which fields of the resulting
        EntitlementOut are meaningful to show — nothing here is
        admin-only data by itself). One query, no N+1: outerjoin Subject
        (a 'course' product has none) and outerjoin User for granted_by
        (NULL for purchases)."""
        granted_by_user = User
        stmt = (
            select(Entitlement, CatalogProduct, Subject, granted_by_user)
            .join(CatalogProduct, CatalogProduct.id == Entitlement.product_id)
            .outerjoin(Subject, Subject.id == CatalogProduct.subject_id)
            .outerjoin(granted_by_user, granted_by_user.id == Entitlement.granted_by)
            .where(Entitlement.user_id == user_id, Entitlement.deleted_at.is_(None))
            .order_by(Entitlement.created_at.desc())
        )
        return list(self.db.execute(stmt).all())

    def get_with_display(self, entitlement_id: uuid.UUID) -> tuple[Entitlement, CatalogProduct, Subject | None, User | None] | None:
        granted_by_user = User
        stmt = (
            select(Entitlement, CatalogProduct, Subject, granted_by_user)
            .join(CatalogProduct, CatalogProduct.id == Entitlement.product_id)
            .outerjoin(Subject, Subject.id == CatalogProduct.subject_id)
            .outerjoin(granted_by_user, granted_by_user.id == Entitlement.granted_by)
            .where(Entitlement.id == entitlement_id, Entitlement.deleted_at.is_(None))
        )
        return self.db.execute(stmt).first()

    def get_blocking_entitlement_for_grant(self, user_id: uuid.UUID, product_id: uuid.UUID) -> Entitlement | None:
        """The row (if any) that would conflict with a NEW grant for
        this exact (user, product) pair — i.e. a currently stored
        status='active' row, regardless of whether it is, by date,
        already effectively expired or still scheduled. The caller
        (service.grant_mock_test_entitlement) is responsible for
        telling those two cases apart: a date-expired one gets silently
        lazy-transitioned to status='expired' and the grant proceeds; a
        genuinely current/scheduled one blocks the grant with
        DuplicateActiveEntitlementException, directing the admin to
        the extend/reactivate endpoint instead (spec §3 — 'provide a
        safe extension/reactivation workflow instead of creating
        conflicting records')."""
        stmt = select(Entitlement).where(
            Entitlement.user_id == user_id,
            Entitlement.product_id == product_id,
            Entitlement.status == STATUS_ACTIVE,
            Entitlement.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def mark_expired(self, entitlement: Entitlement) -> None:
        """Single-row, explicit lazy transition — never touches any
        other entitlement (spec §3 — 'revoking one entitlement must not
        modify unrelated ones' applies just as much to this internal
        hygiene step as it does to an explicit revoke)."""
        entitlement.status = STATUS_EXPIRED
        self.db.flush()

    def has_active_grade_entitlement(self, user_id: uuid.UUID, grade_id: uuid.UUID) -> bool:
        """The exact-match grade check spec §2 depends on: a Grade 3
        entitlement can only ever satisfy a Grade 3 lookup, because
        CatalogProduct.grade_id is a plain equality join — there is no
        range/hierarchy logic here that could accidentally widen a
        match to Grade 2/4. `end_date IS NULL OR end_date > now()`
        covers the no-expiry case (NULL) and the still-valid case in
        one condition.

        `start_date <= now` (Task D fix): before Admin Management of
        Mock Test Entitlements, every entitlement's start_date was
        always "now" at creation time (purchases are immediate), so
        this condition was always trivially true and its absence was
        invisible. Task D lets an admin grant a *future-dated* (spec:
        "scheduled") entitlement, so without this condition a scheduled
        grant would incorrectly authorize access before its own start
        date arrives."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Entitlement.id)
            .join(CatalogProduct, CatalogProduct.id == Entitlement.product_id)
            .where(
                Entitlement.user_id == user_id,
                Entitlement.status == STATUS_ACTIVE,
                Entitlement.deleted_at.is_(None),
                CatalogProduct.product_type == PRODUCT_TYPE_GRADE_SUBSCRIPTION,
                CatalogProduct.grade_id == grade_id,
                Entitlement.start_date <= now,
                (Entitlement.end_date.is_(None)) | (Entitlement.end_date > now),
            )
        )
        return self.db.execute(stmt).scalar_one_or_none() is not None

    def has_active_mock_test_entitlement(self, user_id: uuid.UUID, subject_id: uuid.UUID) -> bool:
        """Mirrors has_active_grade_entitlement() exactly, scoped to
        mock_test products. subject_id is an equality join (never a
        hierarchy/range), so a Physics entitlement can only ever
        satisfy a Physics lookup — never Mathematics, never IELTS, and
        never a Physics *grade subscription or course* (those are
        different product_type rows entirely, spec §1/§4 — 'Mock Test
        entitlements must remain separate from grade subscriptions and
        preparation courses'). See has_active_grade_entitlement()'s
        docstring for why `start_date <= now` was added (Task D)."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Entitlement.id)
            .join(CatalogProduct, CatalogProduct.id == Entitlement.product_id)
            .where(
                Entitlement.user_id == user_id,
                Entitlement.status == STATUS_ACTIVE,
                Entitlement.deleted_at.is_(None),
                CatalogProduct.product_type == PRODUCT_TYPE_MOCK_TEST,
                CatalogProduct.subject_id == subject_id,
                Entitlement.start_date <= now,
                (Entitlement.end_date.is_(None)) | (Entitlement.end_date > now),
            )
        )
        return self.db.execute(stmt).scalar_one_or_none() is not None

    def create(self, entitlement: Entitlement) -> Entitlement:
        self.db.add(entitlement)
        self.db.flush()
        return entitlement

    def update(self, entitlement: Entitlement, data: dict) -> Entitlement:
        for field, value in data.items():
            setattr(entitlement, field, value)
        self.db.flush()
        return entitlement

    def commit(self) -> None:
        self.db.commit()
