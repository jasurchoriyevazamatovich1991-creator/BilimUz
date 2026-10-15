"""
Business logic for entitlement lifecycle: create (from a purchase or an
admin grant), revoke, and the read-side access check future enforcement
code will call.

Admin Management of Mock Test Entitlements (Task D) adds the real
grant/extend/list-for-admin flows on top of the create/revoke methods
that already existed — see each method's own docstring.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.core.audit import log_action
from app.modules.catalog.constants import PRODUCT_TYPE_MOCK_TEST
from app.modules.catalog.exceptions import CatalogProductNotFoundException
from app.modules.catalog.models import CatalogProduct
from app.modules.catalog.repository import CatalogProductRepository
from app.modules.entitlements.constants import (
    EFFECTIVE_STATUS_ACTIVE,
    EFFECTIVE_STATUS_EXPIRED,
    EFFECTIVE_STATUS_REVOKED,
    EFFECTIVE_STATUS_SCHEDULED,
    SOURCE_ADMIN_GRANT,
    SOURCE_PURCHASE,
    STATUS_ACTIVE,
    STATUS_REVOKED,
)
from app.modules.entitlements.exceptions import (
    AdminGrantRequiresGranterException,
    DuplicateActiveEntitlementException,
    EntitlementNotFoundException,
    ProductNotMockTestException,
    ProductNotPurchasableException,
    TargetUserNotFoundException,
)
from app.modules.entitlements.models import Entitlement
from app.modules.entitlements.repository import EntitlementRepository
from app.modules.entitlements.schemas import EntitlementExtendRequest, EntitlementGrantRequest, EntitlementOut


class EntitlementService:
    def __init__(
        self,
        repository: EntitlementRepository,
        product_repository: CatalogProductRepository,
        user_repository=None,
    ):
        self.repo = repository
        self.product_repo = product_repository
        # Optional — only the real HTTP dependency wiring (dependencies.py)
        # supplies a real UserRepository. Every pre-existing caller/test
        # that constructs EntitlementService with the original 2
        # positional args is unaffected (same optional-constructor-
        # dependency pattern already used by AttemptService for
        # entitlement_service itself — see attempts/service.py).
        self.user_repo = user_repository

    def create_entitlement(
        self,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        source: str,
        actor_id: uuid.UUID,
        granted_by: uuid.UUID | None = None,
        payment_id: uuid.UUID | None = None,
    ) -> Entitlement:
        product = self.product_repo.get_by_id(product_id)
        if product is None:
            raise CatalogProductNotFoundException("Mahsulot topilmadi")

        if source == SOURCE_PURCHASE and product.status != "published":
            raise ProductNotPurchasableException("Bu mahsulot hozircha sotib olish uchun mavjud emas")
        if source == SOURCE_ADMIN_GRANT and granted_by is None:
            raise AdminGrantRequiresGranterException("Administrator tomonidan berilgan ruxsat uchun granted_by talab qilinadi")

        if self.repo.get_active_for_user_product(user_id, product_id) is not None:
            raise DuplicateActiveEntitlementException(
                "Foydalanuvchida bu mahsulot uchun allaqachon faol ruxsat mavjud"
            )

        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=product.duration_days) if product.duration_days else None

        entitlement = Entitlement(
            user_id=user_id,
            product_id=product_id,
            source=source,
            granted_by=granted_by,
            payment_id=payment_id,
            start_date=now,
            end_date=end_date,
            created_by=actor_id,
        )
        self.repo.create(entitlement)
        log_action(
            self.repo.db, action="entitlement.created", user_id=actor_id,
            entity_type="entitlement", entity_id=entitlement.id,
            metadata={"target_user_id": str(user_id), "product_id": str(product_id), "source": source},
        )
        self.repo.commit()
        return entitlement

    def revoke_entitlement(self, entitlement_id: uuid.UUID, actor_id: uuid.UUID, reason: str | None = None) -> Entitlement:
        """Sets exactly one row's status to 'revoked'. No bulk
        operation exists in this service — this is what guarantees
        revoking one entitlement can never touch an unrelated product's
        entitlement for the same user (spec §7 — 'Revoking a grade
        subscription must not accidentally revoke unrelated courses or
        mock tests'). `reason` (Task D) is optional free text the admin
        can attach to this specific action — stored on the row itself,
        so the row's own `reason` always reflects the most recent
        admin action taken on it (grant/extend/revoke), not a full
        history of reasons; the full history lives in audit_logs via
        log_action below."""
        entitlement = self.repo.get_by_id(entitlement_id)
        if entitlement is None:
            raise EntitlementNotFoundException("Ruxsat topilmadi")

        updates: dict = {"status": STATUS_REVOKED, "updated_by": actor_id}
        if reason is not None:
            updates["reason"] = reason
        self.repo.update(entitlement, updates)
        log_action(
            self.repo.db, action="entitlement.revoked", user_id=actor_id,
            entity_type="entitlement", entity_id=entitlement_id,
            metadata={"reason": reason} if reason else None,
        )
        self.repo.commit()
        return entitlement

    def list_mine(self, user_id: uuid.UUID) -> list[Entitlement]:
        return self.repo.list_for_user(user_id)

    # --- Admin Management of Mock Test Entitlements (Task D) ---

    def grant_mock_test_entitlement(self, data: EntitlementGrantRequest, actor_id: uuid.UUID) -> Entitlement:
        """Admin-grant entry point for this phase's new admin UI (spec
        §2). Scoped deliberately to product_type='mock_test' only — see
        ProductNotMockTestException's docstring; grade_subscription/
        course grants go through create_entitlement() directly (used
        internally, e.g. by a future payment-confirmation flow) rather
        than this admin surface."""
        if self.user_repo is not None and self.user_repo.get_by_id(data.user_id) is None:
            raise TargetUserNotFoundException("Foydalanuvchi topilmadi")

        product = self.product_repo.get_by_id(data.product_id)
        if product is None:
            raise CatalogProductNotFoundException("Mahsulot topilmadi")
        if product.product_type != PRODUCT_TYPE_MOCK_TEST:
            raise ProductNotMockTestException(
                "Bu amal faqat Mock Test mahsulotlari (fan/yo'nalish) uchun ishlatiladi"
            )

        start_date = data.start_date or datetime.now(timezone.utc)
        end_date = data.resolve_end_date(start_date)

        blocking = self.repo.get_blocking_entitlement_for_grant(data.user_id, data.product_id)
        if blocking is not None:
            now = datetime.now(timezone.utc)
            is_date_expired = blocking.end_date is not None and blocking.end_date <= now
            if is_date_expired:
                # Lazy transition — this row's stored status was never
                # updated by a background job (none exists in this
                # codebase; see constants.py), so it is still 'active'
                # even though its own end_date has passed. Fix that one
                # row's status before creating the new grant, exactly
                # like attempts' lazy auto-finish fixes one attempt's
                # status on next access, never a batch of attempts.
                self.repo.mark_expired(blocking)
                log_action(
                    self.repo.db, action="entitlement.auto_expired", user_id=actor_id,
                    entity_type="entitlement", entity_id=blocking.id,
                )
            else:
                raise DuplicateActiveEntitlementException(
                    "Foydalanuvchida bu yo'nalish uchun allaqachon faol yoki rejalashtirilgan ruxsat mavjud — "
                    "uni cho'zish (extend) imkoniyatidan foydalaning"
                )

        entitlement = Entitlement(
            user_id=data.user_id,
            product_id=data.product_id,
            source=SOURCE_ADMIN_GRANT,
            granted_by=actor_id,
            payment_id=None,
            status=STATUS_ACTIVE,
            start_date=start_date,
            end_date=end_date,
            reason=data.reason,
            created_by=actor_id,
        )
        self.repo.create(entitlement)
        log_action(
            self.repo.db, action="entitlement.admin_granted", user_id=actor_id,
            entity_type="entitlement", entity_id=entitlement.id,
            metadata={
                "target_user_id": str(data.user_id), "product_id": str(data.product_id),
                "start_date": start_date.isoformat(), "end_date": end_date.isoformat() if end_date else None,
                "reason": data.reason,
            },
        )
        self.repo.commit()
        return entitlement

    def extend_entitlement(self, entitlement_id: uuid.UUID, data: EntitlementExtendRequest, actor_id: uuid.UUID) -> Entitlement:
        """Extends a currently active/scheduled entitlement's end_date,
        or reactivates one that had expired or been revoked (spec §2.6
        and §3's 'safe extension/reactivation workflow') — the single
        endpoint handles both, since from the admin's point of view
        they're the same action: 'give this user more time in this
        direction'. Always computed relative to *now* (not the row's
        existing start_date/end_date), so 'extend by 90 days' always
        means '90 days from today', matching the plain-language meaning
        regardless of whether the row was still valid or had already
        lapsed."""
        entitlement = self.repo.get_by_id(entitlement_id)
        if entitlement is None:
            raise EntitlementNotFoundException("Ruxsat topilmadi")

        now = datetime.now(timezone.utc)
        new_end_date = data.resolve_end_date(now)

        updates: dict = {"status": STATUS_ACTIVE, "end_date": new_end_date, "updated_by": actor_id}
        # Reactivating a scheduled-for-the-future row should not also
        # silently move its start_date — only a row that had already
        # started (or expired/was revoked) gets its start_date reset
        # to "now", so access begins immediately rather than waiting
        # out a start_date that already passed.
        if entitlement.start_date <= now:
            updates["start_date"] = now
        if data.reason is not None:
            updates["reason"] = data.reason

        self.repo.update(entitlement, updates)
        log_action(
            self.repo.db, action="entitlement.extended", user_id=actor_id,
            entity_type="entitlement", entity_id=entitlement_id,
            metadata={"new_end_date": new_end_date.isoformat(), "reason": data.reason},
        )
        self.repo.commit()
        return entitlement

    def get_display(self, entitlement_id: uuid.UUID) -> EntitlementOut:
        """Single-row enriched read — used right after grant/extend/
        revoke so the router can return the fresh, display-ready row
        without re-fetching the whole user's list just to find it."""
        row = self.repo.get_with_display(entitlement_id)
        if row is None:
            raise EntitlementNotFoundException("Ruxsat topilmadi")
        entitlement, product, subject, granted_by_user = row
        return self._to_out(entitlement, product, subject, granted_by_user)

    def list_for_user_display(self, user_id: uuid.UUID) -> list[EntitlementOut]:
        """Shared by both the admin list-for-a-user endpoint and the
        student-facing `/entitlements/me` endpoint — same rows, same
        shape; the router alone decides which fields of EntitlementOut
        a given caller is shown (today: all of them, since none of
        granted_by_name/source/dates is sensitive to the entitlement's
        own owner)."""
        rows = self.repo.list_for_user_with_display(user_id)
        return [self._to_out(entitlement, product, subject, granted_by_user) for entitlement, product, subject, granted_by_user in rows]

    def _to_out(self, entitlement: Entitlement, product: CatalogProduct, subject, granted_by_user) -> EntitlementOut:
        return EntitlementOut(
            id=entitlement.id,
            user_id=entitlement.user_id,
            product_id=entitlement.product_id,
            source=entitlement.source,
            granted_by=entitlement.granted_by,
            payment_id=entitlement.payment_id,
            status=entitlement.status,
            start_date=entitlement.start_date,
            end_date=entitlement.end_date,
            reason=entitlement.reason,
            created_at=entitlement.created_at,
            updated_at=entitlement.updated_at,
            product_name=product.name,
            product_type=product.product_type,
            subject_id=product.subject_id,
            subject_name=subject.name if subject is not None else None,
            granted_by_name=f"{granted_by_user.first_name} {granted_by_user.last_name}" if granted_by_user is not None else None,
            effective_status=self._effective_status(entitlement),
        )

    @staticmethod
    def _effective_status(entitlement: Entitlement) -> str:
        """Computed, never stored — see constants.py's EFFECTIVE_STATUS_*
        docstring. Order matters: an explicit revoke always wins over
        date math (a revoked-then-somehow-still-valid-by-date row is
        still revoked), then date-based expiry, then date-based
        scheduling, else active."""
        if entitlement.status == STATUS_REVOKED:
            return EFFECTIVE_STATUS_REVOKED
        now = datetime.now(timezone.utc)
        if entitlement.end_date is not None and entitlement.end_date <= now:
            return EFFECTIVE_STATUS_EXPIRED
        if entitlement.status == "expired":
            return EFFECTIVE_STATUS_EXPIRED
        if entitlement.start_date > now:
            return EFFECTIVE_STATUS_SCHEDULED
        return EFFECTIVE_STATUS_ACTIVE

    def has_grade_access(self, user_id: uuid.UUID, grade_id: uuid.UUID) -> bool:
        """Not called from any router yet this phase — see module
        README. Exists now, fully unit-tested, so the next phase's
        enforcement middleware has a correct, already-proven function
        to call rather than writing this logic for the first time
        under deadline pressure at the content-endpoint layer."""
        return self.repo.has_active_grade_entitlement(user_id, grade_id)

    def has_mock_test_access(self, user_id: uuid.UUID, subject_id: uuid.UUID) -> bool:
        """Called from AttemptService.start_attempt() (see the attempts
        module) for every test flagged is_mock_test=True — this is the
        one check this feature actually wires into a live endpoint,
        unlike has_grade_access() above which remains unwired this
        phase. subject_id must be the test's own subject_id (the
        caller is responsible for that — see
        AttemptService.start_attempt()'s docstring)."""
        return self.repo.has_active_mock_test_entitlement(user_id, subject_id)
