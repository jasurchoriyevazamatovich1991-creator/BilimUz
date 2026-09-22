"""
Sprint 59 — Attempt Finalize Race Condition Fix, against real
PostgreSQL. Reuses the exact real-concurrency pattern already proven in
this codebase (test_module_execution.py, test_result_section_creation.py,
test_sprint58_answer_race_condition.py) — a separate sessionmaker bound
to the real engine plus real threading.Thread workers, NOT the
pg_session fixture (its SAVEPOINT-based transaction can't exhibit real
cross-connection locking behavior) and NOT SQLite or any mock database.

Audit finding under test (Sprint 59 architecture audit, S59-A):
AttemptService.submit_attempt()/_finalize() obtained the TestAttempt
through the unlocked AttemptRepository.get_by_id() path before checking
whether it was already finalized and before writing score/percentage —
the same class of check-then-act race Sprint 50 fixed for
AttemptModuleProgress and Sprint 54 fixed for Result creation, left
unfixed for the attempt's own finalize transition. Fixed by
AttemptService._lock_attempt(), which reuses
AttemptRepository.get_by_id_locked() (SELECT ... FOR UPDATE +
populate_existing=True, introduced for Sprint 54) immediately before
the active-status check and the _finalize() write, on every
finalize-triggering call site: submit_attempt(),
_auto_finish_if_expired(), and submit_module()'s final-module
completion branch.

Deterministic race proof: a bare t1.start()/t2.start() (or even a
start-barrier before calling submit_attempt()) does not reliably force
two threads' FOR UPDATE statements to actually contend on this host —
see test_sprint58_answer_race_condition.py's own documented findings
for the same lesson. This file instead synchronizes at the exact
contention point: a test-only _LockSyncedAttemptRepository subclass
waits on a shared threading.Barrier immediately BEFORE issuing the
locked SELECT (AttemptRepository.get_by_id_locked()) — forcing both
threads to attempt the real PostgreSQL row lock at essentially the same
instant, so one is guaranteed to block on the other's transaction
inside Postgres itself, regardless of host scheduling/logging jitter.
"""
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.audit import AuditLog
from app.db.database import engine
from app.modules.attempts.constants import ACTIVE_STATUSES
from app.modules.attempts.exceptions import AttemptNotActiveException
from app.modules.attempts.models import AttemptStatus, TestAttempt
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

    Waits on a shared 2-party threading.Barrier immediately BEFORE
    calling the real get_by_id_locked() (the actual SELECT ... FOR
    UPDATE), so both threads issue their lock request at essentially
    the same instant — one is then guaranteed to block inside Postgres
    on the other's uncommitted transaction, rather than relying on
    ambient thread-scheduling luck. Never waits anywhere else (not on
    get_by_id(), not on commit()) — this is a pre-lock synchronization
    point only, analogous in spirit to Sprint 58's
    _WriteSyncedAnswerRepository, adapted to a SELECT FOR UPDATE
    contention point instead of an INSERT ON CONFLICT one."""

    barrier: threading.Barrier | None = None

    def get_by_id_locked(self, attempt_id: uuid.UUID) -> TestAttempt | None:
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        return super().get_by_id_locked(attempt_id)


def _setup_attempt(session, *, expired: bool = False):
    """Creates a Student user, Subject, published Test with one
    single_choice Question (correct + wrong option), and starts an
    attempt. Returns (attempt_id, student_id, test_id, subject_id,
    question_id). If expired=True, the attempt's expires_at is backdated
    so _auto_finish_if_expired() will treat it as expired."""
    from app.modules.grades.models import Grade  # noqa: F401 — side-effect import: registers the
    from app.modules.topics.models import Topic  # noqa: F401 — `grades`/`topics` tables in Base.metadata
    # before this raw sessionmaker(bind=engine) is used — see
    # test_sprint58_answer_race_condition.py's identical note; tests.models.Test
    # has an FK to grades that only resolves once something has imported it.

    role = session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="FR", last_name="RT", email=f"frrt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    session.add(user)
    session.flush()
    student_id = user.id

    subject = Subject(name=f"S-{uuid.uuid4()}")
    session.add(subject)
    session.flush()
    test = Test(subject_id=subject.id, title="Finalize Race Test", duration=30, question_count=1, status="published")
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

    service = _make_service(session)
    attempt = service.start_attempt(test.id, student_id)
    attempt_id, question_id = attempt.id, question.id
    test_id, subject_id = test.id, subject.id

    if expired:
        attempt_row = session.get(TestAttempt, attempt_id)
        attempt_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        session.flush()

    session.commit()
    return attempt_id, student_id, test_id, subject_id, question_id


def _cleanup(session, *, attempt_id, question_id, test_id, subject_id):
    session.query(AuditLog).filter(AuditLog.entity_id == attempt_id).delete()
    session.query(TestAttempt).filter(TestAttempt.id == attempt_id).delete()
    session.query(QuestionOption).filter(QuestionOption.question_id == question_id).delete()
    session.query(Question).filter(Question.test_id == test_id).delete()
    session.query(Test).filter(Test.id == test_id).delete()
    session.query(Subject).filter(Subject.id == subject_id).delete()
    session.commit()


# --- TEST A: true concurrent identical finalization (submit_attempt vs submit_attempt) ---

def test_concurrent_submit_attempt_is_race_safe():
    """Two threads call submit_attempt() for the SAME attempt at the
    same real-lock-contention instant. Before the fix: both would pass
    the unlocked active-status check and both would _finalize()+commit,
    producing two "attempt.submitted" audit rows. After the fix: the
    lock serializes them — exactly one succeeds and returns a normal
    result, the other observes the now-finalized status under the lock
    and raises AttemptNotActiveException (a clean, expected exception,
    not a database error) — and exactly one audit row exists."""
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        attempt_id, student_id, test_id, subject_id, question_id = _setup_attempt(setup)
    finally:
        setup.close()

    outcomes = {}
    barrier = threading.Barrier(2)

    def _synced_repo(session):
        repo = _LockSyncedAttemptRepository(session)
        repo.barrier = barrier
        return repo

    def worker(name: str):
        s = Session()
        svc = _make_service(s, attempt_repo=_synced_repo(s))
        try:
            result = svc.submit_attempt(attempt_id, student_id)
            outcomes[name] = ("OK", result)
        except AttemptNotActiveException:
            s.rollback()
            outcomes[name] = ("ALREADY_FINALIZED", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A",))
    t2 = threading.Thread(target=worker, args=("B",))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    results = [outcomes.get("A"), outcomes.get("B")]

    try:
        # Exactly one thread must succeed, the other must observe the
        # clean, expected AttemptNotActiveException — never an
        # unhandled database error.
        successes = [r for r in results if r is not None and r[0] == "OK"]
        already_finalized = [r for r in results if r is not None and r[0] == "ALREADY_FINALIZED"]
        errors = [r for r in results if r is not None and r[0] == "ERROR"]

        assert len(errors) == 0, f"expected no unhandled errors, got {results}"
        assert len(successes) == 1, f"expected exactly one thread to successfully finalize, got {results}"
        assert len(already_finalized) == 1, f"expected exactly one thread to observe the already-finalized state, got {results}"

        verify = Session()
        try:
            attempt_row = verify.get(TestAttempt, attempt_id)
            assert attempt_row.status == AttemptStatus.SUBMITTED.value

            audit_rows = verify.execute(
                select(AuditLog).where(AuditLog.entity_id == attempt_id, AuditLog.action == "attempt.submitted")
            ).scalars().all()
            # The whole point of the fix: exactly one audit-log row, not two.
            assert len(audit_rows) == 1, f"expected exactly 1 'attempt.submitted' audit row, got {len(audit_rows)}"
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            _cleanup(cleanup, attempt_id=attempt_id, question_id=question_id, test_id=test_id, subject_id=subject_id)
        finally:
            cleanup.close()


# --- TEST B: already-finalized attempt (sequential, pre-existing behavior preserved) ---

def test_submit_attempt_on_already_finalized_attempt_raises_as_before(pg_session):
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="AF", last_name="RT", email=f"afrt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()

    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Already Finalized Test", duration=30, question_count=1, status="published")
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
    attempt = service.start_attempt(test.id, user.id)
    pg_session.commit()

    # First submit — succeeds, finalizes normally.
    first = service.submit_attempt(attempt.id, user.id)
    pg_session.commit()
    assert first.status == AttemptStatus.SUBMITTED.value

    # Second submit on the SAME, now genuinely-already-finalized attempt —
    # existing behavior/exception preserved exactly, unchanged by Sprint 59.
    with pytest.raises(AttemptNotActiveException):
        service.submit_attempt(attempt.id, user.id)

    audit_rows = pg_session.execute(
        select(AuditLog).where(AuditLog.entity_id == attempt.id, AuditLog.action == "attempt.submitted")
    ).scalars().all()
    assert len(audit_rows) == 1


# --- TEST C: final-module completion path regression (submit_module's finalize branch) ---

def test_submit_module_final_completion_uses_locked_finalize(pg_session):
    """Regression for the third finalize-triggering path named in the
    audit: submit_module()'s final-module completion branch. Not a
    concurrency test (module completion is itself already serialized by
    Sprint 50's AttemptModuleProgress lock) — this only verifies the
    locked _finalize() path still produces exactly one correct
    finalization and one audit row when a modular attempt's last module
    is submitted, i.e. no regression from routing this branch through
    _lock_attempt()."""
    from app.modules.attempts.module_execution_service import ModuleExecutionService
    from app.modules.attempts.repository import AttemptModuleProgressRepository
    from app.modules.tests.models import ExamModule, ExamSection
    from app.modules.tests.repository import ExamModuleRepository

    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="MF", last_name="RT", email=f"mfrt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()

    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Module Finalize Test", duration=30, question_count=1, status="published")
    pg_session.add(test)
    pg_session.flush()

    section = ExamSection(test_id=test.id, name="Section 1", order_number=1, duration=30)
    pg_session.add(section)
    pg_session.flush()
    module = ExamModule(section_id=section.id, name="Module 1", order_number=1, duration=30)
    pg_session.add(module)
    pg_session.flush()

    question = Question(test_id=test.id, question_text="Only Q", question_type="single_choice", score=1, module_id=module.id)
    pg_session.add(question)
    pg_session.flush()
    correct = QuestionOption(question_id=question.id, option_text="A", is_correct=True)
    pg_session.add(correct)
    pg_session.flush()
    pg_session.commit()

    module_repo = ExamModuleRepository(pg_session)
    progress_repo = AttemptModuleProgressRepository(pg_session)
    question_repo = QuestionRepository(pg_session)
    answer_repo = AnswerRepository(pg_session)
    attempt_repo = AttemptRepository(pg_session)
    module_execution = ModuleExecutionService(module_repo, progress_repo, question_repo, answer_repo, attempt_repo)
    service = AttemptService(
        attempt_repo, answer_repo, TestRepository(pg_session), question_repo, OptionRepository(pg_session),
        module_execution_service=module_execution, module_repository=module_repo,
    )

    attempt = service.start_attempt(test.id, user.id)
    pg_session.commit()

    service.save_answer(attempt.id, user.id, question.id, selected_option=correct.id)
    pg_session.commit()

    outcome = service.submit_module(attempt.id, module.id, user.id)
    pg_session.commit()

    assert outcome["completed"] is True
    assert outcome["result"] is not None

    attempt_row = pg_session.get(TestAttempt, attempt.id)
    assert attempt_row.status == AttemptStatus.SUBMITTED.value

    audit_rows = pg_session.execute(
        select(AuditLog).where(AuditLog.entity_id == attempt.id, AuditLog.action == "attempt.submitted")
    ).scalars().all()
    assert len(audit_rows) == 1


# --- TEST D: auto-finish-if-expired regression (lazy expiry path) ---

def test_auto_finish_if_expired_uses_locked_finalize(pg_session):
    """Regression for the second finalize-triggering path named in the
    audit: _auto_finish_if_expired(). Sequential, not a concurrency
    test — verifies get_attempt() on an expired attempt still correctly
    auto-finalizes exactly once through the new locked path."""
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="EX", last_name="RT", email=f"exrt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()

    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Expiry Test", duration=30, question_count=1, status="published")
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
    attempt = service.start_attempt(test.id, user.id)
    pg_session.commit()

    attempt_row = pg_session.get(TestAttempt, attempt.id)
    attempt_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    pg_session.flush()
    pg_session.commit()

    resumed = service.get_attempt(attempt.id, user.id)
    pg_session.commit()

    assert resumed.status == AttemptStatus.AUTO_FINISHED.value

    # Calling get_attempt() again must be a no-op — the lock-guarded
    # re-check must not attempt to re-finalize an already-finalized
    # attempt.
    service.get_attempt(attempt.id, user.id)
    pg_session.commit()

    audit_rows = pg_session.execute(
        select(TestAttempt).where(TestAttempt.id == attempt.id)
    ).scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].status == AttemptStatus.AUTO_FINISHED.value
