"""
Sprint 82 — Package 1 (Answer-Saving Concurrency), against real
PostgreSQL. Reuses the exact real-concurrency pattern already proven in
this codebase (test_sprint59_attempt_finalize_race_condition.py,
test_sprint58_answer_race_condition.py) — a separate sessionmaker bound
to the real engine plus real threading.Thread workers, NOT the
pg_session fixture (its SAVEPOINT-based transaction can't exhibit real
cross-connection locking behavior) and NOT SQLite or any mock database.

Defect under test: AttemptService.save_answer() read the attempt
through the unlocked AttemptRepository.get_by_id() path (via
_get_owned_attempt()) and checked `attempt.status not in
ACTIVE_STATUSES` WITHOUT ever re-acquiring the row lock
submit_attempt()/submit_module()/_auto_finish_if_expired() already use
(AttemptService._lock_attempt(), Sprint 59) before their own equivalent
check. A concurrent submit_attempt() (a different DB session/
transaction) could finalize and commit the attempt AFTER save_answer()'s
unlocked status check passed but BEFORE save_answer()'s own
answer_repo.upsert()+commit() — silently persisting an Answer the
already-committed score/percentage could never reflect.

Fix: save_answer() now calls self._lock_attempt(attempt) (the same
SELECT ... FOR UPDATE + populate_existing=True path) immediately before
its active-status check, exactly mirroring submit_attempt()'s own
"lock BEFORE the active-status check" convention. Since save_answer()
and submit_attempt() now contend for the exact same row lock, this test
reuses test_sprint59's exact synchronization technique — a
_LockSyncedAttemptRepository subclass that waits on a shared
threading.Barrier immediately before issuing the real locked SELECT, so
both threads' FOR UPDATE statements are forced to contend at the same
instant regardless of host scheduling.

Either lock-acquisition order is an ACCEPTABLE, consistent outcome:
  - save_answer() wins the lock first: it commits the answer (attempt
    still in_progress), releases the lock, then submit_attempt() wins
    the lock next and finalizes/scores INCLUDING that just-committed
    answer.
  - submit_attempt() wins the lock first: it finalizes/commits and
    releases the lock, then save_answer() wins the lock next, re-reads
    the now-"submitted" status under its own lock, and cleanly raises
    AttemptNotActiveException — no Answer row is ever written for the
    already-finalized attempt.
What must NEVER happen (the pre-fix bug): save_answer() silently
succeeds and writes an Answer row for an attempt that was ALREADY
finalized before save_answer()'s own lock acquisition — i.e. a
committed Answer that the attempt's final score does not account for.
"""
import threading
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.audit import AuditLog
from app.db.database import engine
from app.modules.attempts.exceptions import AttemptNotActiveException
from app.modules.attempts.models import Answer, AttemptStatus, TestAttempt
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
    Identical technique to test_sprint59_attempt_finalize_race_condition.py's
    own _LockSyncedAttemptRepository: waits on a shared 2-party
    threading.Barrier immediately BEFORE calling the real
    get_by_id_locked() (the actual SELECT ... FOR UPDATE), forcing both
    threads to issue their lock request at essentially the same
    instant."""

    barrier: threading.Barrier | None = None

    def get_by_id_locked(self, attempt_id: uuid.UUID) -> TestAttempt | None:
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        return super().get_by_id_locked(attempt_id)


def _setup_attempt(session):
    from app.modules.grades.models import Grade  # noqa: F401 — side-effect import: registers the
    from app.modules.topics.models import Topic  # noqa: F401 — `grades`/`topics` tables in Base.metadata
    # before this raw sessionmaker(bind=engine) is used — see
    # test_sprint58/59's identical note.

    role = session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="S82", last_name="A1", email=f"s82a1-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    session.add(user)
    session.flush()
    student_id = user.id

    subject = Subject(name=f"S-{uuid.uuid4()}")
    session.add(subject)
    session.flush()
    test = Test(subject_id=subject.id, title="Sprint 82 Answer Race Test", duration=30, question_count=1, status="published")
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
    attempt_id, question_id, correct_option_id = attempt.id, question.id, correct.id
    test_id, subject_id = test.id, subject.id
    session.commit()
    return attempt_id, student_id, test_id, subject_id, question_id, correct_option_id


def _cleanup(session, *, attempt_id, question_id, test_id, subject_id):
    session.query(AuditLog).filter(AuditLog.entity_id == attempt_id).delete()
    session.query(Answer).filter(Answer.attempt_id == attempt_id).delete()
    session.query(TestAttempt).filter(TestAttempt.id == attempt_id).delete()
    session.query(QuestionOption).filter(QuestionOption.question_id == question_id).delete()
    session.query(Question).filter(Question.test_id == test_id).delete()
    session.query(Test).filter(Test.id == test_id).delete()
    session.query(Subject).filter(Subject.id == subject_id).delete()
    session.commit()


def test_concurrent_save_answer_and_submit_attempt_never_leaves_an_orphaned_answer():
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        attempt_id, student_id, test_id, subject_id, question_id, correct_option_id = _setup_attempt(setup)
    finally:
        setup.close()

    outcomes = {}
    barrier = threading.Barrier(2)

    def _synced_repo(session):
        repo = _LockSyncedAttemptRepository(session)
        repo.barrier = barrier
        return repo

    def save_answer_worker():
        s = Session()
        svc = _make_service(s, attempt_repo=_synced_repo(s))
        try:
            svc.save_answer(attempt_id, student_id, question_id, selected_option=correct_option_id)
            outcomes["save_answer"] = ("OK", None)
        except AttemptNotActiveException:
            s.rollback()
            outcomes["save_answer"] = ("ALREADY_FINALIZED", None)
        except Exception as e:
            s.rollback()
            outcomes["save_answer"] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    def submit_worker():
        s = Session()
        svc = _make_service(s, attempt_repo=_synced_repo(s))
        try:
            result = svc.submit_attempt(attempt_id, student_id)
            outcomes["submit"] = ("OK", result)
        except AttemptNotActiveException:
            s.rollback()
            outcomes["submit"] = ("ALREADY_FINALIZED", None)
        except Exception as e:
            s.rollback()
            outcomes["submit"] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=save_answer_worker)
    t2 = threading.Thread(target=submit_worker)
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    try:
        save_outcome = outcomes.get("save_answer")
        submit_outcome = outcomes.get("submit")

        assert save_outcome is not None and submit_outcome is not None, f"a worker did not finish: {outcomes}"
        assert save_outcome[0] != "ERROR", f"save_answer must never raise an unhandled error, got {save_outcome}"
        assert submit_outcome[0] != "ERROR", f"submit_attempt must never raise an unhandled error, got {submit_outcome}"

        # submit_attempt always eventually succeeds — nothing here ever
        # contends against a second submit.
        assert submit_outcome[0] == "OK", f"expected submit_attempt to succeed, got {submit_outcome}"

        verify = Session()
        try:
            attempt_row = verify.get(TestAttempt, attempt_id)
            assert attempt_row.status == AttemptStatus.SUBMITTED.value

            answer_rows = verify.execute(
                select(Answer).where(Answer.attempt_id == attempt_id, Answer.question_id == question_id)
            ).scalars().all()

            if save_outcome[0] == "OK":
                # save_answer won the lock first (and committed before
                # submit's own lock acquisition) — the answer MUST exist
                # and MUST be reflected in the finalized attempt's score,
                # never silently orphaned.
                assert len(answer_rows) == 1, "save_answer succeeded but its Answer row is missing"
                assert attempt_row.score == 1.0, (
                    "save_answer's committed answer was not reflected in the finalized score — "
                    "this is exactly the race this fix closes"
                )
                assert attempt_row.percentage == 100.0
            else:
                # submit_attempt won the lock first and finalized before
                # save_answer's own lock acquisition — save_answer must
                # have cleanly rejected the write, and NO Answer row may
                # exist for an attempt that was already finalized at the
                # time save_answer's lock was granted.
                assert save_outcome[0] == "ALREADY_FINALIZED", f"unexpected save_answer outcome: {save_outcome}"
                assert len(answer_rows) == 0, (
                    "save_answer must not silently persist an Answer row after the attempt "
                    "was already finalized — this is exactly the pre-fix bug"
                )
                assert attempt_row.score == 0.0
                assert attempt_row.percentage == 0.0
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            _cleanup(cleanup, attempt_id=attempt_id, question_id=question_id, test_id=test_id, subject_id=subject_id)
        finally:
            cleanup.close()


def test_save_answer_on_already_submitted_attempt_raises_and_writes_nothing(pg_session):
    """Sequential regression (no real concurrency needed): save_answer()
    on an attempt that is ALREADY submitted — the baseline, non-racy
    case the fix must not disturb — still raises AttemptNotActiveException
    and never writes an Answer row."""
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="S82", last_name="A2", email=f"s82a2-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()

    subject = Subject(name=f"S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Already Submitted Answer Test", duration=30, question_count=1, status="published")
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

    service.submit_attempt(attempt.id, user.id)
    pg_session.commit()

    with pytest.raises(AttemptNotActiveException):
        service.save_answer(attempt.id, user.id, question.id, selected_option=correct.id)

    rows = pg_session.execute(
        select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id == question.id)
    ).scalars().all()
    assert len(rows) == 0
