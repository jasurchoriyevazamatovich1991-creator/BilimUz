"""
Sprint 75 completion — Adaptive Routing Rule Admin Configuration API
integration tests, against real PostgreSQL (Sprint 40's infrastructure
— pg_session, TEST_DATABASE_URL, the `client` TestClient fixture).

Uses real HTTP requests through TestClient with real JWT tokens,
mirroring test_question_group_api.py's own established pattern exactly
(this project's precedent for RBAC/route-collision verification at the
HTTP layer) — not a parallel/invented test style.

This file tests ONLY the new Admin CRUD surface (POST/GET/PATCH/DELETE
/tests/routing-threshold-rules) and its RBAC/validation. It does not
duplicate test_sprint75_live_adaptive_routing.py's own execution-flow
coverage (sequential fallback, performance-based selection, concurrency,
cross-section rejection, etc.) — those 15 tests remain untouched and
still pass unchanged. The two tests at the end of this file
(test_admin_created_rule_is_used_by_real_execution /
test_no_rules_created_leaves_sequential_fallback_unchanged) exist only
to prove the NEW API round-trips correctly into the EXISTING,
unmodified execution path — not to re-test that path's own logic.
"""
import uuid

import pytest
from sqlalchemy import select

from app.core.security.dependencies import get_jwt_service
from app.modules.attempts.models import AttemptModuleProgress, AttemptStatus, TestAttempt
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.questions.repository import QuestionRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, RoutingThresholdRule, Test
from app.modules.tests.repository import ExamModuleRepository, RoutingThresholdRuleRepository
from app.modules.users.models import User, UserStatus


def _make_user(pg_session, role_name: str) -> User:
    role = pg_session.query(Role).filter(Role.name == role_name).one()
    user = User(role_id=role.id, first_name="U", last_name=role_name, email=f"{role_name}-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user


def _token(user: User) -> str:
    return get_jwt_service().create_access_token(str(user.id))


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {_token(user)}"}


def _make_test(pg_session, title="T") -> Test:
    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title=title, duration=30, question_count=0, status="draft")
    pg_session.add(test)
    pg_session.flush()
    return test


# --- 1/2: Admin and Super Admin can create a rule ---

def test_admin_can_create_rule(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test.id), "routing_group": "difficulty", "min_ratio": 0.7, "variant": "medium",
    }, headers=_auth(admin))

    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["test_id"] == str(test.id)
    assert body["routing_group"] == "difficulty"
    assert body["min_ratio"] == 0.7
    assert body["variant"] == "medium"


def test_super_admin_can_create_rule(client, pg_session):
    super_admin = _make_user(pg_session, "Super Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test.id), "routing_group": "difficulty", "min_ratio": 0.9, "variant": "hard",
    }, headers=_auth(super_admin))

    assert r.status_code == 201, r.text
    assert r.json()["data"]["variant"] == "hard"


# --- 3/4: Teacher and Student are rejected ---

def test_teacher_receives_403(client, pg_session):
    teacher = _make_user(pg_session, "Teacher")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test.id), "routing_group": "difficulty", "min_ratio": 0.5, "variant": "medium",
    }, headers=_auth(teacher))

    assert r.status_code == 403


def test_student_receives_403(client, pg_session):
    student = _make_user(pg_session, "Student")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.get("/api/v1/tests/routing-threshold-rules", params={"test_id": str(test.id)}, headers=_auth(student))

    assert r.status_code == 403


# --- 5/6: test-scoped, cross-test access rejected ---

def test_rule_is_test_scoped_and_cross_test_access_is_rejected(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test_a = _make_test(pg_session, "A")
    test_b = _make_test(pg_session, "B")
    pg_session.commit()

    r = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test_a.id), "routing_group": "difficulty", "min_ratio": 0.5, "variant": "medium",
    }, headers=_auth(admin))
    assert r.status_code == 201, r.text

    # Listing test_b's rules must NEVER include test_a's rule, even
    # though both use the identical routing_group name — this is the
    # exact DB-level scoping RoutingThresholdRuleRepository.list_for_test()
    # (and the UNIQUE(test_id, routing_group, min_ratio) constraint)
    # guarantee.
    r_a = client.get("/api/v1/tests/routing-threshold-rules", params={"test_id": str(test_a.id)}, headers=_auth(admin))
    r_b = client.get("/api/v1/tests/routing-threshold-rules", params={"test_id": str(test_b.id)}, headers=_auth(admin))
    assert len(r_a.json()["data"]) == 1
    assert len(r_b.json()["data"]) == 0


# --- 7: duplicate rejected ---

def test_duplicate_rule_rejected(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    r1 = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test.id), "routing_group": "difficulty", "min_ratio": 0.5, "variant": "medium",
    }, headers=_auth(admin))
    assert r1.status_code == 201

    r2 = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test.id), "routing_group": "difficulty", "min_ratio": 0.5, "variant": "medium_v2",
    }, headers=_auth(admin))
    assert r2.status_code == 409


# --- 8/9: min_ratio range validation ---

def test_min_ratio_below_zero_rejected(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test.id), "routing_group": "difficulty", "min_ratio": -0.1, "variant": "medium",
    }, headers=_auth(admin))

    assert r.status_code == 422


def test_min_ratio_above_one_rejected(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    r = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test.id), "routing_group": "difficulty", "min_ratio": 1.1, "variant": "medium",
    }, headers=_auth(admin))

    assert r.status_code == 422


# --- 10: PATCH works ---

def test_patch_updates_rule(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    created = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test.id), "routing_group": "difficulty", "min_ratio": 0.5, "variant": "medium",
    }, headers=_auth(admin)).json()["data"]

    r = client.patch(f"/api/v1/tests/routing-threshold-rules/{created['id']}", json={"min_ratio": 0.6, "variant": "medium_plus"}, headers=_auth(admin))

    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["min_ratio"] == 0.6
    assert body["variant"] == "medium_plus"
    assert body["test_id"] == str(test.id)  # unchanged — test_id is not patchable


# --- 11/12: DELETE soft-deletes; deleted rule not returned as active ---

def test_delete_soft_deletes_and_excludes_from_active_list(client, pg_session):
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    pg_session.commit()

    created = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test.id), "routing_group": "difficulty", "min_ratio": 0.5, "variant": "medium",
    }, headers=_auth(admin)).json()["data"]

    r = client.delete(f"/api/v1/tests/routing-threshold-rules/{created['id']}", headers=_auth(admin))
    assert r.status_code == 204

    # Row still exists (soft delete), but deleted_at is set and it is
    # excluded from the active list — proven at both the DB level and
    # through the real list endpoint.
    row = pg_session.execute(select(RoutingThresholdRule).where(RoutingThresholdRule.id == uuid.UUID(created["id"]))).scalar_one()
    assert row.deleted_at is not None

    listing = client.get("/api/v1/tests/routing-threshold-rules", params={"test_id": str(test.id)}, headers=_auth(admin))
    assert listing.json()["data"] == []

    # A second PATCH/DELETE against the now-deleted rule must 404 — it
    # is not "active" for any further admin operation either.
    patch_after_delete = client.patch(f"/api/v1/tests/routing-threshold-rules/{created['id']}", json={"variant": "x"}, headers=_auth(admin))
    assert patch_after_delete.status_code == 404


# --- 13: existing adaptive execution uses a rule created through this API ---

def test_admin_created_rule_is_used_by_real_execution(client, pg_session):
    """Proves the round trip: a rule created via the HTTP API (not
    direct ORM insertion, unlike test_sprint75_live_adaptive_routing.py's
    own tests) is what ModuleExecutionService._select_routing_strategy()
    actually reads — the only thing this sprint changes end-to-end."""
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session, "Adaptive")
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    easy = ExamModule(section_id=section.id, name="Easy", order_number=0, routing_group="difficulty", routing_variant="easy")
    hard = ExamModule(section_id=section.id, name="Hard", order_number=1, routing_group="difficulty", routing_variant="hard")
    pg_session.add_all([easy, hard])
    pg_session.commit()

    r = client.post("/api/v1/tests/routing-threshold-rules", json={
        "test_id": str(test.id), "routing_group": "difficulty", "min_ratio": 0.8, "variant": "hard",
    }, headers=_auth(admin))
    assert r.status_code == 201, r.text

    service = ModuleExecutionService(
        ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
        QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
        RoutingThresholdRuleRepository(pg_session),
    )
    strategy = service._select_routing_strategy(test.id, "difficulty")
    assert strategy.__class__.__name__ == "PerformanceThresholdRoutingStrategy"


# --- 14: no rules created -> sequential fallback remains unchanged ---

def test_no_rules_created_leaves_sequential_fallback_unchanged(client, pg_session):
    """A test with zero rules created through this new API — exactly
    every exam that existed before this completion pass — must still
    resolve to SequentialRoutingStrategy. This is the backward-
    compatibility guarantee the Sprint 75 base implementation already
    established; this test only confirms the new API's mere existence
    changes nothing for a test that never calls it."""
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session, "Untouched")
    section = ExamSection(test_id=test.id, name="Section", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="M1", order_number=0, routing_group="difficulty", routing_variant="easy")
    pg_session.add(module)
    pg_session.commit()

    listing = client.get("/api/v1/tests/routing-threshold-rules", params={"test_id": str(test.id)}, headers=_auth(admin))
    assert listing.json()["data"] == []

    service = ModuleExecutionService(
        ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
        QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
        RoutingThresholdRuleRepository(pg_session),
    )
    strategy = service._select_routing_strategy(test.id, "difficulty")
    assert strategy is service.routing_strategy
    assert strategy.__class__.__name__ == "SequentialRoutingStrategy"
