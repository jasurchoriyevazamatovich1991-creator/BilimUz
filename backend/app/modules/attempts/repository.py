"""Data-access layer for TestAttempt and Answer — two repositories in one
file, same cohesive-module reasoning as questions/repository.py."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.attempts.models import Answer, AttemptModuleProgress, TestAttempt
from app.modules.attempts.schemas import AttemptListParams


class AttemptRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, attempt_id: uuid.UUID) -> TestAttempt | None:
        stmt = select(TestAttempt).where(TestAttempt.id == attempt_id, TestAttempt.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

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
