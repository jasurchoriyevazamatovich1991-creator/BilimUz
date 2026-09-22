"""Data-access layer for TestAttempt and Answer — two repositories in one
file, same cohesive-module reasoning as questions/repository.py."""
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.attempts.models import Answer, AttemptModuleProgress, TestAttempt
from app.modules.attempts.schemas import AttemptListParams


class AttemptRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, attempt_id: uuid.UUID) -> TestAttempt | None:
        stmt = select(TestAttempt).where(TestAttempt.id == attempt_id, TestAttempt.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id_locked(self, attempt_id: uuid.UUID) -> TestAttempt | None:
        """Sprint 54 — same real PostgreSQL row-lock pattern as Sprint
        50's AttemptModuleProgressRepository.get_for_attempt_and_module_locked
        (SELECT ... FOR UPDATE + populate_existing=True). Used by
        ResultService.create_result() to serialize concurrent
        Result-creation requests for the SAME attempt: the second
        concurrent caller blocks here until the first one's transaction
        commits (releasing the lock), then re-reads the attempt's
        current state and — critically — re-checks for an
        already-created Result under this same lock, so it observes
        the first caller's now-committed Result instead of racing past
        an earlier unlocked existence check."""
        stmt = (
            select(TestAttempt)
            .where(TestAttempt.id == attempt_id, TestAttempt.deleted_at.is_(None))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def acquire_start_attempt_lock(self, user_id: uuid.UUID, test_id: uuid.UUID) -> None:
        """Sprint 60 — S60-A. Transaction-scoped PostgreSQL advisory lock
        serializing concurrent AttemptService.start_attempt() calls for
        the SAME (user_id, test_id) pair, closing the check-then-act race
        between count_for_user_and_test() and create() that previously
        let concurrent requests exceed Test.max_attempts (two requests
        could both observe count < max_attempts before either commits
        its INSERT).

        Unlike Sprint 50/54/59's SELECT ... FOR UPDATE row locks (which
        need an existing row to lock), there is no natural row to lock
        here before the very first attempt for a (user, test) pair
        exists — a PostgreSQL advisory lock keyed on the pair itself is
        the standard mechanism for this shape of problem, and is a pure
        synchronization primitive: it does not touch or validate any
        row, so it cannot bypass ownership, max_attempts, soft-delete,
        or status checks, which remain exactly where they already were.

        pg_advisory_xact_lock(key1, key2) takes two 32-bit integers and
        is held only for the current transaction, releasing automatically
        on COMMIT or ROLLBACK — never needs an explicit unlock call and
        never outlives the connection — matching this codebase's existing
        lock-for-the-duration-of-one-transaction idiom (the FOR UPDATE
        locks above release the same way). hashtext(...) is PostgreSQL's
        own deterministic string hash returning a signed int4; using it
        instead of converting the UUIDs in Python sidesteps any
        Python-side integer overflow/sign-conversion pitfalls, and
        keeping user_id/test_id as two independent keys (rather than
        hashing their concatenation into one key) means two different
        (user, test) pairs essentially never contend with each other —
        only two calls for the exact same pair do, which is exactly the
        critical section that needs serializing."""
        self.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:user_id), hashtext(:test_id))"),
            {"user_id": str(user_id), "test_id": str(test_id)},
        )

    def count_for_user_and_test(self, user_id: uuid.UUID, test_id: uuid.UUID) -> int:
        """Every attempt ever started counts toward the limit, including
        abandoned in_progress ones — matches the platform's max-attempts
        semantics (starting counts, not just finishing)."""
        stmt = select(func.count()).select_from(TestAttempt).where(
            TestAttempt.user_id == user_id, TestAttempt.test_id == test_id, TestAttempt.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one()

    def list_for_user(self, user_id: uuid.UUID, params: AttemptListParams) -> tuple[list[TestAttempt], int]:
        stmt = select(TestAttempt).where(TestAttempt.user_id == user_id, TestAttempt.deleted_at.is_(None))
        if params.test_id:
            stmt = stmt.where(TestAttempt.test_id == params.test_id)
        if params.status:
            stmt = stmt.where(TestAttempt.status == params.status)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(TestAttempt.start_time.desc())
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def create(self, attempt: TestAttempt) -> TestAttempt:
        self.db.add(attempt)
        self.db.flush()
        return attempt

    def update(self, attempt: TestAttempt, data: dict) -> TestAttempt:
        for field, value in data.items():
            setattr(attempt, field, value)
        self.db.flush()
        return attempt

    def commit(self) -> None:
        self.db.commit()


class AnswerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, attempt_id: uuid.UUID, question_id: uuid.UUID) -> Answer | None:
        stmt = select(Answer).where(
            Answer.attempt_id == attempt_id, Answer.question_id == question_id, Answer.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_attempt(self, attempt_id: uuid.UUID) -> list[Answer]:
        stmt = select(Answer).where(Answer.attempt_id == attempt_id, Answer.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def create(self, answer: Answer) -> Answer:
        self.db.add(answer)
        self.db.flush()
        return answer

    def update(self, answer: Answer, data: dict) -> Answer:
        for field, value in data.items():
            setattr(answer, field, value)
        self.db.flush()
        return answer

    def upsert(self, attempt_id: uuid.UUID, question_id: uuid.UUID, values: dict) -> Answer:
        """Sprint 58 — replaces the old get()-then-create()/update()
        check-then-act call sites in AttemptService.save_answer().

        uq_answers_attempt_question (on (attempt_id, question_id)) has
        existed in the database since migration 0001 — so a duplicate
        Answer row was never actually possible. The real bug was that
        the old check-then-act had no way to know that: two concurrent
        PATCH /attempts/{id}/answer calls for the same question could
        both find no existing row via get(), both call create(), and
        the LOSING side's INSERT would raise an unhandled
        IntegrityError (a 500) instead of succeeding as an update.

        A single INSERT ... ON CONFLICT DO UPDATE is atomic — Postgres
        itself resolves the conflict against that exact constraint, so
        the losing side becomes a graceful UPDATE of the winning row
        instead of a crash. `values` carries exactly the fields the two
        save_answer() branches already computed (selected_option/
        selected_options/is_correct) — unchanged from the old
        create()/update() call sites; text_answer is untouched either
        way, same as before."""
        stmt = (
            pg_insert(Answer)
            .values(attempt_id=attempt_id, question_id=question_id, **values)
            .on_conflict_do_update(
                constraint="uq_answers_attempt_question",
                set_={**values, "updated_at": func.now()},
            )
        )
        self.db.execute(stmt)
        self.db.flush()
        return self.get(attempt_id, question_id)


class AttemptModuleProgressRepository:
    """Sprint 50 — new. Sprint 46 created the AttemptModuleProgress
    model but no repository ever used it (verified: Sprint 46's own
    integration tests read/write it directly via the SQLAlchemy
    session, not through a repository — this sprint is the first real
    consumer)."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, progress_id: uuid.UUID) -> AttemptModuleProgress | None:
        return self.db.get(AttemptModuleProgress, progress_id)

    def get_for_attempt_and_module(self, attempt_id: uuid.UUID, module_id: uuid.UUID) -> AttemptModuleProgress | None:
        stmt = select(AttemptModuleProgress).where(
            AttemptModuleProgress.attempt_id == attempt_id, AttemptModuleProgress.module_id == module_id,
        )
        return self.db.scalars(stmt).first()

    def get_for_attempt_and_module_locked(self, attempt_id: uuid.UUID, module_id: uuid.UUID) -> AttemptModuleProgress | None:
        """Sprint 50 CRITICAL-1 fix. SELECT ... FOR UPDATE on the exact
        (attempt_id, module_id) row — a real PostgreSQL row-level lock,
        held until this transaction commits or rolls back. A second
        concurrent transaction calling this same method for the same
        row blocks here until the first one finishes, then
        (populate_existing=True) re-reads the row's now-current,
        post-commit column values — even if this exact object was
        already loaded earlier in this same session by the plain,
        unlocked get_for_attempt_and_module() call. Without
        populate_existing, SQLAlchemy's identity map would silently
        hand back the earlier (now-stale) in-memory attributes instead
        of the fresh, post-lock database state, defeating the lock's
        entire purpose."""
        stmt = (
            select(AttemptModuleProgress)
            .where(AttemptModuleProgress.attempt_id == attempt_id, AttemptModuleProgress.module_id == module_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.db.scalars(stmt).first()

    def get_active_for_attempt(self, attempt_id: uuid.UUID) -> AttemptModuleProgress | None:
        """The one module currently in progress for this attempt — by
        construction (this sprint's execution flow) there is at most
        one at a time; a submitted module's progress row is never
        reused."""
        stmt = select(AttemptModuleProgress).where(
            AttemptModuleProgress.attempt_id == attempt_id, AttemptModuleProgress.status == "in_progress",
        )
        return self.db.scalars(stmt).first()

    def list_for_attempt(self, attempt_id: uuid.UUID) -> list[AttemptModuleProgress]:
        stmt = select(AttemptModuleProgress).where(AttemptModuleProgress.attempt_id == attempt_id)
        return list(self.db.scalars(stmt).all())

    def create(self, progress: AttemptModuleProgress) -> AttemptModuleProgress:
        self.db.add(progress)
        self.db.flush()
        return progress

    def update(self, progress: AttemptModuleProgress, data: dict) -> AttemptModuleProgress:
        for field, value in data.items():
            setattr(progress, field, value)
        self.db.flush()
        return progress
