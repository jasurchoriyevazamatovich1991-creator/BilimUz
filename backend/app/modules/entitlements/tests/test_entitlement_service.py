"""Unit tests for EntitlementService — repositories mocked, no real DB needed."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AppException
from app.modules.auth.dependencies import require_roles
from app.modules.catalog.constants import PRODUCT_TYPE_COURSE, PRODUCT_TYPE_MOCK_TEST
from app.modules.catalog.exceptions import CatalogProductNotFoundException
from app.modules.entitlements.exceptions import (
    AdminGrantRequiresGranterException,
    DuplicateActiveEntitlementException,
    EntitlementNotFoundException,
    ProductNotMockTestException,
    ProductNotPurchasableException,
    TargetUserNotFoundException,
)
from app.modules.entitlements.schemas import EntitlementExtendRequest, EntitlementGrantRequest
from app.modules.entitlements.service import EntitlementService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_product_repo():
    return MagicMock()


@pytest.fixture
def mock_user_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_product_repo):
    return EntitlementService(mock_repo, mock_product_repo)


@pytest.fixture
def service_with_user_repo(mock_repo, mock_product_repo, mock_user_repo):
    return EntitlementService(mock_repo, mock_product_repo, mock_user_repo)


def _published_product(duration_days=30):
    return MagicMock(id=uuid.uuid4(), status="published", duration_days=duration_days)


def _mock_test_product(duration_days=None):
    return MagicMock(id=uuid.uuid4(), status="published", product_type=PRODUCT_TYPE_MOCK_TEST, duration_days=duration_days)


# --- create_entitlement ---

def test_create_purchase_rejects_unpublished_product(service, mock_repo, mock_product_repo):
    mock_product_repo.get_by_id.return_value = MagicMock(status="draft")
    mock_repo.get_active_for_user_product.return_value = None
    with pytest.raises(ProductNotPurchasableException):
        service.create_entitlement(uuid.uuid4(), uuid.uuid4(), source="purchase", actor_id=uuid.uuid4())


def test_create_admin_grant_without_granter_rejected(service, mock_repo, mock_product_repo):
    mock_product_repo.get_by_id.return_value = _published_product()
    mock_repo.get_active_for_user_product.return_value = None
    with pytest.raises(AdminGrantRequiresGranterException):
        service.create_entitlement(uuid.uuid4(), uuid.uuid4(), source="admin_grant", actor_id=uuid.uuid4())


def test_create_rejects_duplicate_active_entitlement(service, mock_repo, mock_product_repo):
    mock_product_repo.get_by_id.return_value = _published_product()
    mock_repo.get_active_for_user_product.return_value = MagicMock()  # an existing active row
    with pytest.raises(DuplicateActiveEntitlementException):
        service.create_entitlement(uuid.uuid4(), uuid.uuid4(), source="purchase", actor_id=uuid.uuid4())


def test_create_purchase_succeeds_and_computes_end_date_from_product_duration(service, mock_repo, mock_product_repo):
    mock_product_repo.get_by_id.return_value = _published_product(duration_days=30)
    mock_repo.get_active_for_user_product.return_value = None

    entitlement = service.create_entitlement(uuid.uuid4(), uuid.uuid4(), source="purchase", actor_id=uuid.uuid4())

    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()
    assert entitlement.source == "purchase"
    assert entitlement.granted_by is None
    delta = entitlement.end_date - entitlement.start_date
    assert delta.days == 30


def test_create_with_no_expiry_product_leaves_end_date_none(service, mock_repo, mock_product_repo):
    mock_product_repo.get_by_id.return_value = _published_product(duration_days=None)
    mock_repo.get_active_for_user_product.return_value = None

    entitlement = service.create_entitlement(uuid.uuid4(), uuid.uuid4(), source="purchase", actor_id=uuid.uuid4())

    assert entitlement.end_date is None


def test_create_admin_grant_succeeds_with_granter(service, mock_repo, mock_product_repo):
    mock_product_repo.get_by_id.return_value = _published_product()
    mock_repo.get_active_for_user_product.return_value = None
    granter = uuid.uuid4()

    entitlement = service.create_entitlement(
        uuid.uuid4(), uuid.uuid4(), source="admin_grant", actor_id=granter, granted_by=granter,
    )

    assert entitlement.source == "admin_grant"
    assert entitlement.granted_by == granter


# --- revoke_entitlement ---

def test_revoke_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(EntitlementNotFoundException):
        service.revoke_entitlement(uuid.uuid4(), actor_id=uuid.uuid4())


def test_revoke_updates_only_the_targeted_entitlement(service, mock_repo):
    """Regression guard for spec §7 — revoking one entitlement must
    never affect another. There is no bulk path in this service at
    all, so this asserts the single-row call shape stays that way."""
    entitlement = MagicMock(id=uuid.uuid4())
    mock_repo.get_by_id.return_value = entitlement
    actor = uuid.uuid4()

    service.revoke_entitlement(entitlement.id, actor_id=actor)

    mock_repo.update.assert_called_once_with(entitlement, {"status": "revoked", "updated_by": actor})
    mock_repo.commit.assert_called_once()


# --- has_grade_access / grade isolation ---

def test_has_grade_access_delegates_to_repository_exact_grade(service, mock_repo):
    user_id, grade_id = uuid.uuid4(), uuid.uuid4()
    mock_repo.has_active_grade_entitlement.return_value = True

    assert service.has_grade_access(user_id, grade_id) is True
    mock_repo.has_active_grade_entitlement.assert_called_once_with(user_id, grade_id)


def test_has_grade_access_false_for_different_grade(service, mock_repo):
    """A Grade 3 entitlement must not report access for Grade 2 — this
    is enforced by the repository's equality join (see
    repository.py's has_active_grade_entitlement), exercised here via
    the mock returning False for a mismatched grade_id, matching real
    join behavior."""
    user_id = uuid.uuid4()
    grade_3_id, grade_2_id = uuid.uuid4(), uuid.uuid4()

    def fake_check(uid, gid):
        return gid == grade_3_id

    mock_repo.has_active_grade_entitlement.side_effect = fake_check

    assert service.has_grade_access(user_id, grade_3_id) is True
    assert service.has_grade_access(user_id, grade_2_id) is False


# --- has_mock_test_access / subject-direction isolation (Mock Test Entitlements) ---

def test_has_mock_test_access_delegates_to_repository_exact_subject(service, mock_repo):
    user_id, subject_id = uuid.uuid4(), uuid.uuid4()
    mock_repo.has_active_mock_test_entitlement.return_value = True

    assert service.has_mock_test_access(user_id, subject_id) is True
    mock_repo.has_active_mock_test_entitlement.assert_called_once_with(user_id, subject_id)


def test_physics_entitlement_does_not_grant_mathematics_or_chemistry_access(service, mock_repo):
    """Spec test #2 — one physics entitlement must not grant access to
    mathematics or chemistry mock tests."""
    user_id = uuid.uuid4()
    physics_id, math_id, chemistry_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def fake_check(uid, sid):
        return sid == physics_id

    mock_repo.has_active_mock_test_entitlement.side_effect = fake_check

    assert service.has_mock_test_access(user_id, physics_id) is True
    assert service.has_mock_test_access(user_id, math_id) is False
    assert service.has_mock_test_access(user_id, chemistry_id) is False


def test_ielts_entitlement_does_not_grant_sat_or_gre_access(service, mock_repo):
    """Spec test #3 — one IELTS entitlement grants access to all
    published IELTS mock tests but not SAT or GRE."""
    user_id = uuid.uuid4()
    ielts_id, sat_id, gre_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def fake_check(uid, sid):
        return sid == ielts_id

    mock_repo.has_active_mock_test_entitlement.side_effect = fake_check

    assert service.has_mock_test_access(user_id, ielts_id) is True
    assert service.has_mock_test_access(user_id, sat_id) is False
    assert service.has_mock_test_access(user_id, gre_id) is False


def test_multiple_entitlements_evaluated_independently(service, mock_repo):
    """Spec test #4 — multiple separately purchased entitlements work
    independently: holding both Physics and IELTS grants both, and
    neither depends on the other."""
    user_id = uuid.uuid4()
    physics_id, ielts_id, sat_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    held = {physics_id, ielts_id}

    mock_repo.has_active_mock_test_entitlement.side_effect = lambda uid, sid: sid in held

    assert service.has_mock_test_access(user_id, physics_id) is True
    assert service.has_mock_test_access(user_id, ielts_id) is True
    assert service.has_mock_test_access(user_id, sat_id) is False


# --- Admin Management of Mock Test Entitlements (Task D) ---
# Spec test numbers below refer to this feature's own §7 enumeration.

def _grant_request(**overrides):
    defaults = {"user_id": uuid.uuid4(), "product_id": uuid.uuid4()}
    defaults.update(overrides)
    return EntitlementGrantRequest(**defaults)


# --- spec test #1 — an authorized admin can grant a Mock Test entitlement ---

def test_grant_succeeds_and_computes_end_date_from_duration(service, mock_repo, mock_product_repo):
    product = _mock_test_product()
    mock_product_repo.get_by_id.return_value = product
    mock_repo.get_blocking_entitlement_for_grant.return_value = None
    actor = uuid.uuid4()

    data = _grant_request(product_id=product.id, duration_days=90)
    entitlement = service.grant_mock_test_entitlement(data, actor_id=actor)

    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()
    assert entitlement.source == "admin_grant"
    assert entitlement.granted_by == actor
    assert entitlement.status == "active"
    delta = entitlement.end_date - entitlement.start_date
    assert delta.days == 90


def test_grant_with_explicit_end_date_and_future_start_date(service, mock_repo, mock_product_repo):
    product = _mock_test_product()
    mock_product_repo.get_by_id.return_value = product
    mock_repo.get_blocking_entitlement_for_grant.return_value = None

    start = datetime.now(timezone.utc) + timedelta(days=5)
    end = start + timedelta(days=30)
    data = _grant_request(product_id=product.id, start_date=start, end_date=end)
    entitlement = service.grant_mock_test_entitlement(data, actor_id=uuid.uuid4())

    assert entitlement.start_date == start
    assert entitlement.end_date == end


def test_grant_with_no_duration_or_end_date_leaves_end_date_none(service, mock_repo, mock_product_repo):
    product = _mock_test_product()
    mock_product_repo.get_by_id.return_value = product
    mock_repo.get_blocking_entitlement_for_grant.return_value = None

    entitlement = service.grant_mock_test_entitlement(_grant_request(product_id=product.id), actor_id=uuid.uuid4())
    assert entitlement.end_date is None


def test_grant_validates_user_exists_when_user_repo_available(service_with_user_repo, mock_user_repo):
    mock_user_repo.get_by_id.return_value = None
    with pytest.raises(TargetUserNotFoundException):
        service_with_user_repo.grant_mock_test_entitlement(_grant_request(), actor_id=uuid.uuid4())


def test_grant_rejects_unknown_product(service, mock_product_repo):
    mock_product_repo.get_by_id.return_value = None
    with pytest.raises(CatalogProductNotFoundException):
        service.grant_mock_test_entitlement(_grant_request(), actor_id=uuid.uuid4())


def test_grant_rejects_non_mock_test_product_type(service, mock_product_repo):
    """This admin surface is scoped to Mock Test Entitlements only —
    a grade_subscription or course product must be rejected, not
    silently granted through this endpoint."""
    mock_product_repo.get_by_id.return_value = MagicMock(product_type=PRODUCT_TYPE_COURSE)
    with pytest.raises(ProductNotMockTestException):
        service.grant_mock_test_entitlement(_grant_request(), actor_id=uuid.uuid4())


# --- spec test #3/#4 — a grant covers exactly one direction, not another ---

def test_grant_covers_only_the_selected_products_direction(service, mock_repo, mock_product_repo):
    physics_product = _mock_test_product()
    mock_product_repo.get_by_id.return_value = physics_product
    mock_repo.get_blocking_entitlement_for_grant.return_value = None

    entitlement = service.grant_mock_test_entitlement(
        _grant_request(product_id=physics_product.id), actor_id=uuid.uuid4(),
    )
    assert entitlement.product_id == physics_product.id


# --- spec test #7 — duplicate grants are handled without conflicting records ---

def test_grant_blocks_on_genuinely_current_duplicate(service, mock_repo, mock_product_repo):
    product = _mock_test_product()
    mock_product_repo.get_by_id.return_value = product
    still_valid = MagicMock(end_date=datetime.now(timezone.utc) + timedelta(days=10))
    mock_repo.get_blocking_entitlement_for_grant.return_value = still_valid

    with pytest.raises(DuplicateActiveEntitlementException):
        service.grant_mock_test_entitlement(_grant_request(product_id=product.id), actor_id=uuid.uuid4())
    mock_repo.create.assert_not_called()


def test_grant_lazily_expires_a_date_lapsed_row_then_succeeds(service, mock_repo, mock_product_repo):
    """The row blocking a new grant might be stored status='active' but
    already past its own end_date (nothing in this codebase runs a
    background job to flip that) — the grant must still succeed, after
    quietly transitioning that one stale row to 'expired' first."""
    product = _mock_test_product()
    mock_product_repo.get_by_id.return_value = product
    stale = MagicMock(id=uuid.uuid4(), end_date=datetime.now(timezone.utc) - timedelta(days=1))
    mock_repo.get_blocking_entitlement_for_grant.return_value = stale

    entitlement = service.grant_mock_test_entitlement(_grant_request(product_id=product.id), actor_id=uuid.uuid4())

    mock_repo.mark_expired.assert_called_once_with(stale)
    mock_repo.create.assert_called_once()
    assert entitlement is not stale


# --- spec test #5 — extending an entitlement updates its validity safely ---

def test_extend_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(EntitlementNotFoundException):
        service.extend_entitlement(uuid.uuid4(), EntitlementExtendRequest(duration_days=30), actor_id=uuid.uuid4())


def test_extend_updates_end_date_by_duration_from_now(service, mock_repo):
    now = datetime.now(timezone.utc)
    entitlement = MagicMock(id=uuid.uuid4(), start_date=now - timedelta(days=100))
    mock_repo.get_by_id.return_value = entitlement

    service.extend_entitlement(entitlement.id, EntitlementExtendRequest(duration_days=30), actor_id=uuid.uuid4())

    mock_repo.update.assert_called_once()
    called_entitlement, updates = mock_repo.update.call_args[0]
    assert called_entitlement is entitlement
    assert updates["status"] == "active"
    assert (updates["end_date"] - now).days == 30
    mock_repo.commit.assert_called_once()


def test_extend_reactivates_an_expired_or_revoked_entitlement(service, mock_repo):
    """Spec §3's 'safe extension/reactivation workflow' — the same
    extend call both extends a currently-valid row and reactivates one
    that had already lapsed/been revoked."""
    now = datetime.now(timezone.utc)
    entitlement = MagicMock(id=uuid.uuid4(), status="revoked", start_date=now - timedelta(days=400))
    mock_repo.get_by_id.return_value = entitlement

    service.extend_entitlement(entitlement.id, EntitlementExtendRequest(duration_days=90), actor_id=uuid.uuid4())

    updates = mock_repo.update.call_args[0][1]
    assert updates["status"] == "active"
    assert updates["start_date"] >= now - timedelta(seconds=5)  # reset to "now", not left in the past


def test_extend_with_explicit_end_date(service, mock_repo):
    entitlement = MagicMock(id=uuid.uuid4(), start_date=datetime.now(timezone.utc) - timedelta(days=5))
    mock_repo.get_by_id.return_value = entitlement
    new_end = datetime.now(timezone.utc) + timedelta(days=200)

    service.extend_entitlement(entitlement.id, EntitlementExtendRequest(end_date=new_end), actor_id=uuid.uuid4())

    assert mock_repo.update.call_args[0][1]["end_date"] == new_end


# --- spec test #6 — revoking/extending one entitlement must not affect others ---

def test_extend_only_touches_the_targeted_row(service, mock_repo):
    """No bulk path exists for extend either — mirrors the existing
    revoke guarantee."""
    entitlement = MagicMock(id=uuid.uuid4(), start_date=datetime.now(timezone.utc) - timedelta(days=5))
    mock_repo.get_by_id.return_value = entitlement

    service.extend_entitlement(entitlement.id, EntitlementExtendRequest(duration_days=30), actor_id=uuid.uuid4())

    mock_repo.update.assert_called_once()
    assert mock_repo.update.call_args[0][0] is entitlement


# --- schema-level validation (spec test #10 — invalid payloads rejected) ---

def test_grant_schema_rejects_end_date_and_duration_together():
    with pytest.raises(ValueError):
        EntitlementGrantRequest(
            user_id=uuid.uuid4(), product_id=uuid.uuid4(),
            end_date=datetime.now(timezone.utc) + timedelta(days=1), duration_days=30,
        )


def test_grant_schema_rejects_end_date_before_start_date():
    start = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        EntitlementGrantRequest(
            user_id=uuid.uuid4(), product_id=uuid.uuid4(),
            start_date=start, end_date=start - timedelta(days=1),
        )


def test_extend_schema_requires_exactly_one_of_end_date_or_duration():
    with pytest.raises(ValueError):
        EntitlementExtendRequest()
    with pytest.raises(ValueError):
        EntitlementExtendRequest(end_date=datetime.now(timezone.utc) + timedelta(days=1), duration_days=30)


def test_grant_schema_rejects_non_positive_duration():
    with pytest.raises(ValueError):
        EntitlementGrantRequest(user_id=uuid.uuid4(), product_id=uuid.uuid4(), duration_days=0)


# --- _effective_status (spec test #8 — expired/revoked/scheduled display) ---

def test_effective_status_revoked_wins_over_dates():
    entitlement = MagicMock(
        status="revoked", start_date=datetime.now(timezone.utc) - timedelta(days=10),
        end_date=datetime.now(timezone.utc) + timedelta(days=10),
    )
    assert EntitlementService._effective_status(entitlement) == "revoked"


def test_effective_status_expired_by_date_even_if_stored_active():
    entitlement = MagicMock(
        status="active", start_date=datetime.now(timezone.utc) - timedelta(days=10),
        end_date=datetime.now(timezone.utc) - timedelta(days=1),
    )
    assert EntitlementService._effective_status(entitlement) == "expired"


def test_effective_status_scheduled_for_future_start_date():
    entitlement = MagicMock(
        status="active", start_date=datetime.now(timezone.utc) + timedelta(days=5), end_date=None,
    )
    assert EntitlementService._effective_status(entitlement) == "scheduled"


def test_effective_status_active_when_currently_valid():
    entitlement = MagicMock(
        status="active", start_date=datetime.now(timezone.utc) - timedelta(days=1),
        end_date=datetime.now(timezone.utc) + timedelta(days=1),
    )
    assert EntitlementService._effective_status(entitlement) == "active"


# --- list_for_user_display / get_display (admin list + student /me share this) ---

def test_list_for_user_display_builds_enriched_rows(service, mock_repo):
    user_id = uuid.uuid4()
    entitlement = MagicMock(
        id=uuid.uuid4(), user_id=user_id, product_id=uuid.uuid4(), source="admin_grant",
        granted_by=uuid.uuid4(), payment_id=None, status="active",
        start_date=datetime.now(timezone.utc) - timedelta(days=1), end_date=None, reason="test",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    product = MagicMock(product_type=PRODUCT_TYPE_MOCK_TEST, subject_id=uuid.uuid4())
    product.name = "Fizika Mock Test"  # MagicMock(name=...) sets the mock's own repr name, not a .name attribute
    subject = MagicMock()
    subject.name = "Fizika"
    granted_by_user = MagicMock(first_name="Ali", last_name="Valiyev")
    mock_repo.list_for_user_with_display.return_value = [(entitlement, product, subject, granted_by_user)]

    out = service.list_for_user_display(user_id)

    assert len(out) == 1
    assert out[0].product_name == "Fizika Mock Test"
    assert out[0].subject_name == "Fizika"
    assert out[0].granted_by_name == "Ali Valiyev"
    assert out[0].effective_status == "active"


def test_list_for_user_display_handles_no_subject_and_no_granter():
    """A purchase has no granted_by, and a 'course' product has no
    subject — both must render as None, not crash."""
    repo = MagicMock()
    svc = EntitlementService(repo, MagicMock())
    entitlement = MagicMock(
        id=uuid.uuid4(), user_id=uuid.uuid4(), product_id=uuid.uuid4(), source="purchase",
        granted_by=None, payment_id=uuid.uuid4(), status="active",
        start_date=datetime.now(timezone.utc) - timedelta(days=1), end_date=None, reason=None,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    product = MagicMock(product_type=PRODUCT_TYPE_COURSE, subject_id=None)
    product.name = "IELTS Course"
    repo.list_for_user_with_display.return_value = [(entitlement, product, None, None)]

    out = svc.list_for_user_display(entitlement.user_id)
    assert out[0].subject_name is None
    assert out[0].granted_by_name is None


def test_get_display_raises_when_missing(service, mock_repo):
    mock_repo.get_with_display.return_value = None
    with pytest.raises(EntitlementNotFoundException):
        service.get_display(uuid.uuid4())


# --- spec test #2 — an unauthorized user receives a proper authorization error ---

def test_require_roles_rejects_non_admin_role():
    """First direct unit test of require_roles() in this codebase (it
    is otherwise only exercised indirectly, through a real HTTP call in
    each router that uses it) — exact mirror of how every admin-only
    endpoint in this module (and catalog/payments before it) is
    protected."""
    checker = require_roles("Admin", "Super Admin")
    non_admin_user = MagicMock(role=MagicMock(name="Teacher"))
    non_admin_user.role.name = "Teacher"

    with pytest.raises(AppException) as exc_info:
        checker(user=non_admin_user)
    assert exc_info.value.status_code == 403


def test_require_roles_allows_admin_role():
    checker = require_roles("Admin", "Super Admin")
    admin_user = MagicMock()
    admin_user.role.name = "Admin"
    assert checker(user=admin_user) is admin_user
