"""
BilimUz — Task E: Integration Verification and Safe Database Validation
(Sprint 91 — Admin Management of Mock Test Entitlements).

Every test in this file runs against REAL PostgreSQL (the `pg_session`/
`client` fixtures in conftest.py — requires TEST_DATABASE_URL, a
database whose name ends in "_test"). No repository method is mocked
here; this is deliberately the opposite of
app/modules/entitlements/tests/test_entitlement_service.py, which mocks
every repository call. The two suites are complementary, not
redundant: the unit suite proves the service's own branching logic in
isolation; this suite proves the actual SQL — joins, CHECK
constraints, the partial unique index, and the `start_date <= now` fix
— behaves correctly against a real database engine.

Uses ONLY existing models/services — no invented endpoints, no
invented business rules. Where a test name says what the business rule
must be, the corresponding assertion is checked against this project's
ACTUAL code (service.py / repository.py / router.py), not against a
spec assumption.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security.password_service import PasswordService
from app.modules.attempts.exceptions import MockTestAccessDeniedException
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.catalog.constants import PRODUCT_STATUS_PUBLISHED, PRODUCT_TYPE_MOCK_TEST
from app.modules.catalog.models import CatalogProduct
from app.modules.catalog.repository import CatalogProductRepository
from app.modules.entitlements.constants import STATUS_ACTIVE
from app.modules.entitlements.exceptions import DuplicateActiveEntitlementException
from app.modules.entitlements.models import Entitlement
from app.modules.entitlements.repository import EntitlementRepository
from app.modules.entitlements.schemas import EntitlementExtendRequest, EntitlementGrantRequest
from app.modules.entitlements.service import EntitlementService
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import Test, TestStatus
from app.modules.tests.repository import TestRepository
from app.modules.users.models import User, UserStatus
from app.modules.users.repository import UserRepository

# ---------------------------------------------------------------------
# Shared fixtures-as-functions (mirrors the existing convention in
# tests/integration/test_attempt_result_integration.py and
# tests/integration/test_auth_rbac_integration.py — a plain helper
# function taking `pg_session`, not a pytest fixture, since each test
# needs a different combination of these).
# ---------------------------------------------------------------------


def _make_user(pg_session, role_name: str, password: str = "Integration-T3st-P@ss1") -> tuple[User, str]:
    role = pg_session.query(Role).filter(Role.name == role_name).one()
    user = User(
        role_id=role.id, first_name="Integration", last_name=role_name,
        email=f"{role_name.lower().replace(' ', '-')}-{uuid.uuid4()}@example.com",
        password_hash=PasswordService().hash_password(password), status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return user, password


def _make_subject(pg_session, name_prefix: str = "Subject") -> Subject:
    subject = Subject(name=f"{name_prefix} {uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    return subject


def _make_mock_test_product(pg_session, subject: Subject, duration_days: int | None = None) -> CatalogProduct:
    product = CatalogProduct(
        product_type=PRODUCT_TYPE_MOCK_TEST, subject_id=subject.id, grade_id=None,
        name=f"{subject.name} Mock Test", price=0, duration_days=duration_days,
        status=PRODUCT_STATUS_PUBLISHED,
    )
    pg_session.add(product)
    pg_session.flush()
    return product


def _make_mock_test(pg_session, subject: Subject, status: str = TestStatus.PUBLISHED) -> Test:
    test = Test(
        subject_id=subject.id, title=f"{subject.name} Mock Test Exam", duration=60,
        question_count=0, status=status, is_mock_test=True,
        shuffle_questions=False, shuffle_answers=False,
    )
    pg_session.add(test)
    pg_session.flush()
    return test


def _entitlement_service(pg_session) -> EntitlementService:
    return EntitlementService(
        EntitlementRepository(pg_session), CatalogProductRepository(pg_session), UserRepository(pg_session),
    )


def _attempt_service(pg_session, entitlement_service: EntitlementService | None = None) -> AttemptService:
    return AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
        entitlement_service=entitlement_service,
    )


def _grant_entitlement(
    pg_session, service: EntitlementService, user: User, product: CatalogProduct, admin: User,
    start_date=None, end_date=None, duration_days=None,
) -> Entitlement:
    data = EntitlementGrantRequest(
        user_id=user.id, product_id=product.id, start_date=start_date, end_date=end_date, duration_days=duration_days,
    )
    return service.grant_mock_test_entitlement(data, actor_id=admin.id)


# =======================================================================
# Section 2 — Database-level integration tests (repository/service,
# real PostgreSQL, no HTTP layer).
# =======================================================================


def test_active_entitlement_recognized_exactly_on_start_le_now_lt_end(pg_session):
    """Repository-level: has_active_mock_test_entitlement() must be True
    only while start_date <= now < end_date — the exact Task D bugfix
    (start_date previously never checked) is what this proves against a
    real query, not a mock."""
    student, _ = _make_user(pg_session, "Student")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    repo = EntitlementRepository(pg_session)

    now = datetime.now(timezone.utc)
    entitlement = Entitlement(
        user_id=student.id, product_id=product.id, source="admin_grant", granted_by=student.id,
        status=STATUS_ACTIVE, start_date=now - timedelta(days=1), end_date=now + timedelta(days=1),
    )
    pg_session.add(entitlement)
    pg_session.flush()

    assert repo.has_active_mock_test_entitlement(student.id, subject.id) is True


def test_scheduled_entitlement_does_not_grant_premature_access(pg_session):
    """A future start_date must NOT authorize access yet — this is
    exactly the bug that existed before Task D's `start_date <= now`
    fix (verified here against real SQL, not Python mock state)."""
    student, _ = _make_user(pg_session, "Student")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    repo = EntitlementRepository(pg_session)

    now = datetime.now(timezone.utc)
    entitlement = Entitlement(
        user_id=student.id, product_id=product.id, source="admin_grant", granted_by=student.id,
        status=STATUS_ACTIVE, start_date=now + timedelta(days=5), end_date=now + timedelta(days=10),
    )
    pg_session.add(entitlement)
    pg_session.flush()

    assert repo.has_active_mock_test_entitlement(student.id, subject.id) is False


def test_expired_entitlement_cannot_authorize_new_attempt(pg_session):
    """end_date in the past must block access even though the row's
    stored `status` column is still 'active' (no background job flips
    it — see constants.py). This proves the repository query's own
    end_date condition, independent of the lazy-expiry-on-grant
    mechanism tested separately below."""
    student, _ = _make_user(pg_session, "Student")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    test = _make_mock_test(pg_session, subject)
    repo = EntitlementRepository(pg_session)

    now = datetime.now(timezone.utc)
    entitlement = Entitlement(
        user_id=student.id, product_id=product.id, source="admin_grant", granted_by=student.id,
        status=STATUS_ACTIVE, start_date=now - timedelta(days=30), end_date=now - timedelta(days=1),
    )
    pg_session.add(entitlement)
    pg_session.flush()

    assert repo.has_active_mock_test_entitlement(student.id, subject.id) is False

    attempt_service = _attempt_service(pg_session, _entitlement_service(pg_session))
    with pytest.raises(MockTestAccessDeniedException):
        attempt_service.start_attempt(test.id, student.id)


def test_entitlement_covers_every_published_mock_test_under_its_subject(pg_session):
    """One entitlement for a subject/direction unlocks EVERY published
    mock test under that subject — not a single-test unlock (spec's own
    "revised" design, migration 0020's docstring)."""
    student, _ = _make_user(pg_session, "Student")
    admin, _ = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    test_one = _make_mock_test(pg_session, subject)
    test_two = _make_mock_test(pg_session, subject)

    entitlement_service = _entitlement_service(pg_session)
    _grant_entitlement(pg_session, entitlement_service, student, product, admin, duration_days=30)

    attempt_service = _attempt_service(pg_session, entitlement_service)
    attempt_one = attempt_service.start_attempt(test_one.id, student.id)
    attempt_two = attempt_service.start_attempt(test_two.id, student.id)

    assert attempt_one.id != attempt_two.id
    assert attempt_one.test_id == test_one.id
    assert attempt_two.test_id == test_two.id


def test_entitlement_for_one_subject_does_not_authorize_another_subject(pg_session):
    """Cross-subject isolation — a Physics entitlement must never
    satisfy a Mathematics (or any other subject's) mock test lookup."""
    student, _ = _make_user(pg_session, "Student")
    admin, _ = _make_user(pg_session, "Super Admin")
    subject_a = _make_subject(pg_session, "Physics")
    subject_b = _make_subject(pg_session, "Mathematics")
    product_a = _make_mock_test_product(pg_session, subject_a)
    test_b = _make_mock_test(pg_session, subject_b)

    entitlement_service = _entitlement_service(pg_session)
    _grant_entitlement(pg_session, entitlement_service, student, product_a, admin, duration_days=30)

    attempt_service = _attempt_service(pg_session, entitlement_service)
    with pytest.raises(MockTestAccessDeniedException):
        attempt_service.start_attempt(test_b.id, student.id)


def test_duplicate_active_grant_is_rejected_by_service_and_by_db_constraint(pg_session):
    """Two layers both guard against this: the service raises
    DuplicateActiveEntitlementException (409) before even attempting the
    insert; the partial unique index (uq_entitlements_active_user_product,
    WHERE status='active') is the real DB-level backstop if that were
    ever bypassed — proven here by inserting a true duplicate directly
    through the ORM, bypassing the service entirely."""
    student, _ = _make_user(pg_session, "Student")
    admin, _ = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)

    entitlement_service = _entitlement_service(pg_session)
    _grant_entitlement(pg_session, entitlement_service, student, product, admin, duration_days=30)

    with pytest.raises(DuplicateActiveEntitlementException):
        _grant_entitlement(pg_session, entitlement_service, student, product, admin, duration_days=30)

    # DB-level backstop: bypass the service and insert a second
    # status='active' row for the exact same (user_id, product_id) pair
    # directly — real PostgreSQL must refuse it via the partial unique
    # index, independent of any application-layer check.
    duplicate = Entitlement(
        user_id=student.id, product_id=product.id, source="admin_grant", granted_by=admin.id,
        status=STATUS_ACTIVE, start_date=datetime.now(timezone.utc),
    )
    pg_session.add(duplicate)
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_duplicate_grant_is_allowed_again_once_prior_entitlement_is_date_expired(pg_session):
    """Lazy-expiry-on-grant: a stored status='active' row whose
    end_date has already passed must not permanently block a fresh
    grant — grant_mock_test_entitlement() transitions that one row to
    'expired' first, then proceeds (spec's 'safe duplicate handling')."""
    student, _ = _make_user(pg_session, "Student")
    admin, _ = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    entitlement_service = _entitlement_service(pg_session)

    now = datetime.now(timezone.utc)
    stale = Entitlement(
        user_id=student.id, product_id=product.id, source="admin_grant", granted_by=admin.id,
        status=STATUS_ACTIVE, start_date=now - timedelta(days=60), end_date=now - timedelta(days=1),
    )
    pg_session.add(stale)
    pg_session.flush()

    new_entitlement = _grant_entitlement(pg_session, entitlement_service, student, product, admin, duration_days=30)

    pg_session.refresh(stale)
    assert stale.status == "expired"
    assert new_entitlement.id != stale.id
    assert new_entitlement.status == STATUS_ACTIVE


def test_grant_extend_revoke_persist_correctly_across_fresh_reads(pg_session):
    """Grant, extend, and revoke must each persist — re-read via a fresh
    repository query (not the same Python object) to prove the write
    actually reached the database, not just in-memory state."""
    student, _ = _make_user(pg_session, "Student")
    admin, _ = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    entitlement_service = _entitlement_service(pg_session)
    repo = EntitlementRepository(pg_session)

    granted = _grant_entitlement(pg_session, entitlement_service, student, product, admin, duration_days=30)
    reread = repo.get_by_id(granted.id)
    assert reread is not None
    assert reread.status == STATUS_ACTIVE
    original_end_date = reread.end_date

    extended = entitlement_service.extend_entitlement(
        granted.id, EntitlementExtendRequest(duration_days=90, reason="Extended for exam season"), actor_id=admin.id,
    )
    reread = repo.get_by_id(extended.id)
    assert reread.end_date > original_end_date
    assert reread.reason == "Extended for exam season"

    entitlement_service.revoke_entitlement(granted.id, actor_id=admin.id, reason="No longer needed")
    reread = repo.get_by_id(granted.id)
    assert reread.status == "revoked"
    assert reread.reason == "No longer needed"


def test_revoking_one_entitlement_does_not_modify_an_unrelated_entitlement(pg_session):
    """Revoke must be surgical: revoking a user's Physics entitlement
    must leave their Mathematics entitlement (same user, different
    product) completely untouched."""
    student, _ = _make_user(pg_session, "Student")
    admin, _ = _make_user(pg_session, "Super Admin")
    subject_a = _make_subject(pg_session, "Physics")
    subject_b = _make_subject(pg_session, "Mathematics")
    product_a = _make_mock_test_product(pg_session, subject_a)
    product_b = _make_mock_test_product(pg_session, subject_b)
    entitlement_service = _entitlement_service(pg_session)
    repo = EntitlementRepository(pg_session)

    entitlement_a = _grant_entitlement(pg_session, entitlement_service, student, product_a, admin, duration_days=30)
    entitlement_b = _grant_entitlement(pg_session, entitlement_service, student, product_b, admin, duration_days=30)

    entitlement_service.revoke_entitlement(entitlement_a.id, actor_id=admin.id)

    assert repo.get_by_id(entitlement_a.id).status == "revoked"
    assert repo.get_by_id(entitlement_b.id).status == STATUS_ACTIVE


# =======================================================================
# Section 3 — Frontend/API integration: real HTTP layer (the `client`
# fixture), real JWT auth, real role enforcement.
# =======================================================================


def test_admin_endpoints_reject_unauthenticated_requests(client, pg_session):
    response = client.post("/api/v1/entitlements/admin/grant", json={"user_id": str(uuid.uuid4()), "product_id": str(uuid.uuid4())})
    assert response.status_code in (401, 403)


def test_admin_endpoints_reject_non_admin_role(client, pg_session):
    """require_roles("Admin", "Super Admin") enforcement — a real,
    valid JWT for a Student must still be rejected (403), matching the
    established RBAC convention already verified for other admin
    surfaces in test_auth_rbac_integration.py."""
    student, password = _make_user(pg_session, "Student")
    login = client.post("/api/v1/auth/login", json={"identifier": student.email, "password": password})
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]

    response = client.post(
        "/api/v1/entitlements/admin/grant",
        json={"user_id": str(student.id), "product_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_grant_extend_revoke_full_http_flow(client, pg_session):
    """The full admin workflow through the real router — grant, then
    extend, then revoke — each via an actual HTTP call, asserting on
    the JSON envelope the frontend's admin UI actually consumes."""
    student, _ = _make_user(pg_session, "Student")
    admin, admin_password = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    pg_session.commit()

    login = client.post("/api/v1/auth/login", json={"identifier": admin.email, "password": admin_password})
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    grant_response = client.post(
        "/api/v1/entitlements/admin/grant",
        json={"user_id": str(student.id), "product_id": str(product.id), "duration_days": 30},
        headers=headers,
    )
    assert grant_response.status_code == 201
    body = grant_response.json()["data"]
    assert body["effective_status"] == "active"
    assert body["subject_name"] == subject.name
    entitlement_id = body["id"]

    extend_response = client.post(
        f"/api/v1/entitlements/admin/{entitlement_id}/extend",
        json={"duration_days": 90},
        headers=headers,
    )
    assert extend_response.status_code == 200
    assert extend_response.json()["data"]["end_date"] > body["end_date"]

    revoke_response = client.post(
        f"/api/v1/entitlements/admin/{entitlement_id}/revoke",
        json={"reason": "Test cleanup"},
        headers=headers,
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["data"]["effective_status"] == "revoked"


def test_grant_for_nonexistent_user_returns_404(client, pg_session):
    admin, admin_password = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    pg_session.commit()

    login = client.post("/api/v1/auth/login", json={"identifier": admin.email, "password": admin_password})
    token = login.json()["data"]["access_token"]

    response = client.post(
        "/api/v1/entitlements/admin/grant",
        json={"user_id": str(uuid.uuid4()), "product_id": str(product.id), "duration_days": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["message"] == "Foydalanuvchi topilmadi"


def test_grant_against_non_mock_test_product_returns_422(client, pg_session):
    """Scope guard — this admin surface only grants mock_test products;
    a grade_subscription/course product_id must be rejected, not
    silently accepted (spec §5 — no accidental cross-product grants)."""
    student, _ = _make_user(pg_session, "Student")
    admin, admin_password = _make_user(pg_session, "Super Admin")
    from app.modules.grades.models import Grade

    grade = Grade(name=f"Integration Grade {uuid.uuid4()}")
    pg_session.add(grade)
    pg_session.flush()
    grade_product = CatalogProduct(
        product_type="grade_subscription", grade_id=grade.id, subject_id=None,
        name="Grade Subscription", price=0, status=PRODUCT_STATUS_PUBLISHED,
    )
    pg_session.add(grade_product)
    pg_session.commit()

    login = client.post("/api/v1/auth/login", json={"identifier": admin.email, "password": admin_password})
    token = login.json()["data"]["access_token"]

    response = client.post(
        "/api/v1/entitlements/admin/grant",
        json={"user_id": str(student.id), "product_id": str(grade_product.id), "duration_days": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_grant_duplicate_via_http_returns_409(client, pg_session):
    student, _ = _make_user(pg_session, "Student")
    admin, admin_password = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    pg_session.commit()

    login = client.post("/api/v1/auth/login", json={"identifier": admin.email, "password": admin_password})
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/v1/entitlements/admin/grant",
        json={"user_id": str(student.id), "product_id": str(product.id), "duration_days": 30},
        headers=headers,
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/entitlements/admin/grant",
        json={"user_id": str(student.id), "product_id": str(product.id), "duration_days": 30},
        headers=headers,
    )
    assert second.status_code == 409


def test_entitlements_me_returns_only_the_callers_own_rows(client, pg_session):
    """/entitlements/me must never leak another user's entitlement rows
    — scoped strictly to the authenticated caller's own user_id, with
    no user_id accepted from the request at all (see router.py)."""
    student_one, password_one = _make_user(pg_session, "Student")
    student_two, _ = _make_user(pg_session, "Student")
    admin, _ = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)

    entitlement_service = _entitlement_service(pg_session)
    _grant_entitlement(pg_session, entitlement_service, student_one, product, admin, duration_days=30)
    _grant_entitlement(pg_session, entitlement_service, student_two, product, admin, duration_days=30)
    pg_session.commit()

    login = client.post("/api/v1/auth/login", json={"identifier": student_one.email, "password": password_one})
    token = login.json()["data"]["access_token"]

    response = client.get("/api/v1/entitlements/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 1
    assert rows[0]["user_id"] == str(student_one.id)


def test_entitlements_me_rejects_unauthenticated_requests(client, pg_session):
    response = client.get("/api/v1/entitlements/me")
    assert response.status_code in (401, 403)


# =======================================================================
# Section 4 — End-to-end access checks: entitlement creation through
# starting (and resuming) a real mock test attempt, through the real
# HTTP layer, proving backend (not frontend) enforcement.
# =======================================================================


def test_backend_blocks_attempt_start_without_entitlement_via_real_http_call(client, pg_session):
    """Direct backend API requests cannot bypass entitlement
    restrictions — proven here with a real HTTP call that has a valid
    JWT but no entitlement at all, hitting the real /attempts/start
    endpoint, not just unit-testing the service method."""
    student, password = _make_user(pg_session, "Student")
    subject = _make_subject(pg_session)
    test = _make_mock_test(pg_session, subject)
    pg_session.commit()

    login = client.post("/api/v1/auth/login", json={"identifier": student.email, "password": password})
    token = login.json()["data"]["access_token"]

    response = client.post(
        "/api/v1/attempts/start", json={"test_id": str(test.id)}, headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_end_to_end_grant_then_start_attempt_via_real_http_call(client, pg_session):
    """The full path: admin grants an entitlement -> student starts a
    mock test attempt -> succeeds, through two real HTTP round trips
    (not a single in-process service call), confirming the whole stack
    (router -> dependency wiring -> service -> repository -> real
    PostgreSQL) agrees."""
    student, student_password = _make_user(pg_session, "Student")
    admin, admin_password = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    test = _make_mock_test(pg_session, subject)
    pg_session.commit()

    admin_login = client.post("/api/v1/auth/login", json={"identifier": admin.email, "password": admin_password})
    admin_token = admin_login.json()["data"]["access_token"]
    grant = client.post(
        "/api/v1/entitlements/admin/grant",
        json={"user_id": str(student.id), "product_id": str(product.id), "duration_days": 30},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert grant.status_code == 201

    student_login = client.post("/api/v1/auth/login", json={"identifier": student.email, "password": student_password})
    student_token = student_login.json()["data"]["access_token"]
    start = client.post(
        "/api/v1/attempts/start", json={"test_id": str(test.id)}, headers={"Authorization": f"Bearer {student_token}"},
    )
    assert start.status_code == 201


def test_attempt_deadline_persists_across_a_fresh_refetch(pg_session):
    """expires_at, computed once at start_attempt() time, must be
    identical when the attempt is re-fetched afterwards (simulating a
    page refresh) — not recomputed, not reset."""
    student, _ = _make_user(pg_session, "Student")
    admin, _ = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    test = _make_mock_test(pg_session, subject)
    entitlement_service = _entitlement_service(pg_session)
    _grant_entitlement(pg_session, entitlement_service, student, product, admin, duration_days=30)

    attempt_service = _attempt_service(pg_session, entitlement_service)
    attempt = attempt_service.start_attempt(test.id, student.id)
    original_expires_at = attempt.expires_at

    refetched = attempt_service.get_attempt(attempt.id, student.id)
    assert refetched.expires_at == original_expires_at


def test_revoking_entitlement_does_not_affect_an_already_in_progress_attempt(pg_session):
    """Documents the ACTUAL, verified behavior (per Task E §4 — 'do not
    change this policy silently'): AttemptService.start_attempt() is the
    ONLY place entitlement_service is consulted anywhere in
    app/modules/attempts/service.py (grepped directly — no reference in
    save_answer/submit_attempt/get_attempt/get_attempt_detail/
    submit_module). Revocation therefore blocks only NEW attempts; an
    attempt already in progress remains fully accessible and completable
    even after its underlying entitlement is revoked. This is the
    existing, shipped behavior — this test proves it, it does not
    introduce it."""
    student, _ = _make_user(pg_session, "Student")
    admin, _ = _make_user(pg_session, "Super Admin")
    subject = _make_subject(pg_session)
    product = _make_mock_test_product(pg_session, subject)
    test = _make_mock_test(pg_session, subject)
    entitlement_service = _entitlement_service(pg_session)
    entitlement = _grant_entitlement(pg_session, entitlement_service, student, product, admin, duration_days=30)

    attempt_service = _attempt_service(pg_session, entitlement_service)
    attempt = attempt_service.start_attempt(test.id, student.id)

    entitlement_service.revoke_entitlement(entitlement.id, actor_id=admin.id)

    # The in-progress attempt is still fully readable/resumable —
    # get_attempt() never consults entitlement_service at all.
    still_there = attempt_service.get_attempt(attempt.id, student.id)
    assert still_there.id == attempt.id
    assert still_there.status == attempt.status

    # And a NEW attempt for the same (now-revoked) subject is correctly
    # blocked — proving revocation IS effective for anything new.
    with pytest.raises(MockTestAccessDeniedException):
        attempt_service.start_attempt(test.id, student.id)
