"""
Sprint 69 — Statistics Correctness + Concurrency Fix (F1 + F2), against
real PostgreSQL. Reuses this codebase's own established real-concurrency
pattern (test_sprint58_answer_race_condition.py,
test_sprint64_statistics_atomic_upsert.py, test_result_section_creation.py
::test_concurrent_result_creation_is_race_safe) — a separate sessionmaker
bound to the real engine plus real threading.Thread workers and a
write-synchronizing threading.Barrier, NOT the pg_session fixture (its
SAVEPOINT-based transaction can't exhibit real cross-connection
locking/conflict behavior) for the genuinely-concurrent tests; pg_session
IS used for the purely-sequential tests, exactly as the existing Sprint 64
file does.

F1 — audit finding: `results.Statistics` (StatisticsRepository /
ResultService._update_statistics()) had NO unique constraint on
(user_id, subject_id) at all, and used check-then-act (get-then-create-
or-update). Two concurrent first-time writes for the same key could both
insert, producing duplicate rows that then crash every later
get_by_user_and_subject() call with MultipleResultsFound. Fixed by
migration 0016 (uq_statistics_user_id_subject_id, UNIQUE NULLS NOT
DISTINCT) + StatisticsRepository.upsert_after_result() (a single atomic
INSERT ... ON CONFLICT DO UPDATE, same established pattern as
AnswerRepository.upsert()/the analytics module's own upsert() methods).

F2 — audit finding: monthly_statistics/daily_statistics already had a
plain UNIQUE(user_id, subject_id, ...) constraint and an atomic
ON CONFLICT DO UPDATE upsert (Sprint 64), but a plain PostgreSQL UNIQUE
constraint treats NULL <> NULL, so two rows sharing subject_id IS NULL
for the same (user_id, month, year)/(user_id, stat_date) were never
recognized as conflicting — reproduced directly during the Sprint 69
audit by running the exact existing ON CONFLICT statement twice. Fixed
by migration 0016 converting both constraints to UNIQUE NULLS NOT
DISTINCT — MonthlyStatisticsRepository.upsert()/
DailyStatisticsRepository.upsert() themselves are UNCHANGED (same
constraint names, same statements); only the constraints' NULL
semantics changed.
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
from app.modules.results.models import Result, Statistics
from app.modules.results.repository import StatisticsRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.users.models import User, UserStatus


def _make_user(session, prefix: str) -> uuid.UUID:
    role = session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name=prefix, last_name="RT", email=f"{prefix.lower()}-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    session.add(user)
    session.flush()
    session.commit()
    return user.id


def _make_user_and_subject(session, prefix: str):
    uid = _make_user(session, prefix)
    subject = Subject(name=f"{prefix}Subj-{uuid.uuid4()}")
    session.add(subject)
    session.flush()
    session.commit()
    return uid, subject.id


class _WriteSyncedStatisticsRepository(StatisticsRepository):
    """Test-only synchronization aid — never used by application code.
    Waits on a shared threading.Barrier immediately before issuing
    upsert_after_result()'s actual write statement, forcing concurrent
    threads' writes to hit Postgres at essentially the same instant —
    same technique test_sprint64_statistics_atomic_upsert.py and
    test_sprint58_answer_race_condition.py already established."""

    barrier: threading.Barrier | None = None

    def upsert_after_result(self, user_id, subject_id, correct, wrong, percentage):
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        return super().upsert_after_result(user_id, subject_id, correct, wrong, percentage)


class _WriteSyncedMonthlyRepository(MonthlyStatisticsRepository):
    barrier: threading.Barrier | None = None

    def upsert(self, user_id, subject_id, month, year, tests_taken, avg_score):
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        return super().upsert(user_id, subject_id, month, year, tests_taken, avg_score)


class _WriteSyncedDailyRepository(DailyStatisticsRepository):
    barrier: threading.Barrier | None = None

    def upsert(self, user_id, subject_id, stat_date, tests_taken, correct_answers, wrong_answers):
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        return super().upsert(user_id, subject_id, stat_date, tests_taken, correct_answers, wrong_answers)


# =====================================================================
# F1.1 — two concurrent FIRST-TIME statistics writes for the same
# (user_id, subject_id): exactly one row, no exception, correct
# aggregate values.
# =====================================================================

def test_f1_1_concurrent_first_time_writes_produce_exactly_one_row():
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id, subject_id = _make_user_and_subject(setup, "F11")
    finally:
        setup.close()

    outcomes = {}
    write_barrier = threading.Barrier(2)

    def worker(name: str, correct: int, wrong: int, percentage: float):
        s = Session()
        repo = _WriteSyncedStatisticsRepository(s)
        repo.barrier = write_barrier
        try:
            repo.upsert_after_result(user_id, subject_id, correct, wrong, percentage)
            s.commit()
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A", 5, 1, 80.0))
    t2 = threading.Thread(target=worker, args=("B", 3, 2, 60.0))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    try:
        results = [outcomes.get("A"), outcomes.get("B")]
        successes = [r for r in results if r is not None and r[0] == "OK"]
        assert len(successes) == 2, f"expected both concurrent first-time writes to succeed, got {results}"

        verify = Session()
        try:
            rows = verify.execute(
                select(Statistics).where(Statistics.user_id == user_id, Statistics.subject_id == subject_id)
            ).scalars().all()
            assert len(rows) == 1, f"expected exactly 1 Statistics row, got {len(rows)}"
            row = rows[0]
            # Both writers' contributions must be reflected — never a
            # lost update, never a duplicate row: tests_taken=2,
            # correct/wrong summed across both, avg_score the
            # tests_taken-weighted mean of both percentages (80.0 and
            # 60.0, weight 1 each) = 70.0, regardless of arrival order.
            assert row.tests_taken == 2, row.tests_taken
            assert row.correct_answers == 8, row.correct_answers
            assert row.wrong_answers == 3, row.wrong_answers
            assert float(row.avg_score) == 70.0, row.avg_score
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(Statistics).filter(Statistics.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# =====================================================================
# F1.2 — two concurrent UPDATES to an already-existing statistics row:
# exactly one row, both updates reflected, no lost update.
# =====================================================================

def test_f1_2_concurrent_updates_to_existing_row_lose_neither_update():
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id, subject_id = _make_user_and_subject(setup, "F12")
        # Seed an existing row (first test already taken) exactly as
        # ResultService._update_statistics() would leave it.
        StatisticsRepository(setup).upsert_after_result(user_id, subject_id, correct=4, wrong=1, percentage=80.0)
        setup.commit()
    finally:
        setup.close()

    outcomes = {}
    write_barrier = threading.Barrier(2)

    def worker(name: str, correct: int, wrong: int, percentage: float):
        s = Session()
        repo = _WriteSyncedStatisticsRepository(s)
        repo.barrier = write_barrier
        try:
            repo.upsert_after_result(user_id, subject_id, correct, wrong, percentage)
            s.commit()
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A", 2, 0, 100.0))
    t2 = threading.Thread(target=worker, args=("B", 1, 1, 50.0))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    try:
        results = [outcomes.get("A"), outcomes.get("B")]
        successes = [r for r in results if r is not None and r[0] == "OK"]
        assert len(successes) == 2, f"expected both concurrent updates to succeed, got {results}"

        verify = Session()
        try:
            rows = verify.execute(
                select(Statistics).where(Statistics.user_id == user_id, Statistics.subject_id == subject_id)
            ).scalars().all()
            assert len(rows) == 1, f"expected exactly 1 Statistics row after concurrent updates, got {len(rows)}"
            row = rows[0]
            # Baseline: tests_taken=1, correct=4, wrong=1, avg=80.0.
            # Both concurrent writers' contributions must land: final
            # tests_taken = 1 + 1 + 1 = 3 — NOT 2 (which would mean one
            # update was lost). correct/wrong summed across all three
            # contributions: 4+2+1=7, 1+0+1=2. avg_score is the
            # tests_taken-weighted mean of all three percentages
            # (80, 100, 50 each weight 1) = 230/3 = 76.67, regardless
            # of which writer's ON CONFLICT DO UPDATE landed last.
            assert row.tests_taken == 3, f"lost an update — expected tests_taken=3, got {row.tests_taken}"
            assert row.correct_answers == 7, row.correct_answers
            assert row.wrong_answers == 2, row.wrong_answers
            assert float(row.avg_score) == 76.67, row.avg_score
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(Statistics).filter(Statistics.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# =====================================================================
# F1.3 — repeated (sequential) statistics writes never produce
# duplicates, and the running-average math matches the original
# Python formula exactly.
# =====================================================================

def test_f1_3_repeated_sequential_writes_do_not_duplicate(pg_session):
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="F13", last_name="RT", email=f"f13-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    subject = Subject(name=f"F13Subj-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    pg_session.commit()

    repo = StatisticsRepository(pg_session)
    first = repo.upsert_after_result(user.id, subject.id, correct=3, wrong=1, percentage=75.0)
    pg_session.commit()
    second = repo.upsert_after_result(user.id, subject.id, correct=4, wrong=0, percentage=100.0)
    pg_session.commit()
    third = repo.upsert_after_result(user.id, subject.id, correct=2, wrong=2, percentage=50.0)
    pg_session.commit()

    assert first.id == second.id == third.id  # same row throughout, never duplicated

    rows = pg_session.execute(
        select(Statistics).where(Statistics.user_id == user.id, Statistics.subject_id == subject.id)
    ).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.tests_taken == 3
    assert row.correct_answers == 9
    assert row.wrong_answers == 3
    # Original Python formula, applied sequentially:
    # avg1 = 75.0 ; avg2 = ((75.0*1)+100.0)/2 = 87.5 ; avg3 = ((87.5*2)+50.0)/3 = 75.0
    assert float(row.avg_score) == 75.0, row.avg_score


# =====================================================================
# F1.4 — end-to-end through ResultService.create_result() (the real
# production call path per the audit): repeated result creation for
# the same user/subject across different attempts never produces a
# duplicate Statistics row (this exact, previously-crash-prone
# scenario is what the audit found reachable via every POST /results
# call).
# =====================================================================

def test_f1_4_repeated_result_creation_never_duplicates_statistics(pg_session):
    from datetime import datetime, timezone

    from app.modules.attempts.models import Answer, AttemptStatus, TestAttempt
    from app.modules.attempts.repository import AnswerRepository, AttemptRepository
    from app.modules.questions.models import Question, QuestionOption
    from app.modules.questions.repository import OptionRepository, QuestionRepository
    from app.modules.results.repository import ResultRepository, ResultSectionRepository
    from app.modules.results.service import ResultService
    from app.modules.tests.models import Test
    from app.modules.tests.repository import ExamSectionRepository, TestRepository

    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="F14", last_name="RT", email=f"f14-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    subject = Subject(name=f"F14Subj-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="F14 Test", duration=30, question_count=1, status="published")
    pg_session.add(test)
    pg_session.flush()
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1)
    pg_session.add(question)
    pg_session.flush()
    option = QuestionOption(question_id=question.id, option_text="A", is_correct=True)
    pg_session.add(option)
    pg_session.flush()

    service = ResultService(
        ResultRepository(pg_session), StatisticsRepository(pg_session), AttemptRepository(pg_session),
        AnswerRepository(pg_session), TestRepository(pg_session), QuestionRepository(pg_session),
        ExamSectionRepository(pg_session), ResultSectionRepository(pg_session),
    )

    now = datetime.now(timezone.utc)
    for i in range(3):
        attempt = TestAttempt(test_id=test.id, user_id=user.id, status=AttemptStatus.SUBMITTED, start_time=now, question_order=[question.id])
        pg_session.add(attempt)
        pg_session.flush()
        answer = Answer(attempt_id=attempt.id, question_id=question.id, selected_option=option.id, is_correct=True)
        pg_session.add(answer)
        pg_session.flush()
        result = Result(attempt_id=attempt.id, test_id=test.id, user_id=user.id, score=1, percentage=100.0)
        pg_session.add(result)
        pg_session.commit()
        service._update_statistics(user.id, subject.id, attempt.id, 100.0)
        pg_session.commit()

    rows = pg_session.execute(
        select(Statistics).where(Statistics.user_id == user.id, Statistics.subject_id == subject.id)
    ).scalars().all()
    assert len(rows) == 1, f"expected exactly 1 Statistics row after 3 sequential result creations, got {len(rows)}"
    assert rows[0].tests_taken == 3


# =====================================================================
# F2.1 — two SEQUENTIAL monthly upserts, same user, same NULL
# subject_id, same month/year: exactly one row, second updates it.
# =====================================================================

def test_f2_1_sequential_monthly_upsert_null_subject_updates_same_row(pg_session):
    user_id = _make_user(pg_session, "F21")

    repo = MonthlyStatisticsRepository(pg_session)
    first = repo.upsert(user_id, None, 9, 2026, tests_taken=4, avg_score=50.0)
    pg_session.commit()
    second = repo.upsert(user_id, None, 9, 2026, tests_taken=9, avg_score=65.0)
    pg_session.commit()

    assert second.id == first.id  # same row — NOT a duplicate
    rows = pg_session.execute(
        select(MonthlyStatistics).where(MonthlyStatistics.user_id == user_id, MonthlyStatistics.subject_id.is_(None), MonthlyStatistics.month == 9, MonthlyStatistics.year == 2026)
    ).scalars().all()
    assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)} — NULL subject_id ON CONFLICT did not fire"
    assert rows[0].tests_taken == 9
    assert float(rows[0].avg_score) == 65.0


# =====================================================================
# F2.2 — same as F2.1, for daily_statistics.
# =====================================================================

def test_f2_2_sequential_daily_upsert_null_subject_updates_same_row(pg_session):
    user_id = _make_user(pg_session, "F22")
    stat_date = date(2026, 9, 20)

    repo = DailyStatisticsRepository(pg_session)
    first = repo.upsert(user_id, None, stat_date, tests_taken=1, correct_answers=2, wrong_answers=0)
    pg_session.commit()
    second = repo.upsert(user_id, None, stat_date, tests_taken=3, correct_answers=5, wrong_answers=1)
    pg_session.commit()

    assert second.id == first.id
    rows = pg_session.execute(
        select(DailyStatistics).where(DailyStatistics.user_id == user_id, DailyStatistics.subject_id.is_(None), DailyStatistics.stat_date == stat_date)
    ).scalars().all()
    assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)} — NULL subject_id ON CONFLICT did not fire"
    assert rows[0].tests_taken == 3
    assert rows[0].correct_answers == 5
    assert rows[0].wrong_answers == 1


# =====================================================================
# F2.3 — CONCURRENT monthly upserts, same NULL subject_id: exactly one
# row (this is the exact scenario the Sprint 69 audit reproduced as
# broken against the pre-migration constraint).
# =====================================================================

def test_f2_3_concurrent_monthly_upsert_null_subject_produces_exactly_one_row():
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id = _make_user(setup, "F23")
    finally:
        setup.close()

    outcomes = {}
    write_barrier = threading.Barrier(2)

    def worker(name: str, tests_taken: int):
        s = Session()
        repo = _WriteSyncedMonthlyRepository(s)
        repo.barrier = write_barrier
        try:
            repo.upsert(user_id, None, 8, 2026, tests_taken, avg_score=40.0)
            s.commit()
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A", 3))
    t2 = threading.Thread(target=worker, args=("B", 5))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    try:
        results = [outcomes.get("A"), outcomes.get("B")]
        successes = [r for r in results if r is not None and r[0] == "OK"]
        assert len(successes) == 2, f"expected both concurrent NULL-subject upserts to succeed, got {results}"

        verify = Session()
        try:
            rows = verify.execute(
                select(MonthlyStatistics).where(MonthlyStatistics.user_id == user_id, MonthlyStatistics.subject_id.is_(None), MonthlyStatistics.month == 8, MonthlyStatistics.year == 2026)
            ).scalars().all()
            assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)} — this is exactly the audit-reproduced NULL-subject_id defect if it recurs"
            assert rows[0].tests_taken in (3, 5)
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(MonthlyStatistics).filter(MonthlyStatistics.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# =====================================================================
# F2.4 — CONCURRENT daily upserts, same NULL subject_id: exactly one
# row.
# =====================================================================

def test_f2_4_concurrent_daily_upsert_null_subject_produces_exactly_one_row():
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id = _make_user(setup, "F24")
    finally:
        setup.close()

    stat_date = date(2026, 9, 21)
    outcomes = {}
    write_barrier = threading.Barrier(2)

    def worker(name: str, tests_taken: int, correct: int, wrong: int):
        s = Session()
        repo = _WriteSyncedDailyRepository(s)
        repo.barrier = write_barrier
        try:
            repo.upsert(user_id, None, stat_date, tests_taken, correct, wrong)
            s.commit()
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A", 1, 1, 0))
    t2 = threading.Thread(target=worker, args=("B", 2, 1, 1))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    try:
        results = [outcomes.get("A"), outcomes.get("B")]
        successes = [r for r in results if r is not None and r[0] == "OK"]
        assert len(successes) == 2, f"expected both concurrent NULL-subject upserts to succeed, got {results}"

        verify = Session()
        try:
            rows = verify.execute(
                select(DailyStatistics).where(DailyStatistics.user_id == user_id, DailyStatistics.subject_id.is_(None), DailyStatistics.stat_date == stat_date)
            ).scalars().all()
            assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)} — this is exactly the audit-reproduced NULL-subject_id defect if it recurs"
            assert rows[0].tests_taken in (1, 2)
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(DailyStatistics).filter(DailyStatistics.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# =====================================================================
# F2.5 — non-NULL subject_id behavior remains correct (regression
# guard: the NULLS NOT DISTINCT constraint change must not affect the
# normal, real-subject case at all).
# =====================================================================

def test_f2_5_non_null_subject_id_behavior_is_unaffected(pg_session):
    user_id = _make_user(pg_session, "F25")
    subject = Subject(name=f"F25Subj-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    pg_session.commit()

    monthly_repo = MonthlyStatisticsRepository(pg_session)
    m1 = monthly_repo.upsert(user_id, subject.id, 7, 2026, tests_taken=2, avg_score=55.0)
    pg_session.commit()
    m2 = monthly_repo.upsert(user_id, subject.id, 7, 2026, tests_taken=5, avg_score=70.0)
    pg_session.commit()
    assert m1.id == m2.id
    monthly_rows = pg_session.execute(
        select(MonthlyStatistics).where(MonthlyStatistics.user_id == user_id, MonthlyStatistics.subject_id == subject.id, MonthlyStatistics.month == 7, MonthlyStatistics.year == 2026)
    ).scalars().all()
    assert len(monthly_rows) == 1
    assert monthly_rows[0].tests_taken == 5

    # A DIFFERENT subject_id (still non-NULL) must NOT collide with the
    # row above — proves NULLS NOT DISTINCT only merges NULLs with
    # NULLs, never distinct real UUIDs with each other.
    other_subject = Subject(name=f"F25OtherSubj-{uuid.uuid4()}")
    pg_session.add(other_subject)
    pg_session.flush()
    pg_session.commit()
    monthly_repo.upsert(user_id, other_subject.id, 7, 2026, tests_taken=1, avg_score=10.0)
    pg_session.commit()
    all_rows = pg_session.execute(
        select(MonthlyStatistics).where(MonthlyStatistics.user_id == user_id, MonthlyStatistics.month == 7, MonthlyStatistics.year == 2026)
    ).scalars().all()
    assert len(all_rows) == 2, "distinct non-NULL subject_id rows must remain separate"

    daily_repo = DailyStatisticsRepository(pg_session)
    stat_date = date(2026, 7, 15)
    d1 = daily_repo.upsert(user_id, subject.id, stat_date, tests_taken=1, correct_answers=1, wrong_answers=0)
    pg_session.commit()
    d2 = daily_repo.upsert(user_id, subject.id, stat_date, tests_taken=2, correct_answers=2, wrong_answers=1)
    pg_session.commit()
    assert d1.id == d2.id
    daily_rows = pg_session.execute(
        select(DailyStatistics).where(DailyStatistics.user_id == user_id, DailyStatistics.subject_id == subject.id, DailyStatistics.stat_date == stat_date)
    ).scalars().all()
    assert len(daily_rows) == 1
    assert daily_rows[0].tests_taken == 2

    stats_repo = StatisticsRepository(pg_session)
    s1 = stats_repo.upsert_after_result(user_id, subject.id, correct=3, wrong=1, percentage=75.0)
    pg_session.commit()
    s2 = stats_repo.upsert_after_result(user_id, subject.id, correct=2, wrong=0, percentage=100.0)
    pg_session.commit()
    assert s1.id == s2.id
    stats_rows = pg_session.execute(
        select(Statistics).where(Statistics.user_id == user_id, Statistics.subject_id == subject.id)
    ).scalars().all()
    assert len(stats_rows) == 1
    assert stats_rows[0].tests_taken == 2


# =====================================================================
# F2.6 — existing Sprint 64 atomic-upsert-under-concurrency behavior
# (non-NULL subject_id) remains correct after the constraint change —
# a direct regression check alongside test_sprint64_statistics_atomic_
# upsert.py's own (unmodified) tests.
# =====================================================================

def test_f2_6_sprint64_concurrent_upsert_behavior_still_correct_after_constraint_change():
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id, subject_id = _make_user_and_subject(setup, "F26")
    finally:
        setup.close()

    outcomes = {}
    write_barrier = threading.Barrier(2)

    def worker(name: str, tests_taken: int):
        s = Session()
        repo = _WriteSyncedMonthlyRepository(s)
        repo.barrier = write_barrier
        try:
            repo.upsert(user_id, subject_id, 6, 2026, tests_taken, avg_score=45.0)
            s.commit()
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A", 2))
    t2 = threading.Thread(target=worker, args=("B", 9))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    try:
        results = [outcomes.get("A"), outcomes.get("B")]
        successes = [r for r in results if r is not None and r[0] == "OK"]
        assert len(successes) == 2, f"expected both concurrent non-NULL-subject upserts to succeed, got {results}"

        verify = Session()
        try:
            rows = verify.execute(
                select(MonthlyStatistics).where(MonthlyStatistics.user_id == user_id, MonthlyStatistics.subject_id == subject_id, MonthlyStatistics.month == 6, MonthlyStatistics.year == 2026)
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].tests_taken in (2, 9)
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
