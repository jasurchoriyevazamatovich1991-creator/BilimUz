"""
Sprint 72 — RANK-2: Ranking concurrency fix, against real PostgreSQL.
Reuses this codebase's own established real-concurrency pattern (see
test_sprint69_statistics_null_subject_and_concurrency.py, which this
file mirrors closely) — a separate sessionmaker bound to the real
engine plus real threading.Thread workers and a write-synchronizing
threading.Barrier for the genuinely-concurrent tests; pg_session is
used for the purely-sequential/non-collision tests.

RANK-2 — audit finding: `results.Ranking` (RankingRepository.upsert())
had NO unique constraint on (user_id, subject_id, period) at all, and
used check-then-act (get()-then-create-or-update) — the same shape as
the F1 defect migration 0016 already fixed for `statistics`. Fixed by
migration 0017 (uq_ranking_user_subject_period, UNIQUE NULLS NOT
DISTINCT) + RankingRepository.upsert() becoming a single atomic
INSERT ... ON CONFLICT DO UPDATE.

Unlike Statistics, Ranking.score/rank are not accumulated — each
upsert() call supplies the full already-computed value, so under
concurrent writes for the same key there is no "lost update" to detect
(overwrite semantics, last commit wins); what matters is that exactly
one row survives and neither writer raises an unhandled exception.
"""
import threading
import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.database import engine
from app.modules.results.models import Ranking
from app.modules.results.repository import RankingRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.users.models import User, UserStatus


def _make_user(session, prefix: str) -> uuid.UUID:
    role = session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name=prefix, last_name="RK", email=f"{prefix.lower()}-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
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


class _WriteSyncedRankingRepository(RankingRepository):
    """Test-only synchronization aid — never used by application code.
    Waits on a shared threading.Barrier immediately before issuing
    upsert()'s actual write statement, forcing concurrent threads'
    writes to hit Postgres at essentially the same instant — same
    technique test_sprint69_statistics_null_subject_and_concurrency.py
    already established."""

    barrier: threading.Barrier | None = None

    def upsert(self, user_id, subject_id, period, score, rank):
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        return super().upsert(user_id, subject_id, period, score, rank)


# =====================================================================
# RANK2.1 — two concurrent FIRST-TIME ranking writes for the same
# (user_id, subject_id, period): exactly one row, no exception.
# =====================================================================

def test_rank2_1_concurrent_first_time_writes_produce_exactly_one_row():
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id, subject_id = _make_user_and_subject(setup, "RK11")
    finally:
        setup.close()

    outcomes = {}
    write_barrier = threading.Barrier(2)

    def worker(name: str, score: float, rank: int):
        s = Session()
        repo = _WriteSyncedRankingRepository(s)
        repo.barrier = write_barrier
        try:
            repo.upsert(user_id, subject_id, "all_time", score, rank)
            s.commit()
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A", 90.0, 1))
    t2 = threading.Thread(target=worker, args=("B", 85.0, 2))
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
                select(Ranking).where(Ranking.user_id == user_id, Ranking.subject_id == subject_id, Ranking.period == "all_time")
            ).scalars().all()
            assert len(rows) == 1, f"expected exactly 1 Ranking row, got {len(rows)}"
            # Overwrite semantics — whichever writer's statement
            # committed last wins outright; either outcome is correct
            # as long as it's exactly one of the two submitted values.
            assert (float(rows[0].score), rows[0].rank) in [(90.0, 1), (85.0, 2)]
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(Ranking).filter(Ranking.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# =====================================================================
# RANK2.2 — two concurrent UPDATES to an already-existing ranking row:
# exactly one row survives, no exception (overwrite semantics — no
# "lost update" to detect since score/rank are not accumulated).
# =====================================================================

def test_rank2_2_concurrent_updates_to_existing_row_produce_exactly_one_row():
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id, subject_id = _make_user_and_subject(setup, "RK12")
        RankingRepository(setup).upsert(user_id, subject_id, "all_time", 50.0, 10)
        setup.commit()
    finally:
        setup.close()

    outcomes = {}
    write_barrier = threading.Barrier(2)

    def worker(name: str, score: float, rank: int):
        s = Session()
        repo = _WriteSyncedRankingRepository(s)
        repo.barrier = write_barrier
        try:
            repo.upsert(user_id, subject_id, "all_time", score, rank)
            s.commit()
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A", 95.0, 1))
    t2 = threading.Thread(target=worker, args=("B", 70.0, 3))
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
                select(Ranking).where(Ranking.user_id == user_id, Ranking.subject_id == subject_id, Ranking.period == "all_time")
            ).scalars().all()
            assert len(rows) == 1, f"expected exactly 1 Ranking row after concurrent updates, got {len(rows)}"
            assert (float(rows[0].score), rows[0].rank) in [(95.0, 1), (70.0, 3)]
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(Ranking).filter(Ranking.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.query(Subject).filter(Subject.id == subject_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# =====================================================================
# RANK2.3 — CONCURRENT upserts, same NULL subject_id (the "overall,
# not subject-scoped" ranking bucket): exactly one row — this is the
# exact NULLS NOT DISTINCT scenario migration 0016 already proved for
# `statistics`/`monthly_statistics`/`daily_statistics`, now extended
# to `ranking`.
# =====================================================================

def test_rank2_3_concurrent_upsert_null_subject_produces_exactly_one_row():
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id = _make_user(setup, "RK13")
    finally:
        setup.close()

    outcomes = {}
    write_barrier = threading.Barrier(2)

    def worker(name: str, score: float, rank: int):
        s = Session()
        repo = _WriteSyncedRankingRepository(s)
        repo.barrier = write_barrier
        try:
            repo.upsert(user_id, None, "monthly", score, rank)
            s.commit()
            outcomes[name] = ("OK", None)
        except Exception as e:
            s.rollback()
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A", 40.0, 5))
    t2 = threading.Thread(target=worker, args=("B", 60.0, 2))
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
                select(Ranking).where(Ranking.user_id == user_id, Ranking.subject_id.is_(None), Ranking.period == "monthly")
            ).scalars().all()
            assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)} — NULL subject_id ON CONFLICT did not fire"
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(Ranking).filter(Ranking.user_id == user_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


# =====================================================================
# RANK2.4 — repeated (sequential) upserts for the same key never
# produce duplicates and always update the same row in place.
# =====================================================================

def test_rank2_4_repeated_sequential_upserts_do_not_duplicate(pg_session):
    user_id, subject_id = _make_user_and_subject(pg_session, "RK14")

    repo = RankingRepository(pg_session)
    first = repo.upsert(user_id, subject_id, "weekly", 10.0, 9)
    pg_session.commit()
    second = repo.upsert(user_id, subject_id, "weekly", 20.0, 4)
    pg_session.commit()
    third = repo.upsert(user_id, subject_id, "weekly", 30.0, 1)
    pg_session.commit()

    assert first.id == second.id == third.id  # same row throughout, never duplicated

    rows = pg_session.execute(
        select(Ranking).where(Ranking.user_id == user_id, Ranking.subject_id == subject_id, Ranking.period == "weekly")
    ).scalars().all()
    assert len(rows) == 1
    assert float(rows[0].score) == 30.0
    assert rows[0].rank == 1


# =====================================================================
# RANK2.5 — non-collision regression guard: a different subject_id, a
# different period, or a different user_id must NOT collide with an
# existing ranking row, even when every other field matches — proves
# the composite constraint is exactly (user_id, subject_id, period),
# not a subset of it, and that NULLS NOT DISTINCT only merges NULLs
# with NULLs, never distinct real UUIDs with each other.
# =====================================================================

def test_rank2_5_different_subject_period_or_user_never_collide(pg_session):
    user_id, subject_id = _make_user_and_subject(pg_session, "RK15")
    repo = RankingRepository(pg_session)

    base = repo.upsert(user_id, subject_id, "all_time", 50.0, 1)
    pg_session.commit()

    # Different period, same user/subject.
    other_period = repo.upsert(user_id, subject_id, "monthly", 50.0, 1)
    pg_session.commit()
    assert other_period.id != base.id

    # Different subject_id (still non-NULL), same user/period.
    other_subject = Subject(name=f"RK15OtherSubj-{uuid.uuid4()}")
    pg_session.add(other_subject)
    pg_session.flush()
    pg_session.commit()
    other_subject_row = repo.upsert(user_id, other_subject.id, "all_time", 50.0, 1)
    pg_session.commit()
    assert other_subject_row.id != base.id

    # Different user, same subject/period.
    other_user_id = _make_user(pg_session, "RK15B")
    other_user_row = repo.upsert(other_user_id, subject_id, "all_time", 50.0, 1)
    pg_session.commit()
    assert other_user_row.id != base.id

    rows = pg_session.execute(
        select(Ranking).where(Ranking.user_id.in_([user_id, other_user_id]))
    ).scalars().all()
    assert len(rows) == 4, f"expected 4 distinct, non-colliding rows, got {len(rows)}"
