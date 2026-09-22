"""
Sprint 60 — max_attempts Concurrency Race Fix (S60-A), against real
PostgreSQL. Reuses the exact real-concurrency pattern already proven in
this codebase (test_module_execution.py, test_result_section_creation.py,
test_sprint58_answer_race_condition.py, test_sprint59_attempt_finalize_race_condition.py)
— a separate sessionmaker bound to the real engine plus real
threading.Thread workers, NOT the pg_session fixture (its SAVEPOINT-based
transaction can't exhibit real cross-connection locking behavior) and NOT
SQLite or any mock database.

Audit finding under test (Sprint 60 architecture audit, S60-A):
AttemptService.start_attempt() did count_for_user_and_test() -> compare
against effective_max_attempts -> create(), with no synchronization
between the count and the create. Two concurrent start_attempt() calls
for the SAME (user_id, test_id) pair could both observe the same
pre-create count and both pass the max_attempts check, letting concurrent
requests create more attempts than Test.max_attempts allows — the same
class of check-then-act race Sprints 50/54/58/59 already fixed for other
state transitions, left unfixed here.

Fixed by AttemptRepository.acquire_start_attempt_lock(user_id, test_id),
called from start_attempt() immediately before count_for_user_and_test().
It issues `SELECT pg_advisory_xact_lock(hashtext(user_id), hashtext(test_id))`
— a transaction-scoped PostgreSQL advisory lock (not a row lock, since no
row necessarily exists yet for a user's first attempt at a test) that
serializes concurrent start_attempt() calls for the same pair and
auto-releases at COMMIT/ROLLBACK of the enclosing transaction, exactly
like the SELECT ... FOR UPDATE locks already used elsewhere in this
codebase.

Deterministic race proof: per the hard-won lesson from Sprint 58's review
(a bare t1.start()/t2.start(), or even a start-barrier before calling the
method under test, does not reliably force real contention on this host),
this file synchronizes at the exact contention point instead: a test-only
_LockSyncedAttemptRepository subclass waits on a shared threading.Barrier
immediately BEFORE issuing the real pg_advisory_xact_lock call — forcing
every thread to attempt the actual Postgres lock at essentially the same
instant, so all but one are guaranteed to block inside Postgres itself on
the lock-holder's uncommitted transaction, regardless of host
scheduling/logging jitter.
"""
import threading
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.database import engine
from app.modules.attempts.exceptions import MaxAttemptsExceededException
from app.modules.attempts.models import TestAttempt
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import Test
from app.modules.tests.repository import TestRepository
from app.modules.users.models import User, UserStatus


def _make_service(session, attempt_repo=None) -> AttemptService:
    return AttemptService(
        attempt_repo if attempt_repo is not None else AttemptRepository(session),
        AnswerRepository(session), TestRepository(session),
        QuestionRepository(session), OptionRepository(session),
    )


class _LockSyncedAttemptRepository(AttemptRepository):
    """Test-only synchronization aid — never used by application code.

    Waits on a shared N-party threading.Barrier immediately BEFORE
    calling the real acquire_start_attempt_lock() (the actual
    pg_advisory_xact_lock statement), so every worker thread issues its
    lock request at essentially the same instant — all but one are then
    guaranteed to block inside Postgres on the lock-holder's uncommitted
    transaction, rather than relying on ambient thread-scheduling luck.
    Never waits anywhere else (not on count_for_user_and_test(), not on
    create(), not on commit()) — this is a pre-lock synchronization point
    only, exactly analogous to Sprint 59's _LockSyncedAttemptRepository
    (which synchronized before get_by_id_locked()) and Sprint 58's
    _WriteSyncedAnswerRepository (before the atomic upsert write)."""

    barrier: threading.Barrier | None = None

    def acquire_start_attempt_lock(self, user_id: uuid.UUID, test_id: uuid.UUID) -> None:
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        return super().acquire_start_attempt_lock(user_id, test_id)


def _setup_test(session, *, max_attempts: int | None):
    """Creates a Subject and a published Test with one single_choice
    Question, with the given max_attempts (None = platform default).
    Returns (test_id, subject_id, question_id)."""
    from app.modules.grades.models import Grade  # noqa: F401 — side-effect import: registers the
    from app.modules.topics.models import Topic  # noqa: F401 — `grades`/`topics` tables in Base.metadata
    # before this raw sessionmaker(bind=engine) is used — see
    # test_sprint58/59's identical note; tests.models.Test has an FK to
    # grades that only resolves once something has imported it.

    subject = Subject(name=f"S-{uuid.uuid4()}")
    session.add(subject)
    session.flush()
    test = Test(
        subject_id=subject.id, title="Max Attempts Race Test", duration=30,
        question_count=1, status="published", max_attempts=max_attempts,
    )
    session.add(test)
    session.flush()

    question = Question(test_id=test.id, question_text="2+2=?", question_type="single_choice", score=1)
    session.add(question)
    session.flush()
    correct = QuestionOption(question_id=question.id, option_text="4", is_correct=True)
    wrong = QuestionOption(question_id=question.id, option_text="5", is_correct=False)
    session.add_all([correct, wrong])
    session.flush()
    session.commit()

    return test.id, subject.id, question.id


def _make_student(session, tag: str) -> uuid.UUID:
    role = session.query(Role).filter(Role.name == "Student").one()
    user = User(
        role_id=role.id, first_name=tag, last_name="RT",
        email=f"{tag.lower()}-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.flush()
    session.commit()
    return user.id


def _cleanup(session, *, user_ids, test_id, subject_id, question_id):
    from app.core.audit import AuditLog

    # start_attempt() writes an "attempt.started" AuditLog row keyed by
    # user_id (fk_audit_logs_user_id) — must go before the Users delete
    # below, or it raises a ForeignKeyViolation exactly like deleting a
    # TestAttempt's own audit rows would (see Sprint 59's _cleanup, which
    # deletes AuditLog by entity_id for the same reason).
    session.query(AuditLog).filter(AuditLog.user_id.in_(user_ids)).delete(synchronize_session=False)
    session.query(TestAttempt).filter(TestAttempt.test_id == test_id).delete()
    session.query(QuestionOption).filter(QuestionOption.question_id == question_id).delete()
    session.query(Question).filter(Question.test_id == test_id).delete()
    session.query(Test).filter(Test.id == test_id).delete()
    session.query(Subject).filter(Subject.id == subject_id).delete()
    session.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    session.commit()


def _run_concurrent_starts(test_id, student_id, n: int):
    """Fires n concurrent start_attempt() calls for the SAME (student_id,
    test_id) pair, each on its own session/connection, synchronized to
    attempt the advisory lock at the same instant. Returns a dict of
    outcomes keyed by worker index: ("OK", attempt) | ("REJECTED", None) |
    ("ERROR", exc_type_name)."""
    Session = sessionmaker(bind=engine)
    outcomes: dict[int, tuple] = {}
    barrier = threading.Barrier(n)

    def _synced_repo(session):
        repo = _LockSyncedAttemptRepository(session)
        repo.barrier = barrier
        return repo

    def worker(i: int):
        s = Session()
        svc = _make_service(s, attempt_repo=_synced_repo(s))
        try:
            attempt = svc.start_attempt(test_id, student_id)
            outcomes[i] = ("OK", attempt)
        except MaxAttemptsExceededException:
            s.rollback()
            outcomes[i] = ("REJECTED", None)
        except Exception as e:
            s.rollback()
            outcomes[i] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    return outcomes


# --- TEST 1: max_attempts = 1, two concurrent starts for the same user ---

def test_concurrent_start_attempt_with_max_attempts_one_allows_exactly_one():
    """Two threads call start_attempt() for the SAME (user, test) pair at
    the same real-lock-contention instant, with max_attempts=1 and zero
    existing attempts. Before the fix: both could observe count=0 and
    both create an attempt (2 attempts for a limit of 1). After the fix:
    the advisory lock serializes them — exactly one succeeds, the other
    observes count=1 under the lock and is correctly rejected — and the
    database contains exactly one TestAttempt row."""
    Session = sessionmaker(bind=engine)
    setup = Session()
    try:
        test_id, subject_id, question_id = _setup_test(setup, max_attempts=1)
        student_id = _make_student(setup, "R1")
    finally:
        setup.close()

    try:
        outcomes = _run_concurrent_starts(test_id, student_id, n=2)
        results = list(outcomes.values())

        errors = [r for r in results if r[0] == "ERROR"]
        successes = [r for r in results if r[0] == "OK"]
        rejected = [r for r in results if r[0] == "REJECTED"]

        assert len(errors) == 0, f"expected no unhandled errors, got {results}"
        assert len(successes) == 1, f"expected exactly one thread to succeed, got {results}"
        assert len(rejected) == 1, f"expected exactly one thread to be rejected, got {results}"

        verify = Session()
        try:
            count = verify.execute(
                select(TestAttempt).where(TestAttempt.test_id == test_id, TestAttempt.user_id == student_id)
            ).scalars().all()
            assert len(count) == 1, f"expected exactly 1 attempt row in the database, got {len(count)}"
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            _cleanup(cleanup, user_ids=[student_id], test_id=test_id, subject_id=subject_id, question_id=question_id)
        finally:
            cleanup.close()


# --- TEST 2: max_attempts = 2, four concurrent starts for the same user ---

def test_concurrent_start_attempt_with_max_attempts_two_allows_exactly_two():
    """Four threads call start_attempt() for the SAME (user, test) pair
    concurrently, with max_attempts=2 and zero existing attempts. The
    advisory lock serializes all four through the count -> check ->
    create critical section one at a time: exactly two succeed (the
    first two to acquire the lock, in whatever order the scheduler
    picks), the other two observe count=2 under the lock and are
    rejected. The database contains exactly two TestAttempt rows."""
    Session = sessionmaker(bind=engine)
    setup = Session()
    try:
        test_id, subject_id, question_id = _setup_test(setup, max_attempts=2)
        student_id = _make_student(setup, "R2")
    finally:
        setup.close()

    try:
        outcomes = _run_concurrent_starts(test_id, student_id, n=4)
        results = list(outcomes.values())

        errors = [r for r in results if r[0] == "ERROR"]
        successes = [r for r in results if r[0] == "OK"]
        rejected = [r for r in results if r[0] == "REJECTED"]

        assert len(errors) == 0, f"expected no unhandled errors, got {results}"
        assert len(successes) == 2, f"expected exactly two threads to succeed, got {results}"
        assert len(rejected) == 2, f"expected exactly two threads to be rejected, got {results}"

        verify = Session()
        try:
            rows = verify.execute(
                select(TestAttempt).where(TestAttempt.test_id == test_id, TestAttempt.user_id == student_id)
            ).scalars().all()
            assert len(rows) == 2, f"expected exactly 2 attempt rows in the database, got {len(rows)}"
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            _cleanup(cleanup, user_ids=[student_id], test_id=test_id, subject_id=subject_id, question_id=question_id)
        finally:
            cleanup.close()


# --- TEST 3: different users concurrently — must NOT unnecessarily serialize ---

def test_concurrent_start_attempt_different_users_both_succeed():
    """Two different users starting the SAME test concurrently use
    different advisory lock keys (hashtext(user_id) differs per user), so
    they must not block each other's max_attempts check: with
    max_attempts=1 and zero existing attempts for either user, both
    concurrent starts must succeed."""
    Session = sessionmaker(bind=engine)
    setup = Session()
    try:
        test_id, subject_id, question_id = _setup_test(setup, max_attempts=1)
        student_a = _make_student(setup, "DA")
        student_b = _make_student(setup, "DB")
    finally:
        setup.close()

    outcomes = {}
    # No barrier needed to prove correctness here (different lock keys
    # can't contend by construction) — a plain concurrent start for each
    # user is enough to prove neither is incorrectly rejected due to the
    # other's in-flight transaction.
    barrier = threading.Barrier(2)

    def _synced_repo(session):
        repo = _LockSyncedAttemptRepository(session)
        repo.barrier = barrier
        return repo

    def worker(name: str, user_id):
        s = Session()
        svc = _make_service(s, attempt_repo=_synced_repo(s))
        try:
            attempt = svc.start_attempt(test_id, user_id)
            outcomes[name] = ("OK", attempt)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    try:
        t1 = threading.Thread(target=worker, args=("A", student_a))
        t2 = threading.Thread(target=worker, args=("B", student_b))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert outcomes.get("A", (None,))[0] == "OK", f"user A should have succeeded, got {outcomes.get('A')}"
        assert outcomes.get("B", (None,))[0] == "OK", f"user B should have succeeded, got {outcomes.get('B')}"

        verify = Session()
        try:
            rows_a = verify.execute(
                select(TestAttempt).where(TestAttempt.test_id == test_id, TestAttempt.user_id == student_a)
            ).scalars().all()
            rows_b = verify.execute(
                select(TestAttempt).where(TestAttempt.test_id == test_id, TestAttempt.user_id == student_b)
            ).scalars().all()
            assert len(rows_a) == 1
            assert len(rows_b) == 1
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            _cleanup(cleanup, user_ids=[student_a, student_b], test_id=test_id, subject_id=subject_id, question_id=question_id)
        finally:
            cleanup.close()


# --- TEST 4: sequential regression — normal behavior unchanged ---

def test_sequential_start_attempt_rejects_second_when_max_attempts_reached(pg_session):
    """Not a concurrency test — proves the advisory lock introduces zero
    behavior change for the ordinary, non-racing sequential case: a
    second start_attempt() call for a test with max_attempts=1, made
    strictly after the first one has committed, must still be rejected
    exactly as before Sprint 60."""
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(
        role_id=role.id, first_name="SQ", last_name="RT",
        email=f"sqrt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()

    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(
        subject_id=subject.id, title="Sequential Max Attempts Test", duration=30,
        question_count=1, status="published", max_attempts=1,
    )
    pg_session.add(test)
    pg_session.flush()
    question = Question(test_id=test.id, question_text="Pick one", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.flush()
    correct = QuestionOption(question_id=question.id, option_text="A", is_correct=True)
    pg_session.add(correct)
    pg_session.flush()
    pg_session.commit()

    service = _make_service(pg_session)

    first = service.start_attempt(test.id, user.id)
    pg_session.commit()
    assert first is not None

    with pytest.raises(MaxAttemptsExceededException):
        service.start_attempt(test.id, user.id)

    rows = pg_session.execute(
        select(TestAttempt).where(TestAttempt.test_id == test.id, TestAttempt.user_id == user.id)
    ).scalars().all()
    assert len(rows) == 1
