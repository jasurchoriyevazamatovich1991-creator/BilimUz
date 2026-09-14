"""Data access for LessonProgress. No soft-delete (no `deleted_at`
column exists on this table — see models.py's own note on why
StatusMixin/AuditMixin weren't used)."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.progress.models import LessonProgress


class LessonProgressRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_user_and_lesson(self, user_id: uuid.UUID, lesson_id: uuid.UUID) -> LessonProgress | None:
        """The point lookup the unique(user_id, lesson_id) constraint
        exists for — also the basis of idempotent completion (Phase 3)."""
        stmt = select(LessonProgress).where(LessonProgress.user_id == user_id, LessonProgress.lesson_id == lesson_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID) -> list[LessonProgress]:
        """Unpaginated by design — see schemas.py's MyProgressOut
        docstring for the rationale (small realistic total lesson count
        this sprint; documented as a future scaling limitation)."""
        stmt = select(LessonProgress).where(LessonProgress.user_id == user_id)
        return list(self.db.execute(stmt).scalars().all())

    def count_all_lessons(self) -> int:
        """The denominator for the Dashboard's X/Y — total lessons a
        student can actually see (status=active, not soft-deleted),
        matching the exact same filter the public GET /lessons?status=
        active endpoint already applies — not a raw, unfiltered count."""
        from app.modules.lessons.models import Lesson  # local import: progress reads Lesson read-only, avoids a module-load-order cycle
        stmt = select(func.count()).select_from(Lesson).where(Lesson.status == "active", Lesson.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one()

    def create(self, progress: LessonProgress) -> LessonProgress:
        self.db.add(progress)
        self.db.flush()
        return progress
