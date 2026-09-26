"""
Sprint 64 — C6. Statistics Atomic Upsert, against real PostgreSQL. Reuses
the exact real-concurrency pattern already established in this codebase
(test_sprint58_answer_race_condition.py, test_module_execution.py::
test_concurrent_module_submit_is_race_safe, test_result_section_creation.py::
test_concurrent_result_creation_is_race_safe) — a separate sessionmaker
bound to the real engine plus real threading.Thread workers and a
write-synchronizing threading.Barrier, NOT the pg_session fixture (its
SAVEPOINT-based transaction can't exhibit real cross-connection
locking/conflict behavior) and NOT a mock-only test.

Audit finding under test: MonthlyStatisticsRepository.upsert() and the
AnalyticsService.recompute_daily() per-bucket write both used to be
get()-then-write / delete()-then-create() (check-then-act). Two
concurrent writers targeting the SAME logical unique key
(uq_monthly_statistics_user_subject_month_year /
uq_daily_statistics_user_subject_date — both already existed since
migration 0001) could both take the "doesn't exist yet" branch and race
their plain INSERTs, the loser raising an unhandled IntegrityError
instead of succeeding. Fixed by converting both to a single atomic
INSERT ... ON CONFLICT DO UPDATE (the same established pattern as
AnswerRepository.upsert(), Sprint 58) — no new migration, no schema
change, same existing constraints, same returned-row shape/API.
"""
import threading
import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.database import engine
from app.modules.analytics.models import DailyStatistics, MonthlyStatistics
from app.modules.analytics.repository import DailyStatisticsRepository, MonthlyStatisticsRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.users.models import User, UserStatus


def _make_user_and_subject(session):
    role = session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="Stat", last_name="RT", email=f"statrt-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    session.add(user)
    subject = Subject(name=f"StatSubj-{uuid.uuid4()}")
    session.add(subject)
    session.flush()
    session.commit()
    return user.id, subject.id


class _WriteSyncedMonthlyRepository(MonthlyStatisticsRepository):
    """Test-only synchronization aid — never used by application code.
    Waits on a shared 2-party threading.Barrier immediately before
    issuing upsert()'s actual write statement, forcing both threads'
    writes to hit Postgres at essentially the same instant regardless of
    host scheduling — same technique Sprint 58's own concurrency test
    established for AnswerRepository.upsert()."""

    barrier: threading.Barrier | None = None

    def upsert(self, user_id, subject_id, month, year, tests_taken, avg_score):
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        return super().upsert(user_id, subject_id, month, year, tests_taken, avg_score)


class _WriteSyncedDailyRepository(DailyStatisticsRepository):
    """Same synchronization aid as _WriteSyncedMonthlyRepository above,
    for DailyStatisticsRepository.upsert()."""

    barrier: threading.Barrier | None = None

    def upsert(self, user_id, subject_id, stat_date, tests_taken, correct_answers, wrong_answers):
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        return super().upsert(user_id, subject_id, stat_date, tests_taken, correct_answers, wrong_answers)


# --- TEST A: concurrent MonthlyStatisticsRepository.upsert() for the same key ---

def test_concurrent_monthly_upsert_same_key_produces_exactly_one_row():
    """Before the fix: one of the two threads' create() branch would
    raise an unhandled IntegrityError against
    uq_monthly_statistics_user_subject_month_year. After the fix: both
    threads succeed (the loser's INSERT becomes an UPDATE via ON
    CONFLICT), and exactly one MonthlyStatistics row exists for
    (user_id, subject_id, month, year)."""
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id, subject_id = _make_user_and_subject(setup)
    finally:
        setup.close()

    outcomes = {}
    write_barrier = threading.Barrier(2)

    def worker(name: str, tests_taken: int):
        s = Session()
        repo = _WriteSyncedMonthlyRepository(s)
        repo.barrier = write_barrier
        try:
            repo.upsert(user_id, subject_id, 3, 2026, tests_taken, avg_score=50.0)
            s.commit()
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A", 4))
    t2 = threading.Thread(target=worker, args=("B", 7))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    results = [outcomes.get("A"), outcomes.get("B")]

    try:
        successes = [r for r in results if r is not None and r[0] == "OK"]
        assert len(successes) == 2, f"expected both concurrent upserts to succeed gracefully, got {results}"

        verify = Session()
        try:
            rows = verify.execute(
                select(MonthlyStatistics).where(
                    MonthlyStatistics.user_id == user_id, MonthlyStatistics.subject_id == subject_id,
                    MonthlyStatistics.month == 3, MonthlyStatistics.year == 2026,
                )
            ).scalars().all()
            # Exactly one row — never duplicated, never crashed. Final
            # tests_taken is whichever writer's ON CONFLICT DO UPDATE
            # landed last (4 or 7) — both are valid, race-safe outcomes;
            # what matters is there is exactly one consistent row.
            assert len(rows) == 1, f"expected exactly 1 MonthlyStatistics row, got {len(rows)}"
            assert rows[0].tests_taken in (4, 7)
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(MonthlyStatistics).filter(MonthlyStatistics.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# --- TEST B: concurrent DailyStatisticsRepository.upsert() for the same key ---

def test_concurrent_daily_upsert_same_key_produces_exactly_one_row():
    """Same proof as Test A, for DailyStatisticsRepository.upsert() —
    the atomic write AnalyticsService.recompute_daily() now uses instead
    of create() after delete_for_range()."""
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id, subject_id = _make_user_and_subject(setup)
    finally:
        setup.close()

    stat_date = date(2026, 3, 15)
    outcomes = {}
    write_barrier = threading.Barrier(2)

    def worker(name: str, tests_taken: int, correct: int, wrong: int):
        s = Session()
        repo = _WriteSyncedDailyRepository(s)
        repo.barrier = write_barrier
        try:
            repo.upsert(user_id, subject_id, stat_date, tests_taken, correct, wrong)
            s.commit()
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A", 2, 5, 1))
    t2 = threading.Thread(target=worker, args=("B", 3, 6, 2))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    results = [outcomes.get("A"), outcomes.get("B")]

    try:
        successes = [r for r in results if r is not None and r[0] == "OK"]
        assert len(successes) == 2, f"expected both concurrent upserts to succeed gracefully, got {results}"

        verify = Session()
        try:
            rows = verify.execute(
                select(DailyStatistics).where(
                    DailyStatistics.user_id == user_id, DailyStatistics.subject_id == subject_id,
                    DailyStatistics.stat_date == stat_date,
                )
            ).scalars().all()
            assert len(rows) == 1, f"expected exactly 1 DailyStatistics row, got {len(rows)}"
            assert rows[0].tests_taken in (2, 3)
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(DailyStatistics).filter(DailyStatistics.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# --- TEST C: sequential upsert-then-upsert regression (pg_session is fine here — no true concurrency needed) ---

def test_sequential_monthly_upsert_updates_same_row_not_a_new_one(pg_session):
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="SeqM", last_name="RT", email=f"seqm-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    subject = Subject(name=f"SeqSubj-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    pg_session.commit()

    repo = MonthlyStatisticsRepository(pg_session)
    first = repo.upsert(user.id, subject.id, 5, 2026, tests_taken=3, avg_score=60.0)
    pg_session.commit()

    second = repo.upsert(user.id, subject.id, 5, 2026, tests_taken=8, avg_score=75.0)
    pg_session.commit()

    assert second.id == first.id  # same row, not a new one
    rows = pg_session.execute(
        select(MonthlyStatistics).where(MonthlyStatistics.user_id == user.id, MonthlyStatistics.subject_id == subject.id, MonthlyStatistics.month == 5, MonthlyStatistics.year == 2026)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].tests_taken == 8
    assert float(rows[0].avg_score) == 75.0


def test_sequential_daily_upsert_updates_same_row_not_a_new_one(pg_session):
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="SeqD", last_name="RT", email=f"seqd-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    subject = Subject(name=f"SeqSubj2-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    pg_session.commit()

    stat_date = date(2026, 4, 1)
    repo = DailyStatisticsRepository(pg_session)
    first = repo.upsert(user.id, subject.id, stat_date, tests_taken=1, correct_answers=2, wrong_answers=0)
    pg_session.commit()

    second = repo.upsert(user.id, subject.id, stat_date, tests_taken=2, correct_answers=3, wrong_answers=1)
    pg_session.commit()

    assert second.id == first.id  # same row, not a new one
    rows = pg_session.execute(
        select(DailyStatistics).where(DailyStatistics.user_id == user.id, DailyStatistics.subject_id == subject.id, DailyStatistics.stat_date == stat_date)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].tests_taken == 2
    assert rows[0].correct_answers == 3
    assert rows[0].wrong_answers == 1


# --- TEST D: recompute_daily() end-to-end still returns the same API/shape via the new atomic write ---

def test_recompute_daily_rerun_is_idempotent_via_atomic_upsert(pg_session):
    """Re-running AnalyticsService.recompute_daily() for the same window
    twice must still converge to the same single row per bucket (no
    double counting) now that the per-bucket write is upsert() instead
    of create() — preserving recompute_daily()'s pre-existing
    delete-and-rebuild idempotency guarantee end-to-end."""
    from app.modules.analytics.service import AnalyticsService
    from app.modules.attempts.models import Answer, TestAttempt, AttemptStatus
    from app.modules.attempts.repository import AnswerRepository
    from app.modules.questions.models import Question, QuestionOption
    from app.modules.results.models import Result
    from app.modules.results.repository import ResultRepository
    from app.modules.tests.models import Test
    from app.modules.tests.repository import TestRepository
    from datetime import datetime, timezone

    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="Re", last_name="Comp", email=f"recomp-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    subject = Subject(name=f"RecompSubj-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Recompute Test", duration=30, question_count=1, status="published")
    pg_session.add(test)
    pg_session.flush()
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.flush()
    option = QuestionOption(question_id=question.id, option_text="A", is_correct=True)
    pg_session.add(option)
    pg_session.flush()

    now = datetime.now(timezone.utc)
    attempt = TestAttempt(test_id=test.id, user_id=user.id, status=AttemptStatus.SUBMITTED, start_time=now, question_order=[question.id])
    pg_session.add(attempt)
    pg_session.flush()
    answer = Answer(attempt_id=attempt.id, question_id=question.id, selected_option=option.id, is_correct=True)
    pg_session.add(answer)
    pg_session.flush()

    result = Result(attempt_id=attempt.id, test_id=test.id, user_id=user.id, score=1, percentage=100.0)
    result.created_at = now
    pg_session.add(result)
    pg_session.commit()

    service = AnalyticsService(
        DailyStatisticsRepository(pg_session), MonthlyStatisticsRepository(pg_session),
        ResultRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
    )

    count1 = service.recompute_daily(now.date(), now.date())
    assert count1 == 1
    rows_after_first = pg_session.execute(
        select(DailyStatistics).where(DailyStatistics.user_id == user.id, DailyStatistics.stat_date == now.date())
    ).scalars().all()
    assert len(rows_after_first) == 1
    assert rows_after_first[0].tests_taken == 1

    # Re-run: must still converge to exactly one row, not a duplicate.
    count2 = service.recompute_daily(now.date(), now.date())
    assert count2 == 1
    rows_after_second = pg_session.execute(
        select(DailyStatistics).where(DailyStatistics.user_id == user.id, DailyStatistics.stat_date == now.date())
    ).scalars().all()
    assert len(rows_after_second) == 1
    assert rows_after_second[0].tests_taken == 1
