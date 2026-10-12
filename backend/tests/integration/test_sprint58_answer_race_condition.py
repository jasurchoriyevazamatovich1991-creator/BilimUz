"""
Sprint 58 — Answer Race Condition Fix, against real PostgreSQL. Reuses
the exact real-concurrency pattern already proven in this codebase
(test_module_execution.py::test_concurrent_module_submit_is_race_safe,
test_result_section_creation.py::test_concurrent_result_creation_is_race_safe)
— a separate sessionmaker bound to the real engine plus real
threading.Thread workers, NOT the pg_session fixture (its SAVEPOINT-based
transaction can't exhibit real cross-connection locking/conflict
behavior) and NOT SQLite or any mock database.

Audit finding under test (Sprint 57/58 architecture audits, corrected
during this sprint's implementation): AttemptService.save_answer() used
to do an unprotected check-then-act — AnswerRepository.get() then
create()/update() — with no code path that expected the insert to be
rejected. It turns out uq_answers_attempt_question (UNIQUE on
(attempt_id, question_id)) has existed in the database since migration
0001 — so a duplicate Answer row was never actually possible — but the
real bug was that the losing side of a race would raise an UNHANDLED
IntegrityError (a 500) instead of succeeding gracefully. Fixed by
AnswerRepository.upsert(), a single atomic INSERT ... ON CONFLICT DO
UPDATE against that exact constraint.

Sprint 82 update (Package 1 interaction): save_answer() now calls
self._lock_attempt(attempt) — a real `SELECT ... FOR UPDATE` against
the attempt row — BEFORE it ever reaches the answer-repo write step
this test used to synchronize on. That made the original
_WriteSyncedAnswerRepository barrier (synced at the write statement)
produce a real deadlock: the lock-winning thread would acquire the
attempt's row lock and then block on the barrier waiting for the
lock-losing thread, which could never arrive at that barrier because
it was itself blocked at the Postgres level waiting for the winner's
lock to release — confirmed directly: the losing thread's `SELECT ...
FOR UPDATE` sat for the full 10s barrier timeout, then both threads
rolled back with a BrokenBarrierError, caught by this test's generic
`except Exception` as an "ERROR" outcome.

Fixed here by moving the synchronization point to match the new real
earliest contention point for two concurrent save_answer() calls on
the same attempt: the attempt-row lock itself, exactly mirroring
test_sprint59_attempt_finalize_race_condition.py's and
test_sprint82_answer_saving_attempt_finalize_race.py's own
_LockSyncedAttemptRepository technique (wait on the barrier
immediately BEFORE issuing the real locked SELECT, never after a
write). This keeps the test's original intent — prove exactly one
Answer row results, no unhandled error — fully intact, now compatible
with Package 1's new lock ordering.
"""
import threading
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.database import engine
from app.modules.attempts.models import Answer, TestAttempt
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.models import Question, QuestionOption
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import Test
from app.modules.tests.repository import TestRepository
from app.modules.users.models import User, UserStatus


def _make_service(session, attempt_repo: AttemptRepository | None = None) -> AttemptService:
    return AttemptService(
        attempt_repo if attempt_repo is not None else AttemptRepository(session), AnswerRepository(session),
        TestRepository(session), QuestionRepository(session), OptionRepository(session),
    )


class _LockSyncedAttemptRepository(AttemptRepository):
    """Test-only synchronization aid — never used by application code.

    Review finding (original Sprint 58 version of this test): real
    Postgres round-trips on this host are fast enough (sub-millisecond)
    that two threads simply started together (`t1.start(); t2.start()`),
    or even released together from a barrier placed BEFORE
    `save_answer()` is called, do not reliably overlap — one thread can
    run its entire request to completion before the other issues its
    first query, especially once SQL echo logging (which was
    accidentally adding GIL-yielding I/O and masking this) is off, as it
    is in the real test suite (`echo=settings.DEBUG`, False under
    pytest).

    Sprint 82 update: since AttemptService.save_answer() now calls
    self._lock_attempt(attempt) (a real `SELECT ... FOR UPDATE`) BEFORE
    it ever reaches the answer-repo write step, that write step is no
    longer the earliest point where two concurrent save_answer() calls
    on the same attempt actually contend — the attempt-row lock
    acquisition is. Synchronizing at the OLD (write) point now deadlocks
    on this host, the way to actually understand this is: the
    lock-winning thread would acquire the real Postgres row lock,
    continue to the write step, and then block on this test's own
    barrier waiting for the lock-losing thread — which can never arrive
    there because it's still blocked at the DB level waiting for the
    winner's lock to release. Moving the barrier to wait immediately
    BEFORE the real locked SELECT (this class, identical technique to
    test_sprint59_attempt_finalize_race_condition.py's and
    test_sprint82_answer_saving_attempt_finalize_race.py's own
    _LockSyncedAttemptRepository) forces both threads' lock requests to
    hit Postgres at essentially the same instant, with no wait of any
    kind after a write — so there is no deadlock risk: the lock loser
    simply queues at the real Postgres row lock (resolved in finite
    time, exactly as it would in production) while the winner proceeds
    all the way through its own commit."""

    barrier: threading.Barrier | None = None

    def get_by_id_locked(self, attempt_id: uuid.UUID) -> TestAttempt | None:
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        return super().get_by_id_locked(attempt_id)


# --- TEST A: true concurrent identical answer requests ---

def test_concurrent_identical_answer_requests_produce_exactly_one_row():
    """Before the fix: one of the two threads' create() would raise an
    unhandled IntegrityError against uq_answers_attempt_question — this
    test's own git-history proof (see the implementation report) showed
    that exact failure on the pre-fix code. After the fix: both threads
    succeed (the loser's INSERT becomes an UPDATE via ON CONFLICT), and
    exactly one Answer row exists for (attempt_id, question_id)."""
    from app.modules.grades.models import Grade  # noqa: F401 — side-effect import: registers the `grades` table
    # in Base.metadata before this raw sessionmaker(bind=engine) is used,
    # exactly as test_result_section_creation.py's and
    # test_module_execution.py's own real-concurrency tests already do —
    # tests.models.Test has an FK to grades that only resolves once
    # something has imported the grades module (normally done as a
    # side-effect of the app.main import a TestClient-based fixture
    # pulls in; this test uses neither, so it needs the same explicit
    # import those two established tests use).
    from app.modules.topics.models import Topic  # noqa: F401

    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        role = setup.query(Role).filter(Role.name == "Student").one()
        user = User(role_id=role.id, first_name="RC", last_name="RT", email=f"rcrt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
        setup.add(user)
        setup.flush()
        student_id = user.id

        subject = Subject(name=f"S-{uuid.uuid4()}")
        setup.add(subject)
        setup.flush()
        test = Test(subject_id=subject.id, title="Race Test", duration=30, question_count=1, status="published")
        setup.add(test)
        setup.flush()

        question = Question(test_id=test.id, question_text="2+2=?", question_type="single_choice", score=1)
        setup.add(question)
        setup.flush()
        correct = QuestionOption(question_id=question.id, option_text="4", is_correct=True)
        wrong = QuestionOption(question_id=question.id, option_text="5", is_correct=False)
        setup.add_all([correct, wrong])
        setup.flush()
        setup.commit()

        service = _make_service(setup)
        attempt = service.start_attempt(test.id, student_id)
        attempt_id, question_id, correct_option_id = attempt.id, question.id, correct.id
        test_id, subject_id = test.id, subject.id
        setup.commit()
    finally:
        setup.close()

    outcomes = {}
    # Review finding: neither bare t1.start()/t2.start() nor a barrier
    # placed before save_answer() reliably overlaps on this host once
    # SQL echo logging is off (the real pytest condition — echo is tied
    # to settings.DEBUG). Sprint 82: synchronizing at the attempt-row
    # lock acquisition (see _LockSyncedAttemptRepository's docstring) is
    # now the correct point — it's the earliest real contention point
    # for two concurrent save_answer() calls on the same attempt, and
    # waiting there (never after a write) carries no deadlock risk.
    lock_barrier = threading.Barrier(2)

    def _synced_repo(session) -> _LockSyncedAttemptRepository:
        repo = _LockSyncedAttemptRepository(session)
        repo.barrier = lock_barrier
        return repo

    def worker(name: str):
        s = Session()
        svc = _make_service(s, attempt_repo=_synced_repo(s))
        try:
            svc.save_answer(attempt_id, student_id, question_id, selected_option=correct_option_id)
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A",))
    t2 = threading.Thread(target=worker, args=("B",))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    results = [outcomes.get("A"), outcomes.get("B")]

    try:
        # The whole point of the fix: BOTH concurrent requests succeed —
        # neither one crashes with an unhandled IntegrityError.
        successes = [r for r in results if r is not None and r[0] == "OK"]
        assert len(successes) == 2, f"expected both requests to succeed gracefully, got {results}"

        verify = Session()
        try:
            rows = verify.execute(
                select(Answer).where(Answer.attempt_id == attempt_id, Answer.question_id == question_id)
            ).scalars().all()
            # Exactly one Answer row — never duplicated, never crashed.
            assert len(rows) == 1, f"expected exactly 1 Answer row, got {len(rows)}"
            assert rows[0].selected_option == correct_option_id
            assert rows[0].is_correct is True
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(Answer).filter(Answer.attempt_id == attempt_id).delete()
            cleanup.query(TestAttempt).filter(TestAttempt.id == attempt_id).delete()
            cleanup.query(QuestionOption).filter(QuestionOption.question_id == question_id).delete()
            cleanup.query(Question).filter(Question.test_id == test_id).delete()
            cleanup.query(Test).filter(Test.id == test_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# --- TEST B: sequential create-then-update regression (pg_session is fine here — no true concurrency needed) ---

def test_sequential_create_then_update_stays_a_single_row(pg_session):
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="SQ", last_name="RT", email=f"sqrt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()

    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Update Test", duration=30, question_count=1, status="published")
    pg_session.add(test)
    pg_session.flush()

    question = Question(test_id=test.id, question_text="Pick one", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.flush()
    option_a = QuestionOption(question_id=question.id, option_text="A", is_correct=True)
    option_b = QuestionOption(question_id=question.id, option_text="B", is_correct=False)
    pg_session.add_all([option_a, option_b])
    pg_session.flush()
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, user.id)
    pg_session.commit()

    # First save — creates the row.
    service.save_answer(attempt.id, user.id, question.id, selected_option=option_a.id)
    pg_session.commit()

    rows_after_create = pg_session.execute(
        select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id == question.id)
    ).scalars().all()
    assert len(rows_after_create) == 1
    assert rows_after_create[0].selected_option == option_a.id
    assert rows_after_create[0].is_correct is True

    # Second save, different selection — must UPDATE the same row, not
    # create a second one.
    service.save_answer(attempt.id, user.id, question.id, selected_option=option_b.id)
    pg_session.commit()

    rows_after_update = pg_session.execute(
        select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id == question.id)
    ).scalars().all()
    assert len(rows_after_update) == 1
    assert rows_after_update[0].id == rows_after_create[0].id  # same row, not a new one
    assert rows_after_update[0].selected_option == option_b.id
    assert rows_after_update[0].is_correct is False


# --- TEST C: multiple_choice upsert regression (both branches of save_answer) ---

def test_multiple_choice_sequential_create_then_update_stays_a_single_row(pg_session):
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="MC", last_name="RT", email=f"mcrt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()

    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="MC Update Test", duration=30, question_count=1, status="published")
    pg_session.add(test)
    pg_session.flush()

    question = Question(test_id=test.id, question_text="Pick all correct", question_type="multiple_choice", score=1)
    pg_session.add(question)
    pg_session.flush()
    opt_a = QuestionOption(question_id=question.id, option_text="A", is_correct=True)
    opt_b = QuestionOption(question_id=question.id, option_text="B", is_correct=True)
    opt_c = QuestionOption(question_id=question.id, option_text="C", is_correct=False)
    pg_session.add_all([opt_a, opt_b, opt_c])
    pg_session.flush()
    pg_session.commit()

    service = _make_service(pg_session)
    attempt = service.start_attempt(test.id, user.id)
    pg_session.commit()

    # First save — partial, wrong selection.
    service.save_answer(attempt.id, user.id, question.id, selected_option=None, selected_options=[opt_a.id])
    pg_session.commit()

    rows = pg_session.execute(
        select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id == question.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_correct is False  # missing opt_b

    # Second save — corrected, full selection. Must update the same row.
    service.save_answer(attempt.id, user.id, question.id, selected_option=None, selected_options=[opt_a.id, opt_b.id])
    pg_session.commit()

    rows_after = pg_session.execute(
        select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id == question.id)
    ).scalars().all()
    assert len(rows_after) == 1
    assert rows_after[0].id == rows[0].id
    assert set(rows_after[0].selected_options) == {opt_a.id, opt_b.id}
    assert rows_after[0].is_correct is True
    assert rows_after[0].selected_option is None
