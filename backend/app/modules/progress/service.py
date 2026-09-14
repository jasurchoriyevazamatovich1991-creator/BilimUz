"""Business logic for Student Progress / Lesson Completion (Sprint 36).

LessonRepository is a new, READ-ONLY cross-module dependency (same
one-directional shape already established throughout this project —
e.g. uploads/service.py reads LessonRepository read-only for Sprint
27's lesson_id validation, questions/service.py reads UploadRepository
read-only for Sprint 32's media validation). This service never writes
to Lessons.
"""
import uuid
from datetime import datetime, timezone

from app.core.audit import log_action
from app.modules.lessons.repository import LessonRepository
from app.modules.progress.exceptions import LessonNotFoundForProgressException
from app.modules.progress.models import LessonProgress
from app.modules.progress.repository import LessonProgressRepository
from app.modules.progress.schemas import MyProgressOut


class ProgressService:
    def __init__(self, repository: LessonProgressRepository, lesson_repository: LessonRepository):
        self.repo = repository
        self.lesson_repo = lesson_repository

    def complete_lesson(self, user_id: uuid.UUID, lesson_id: uuid.UUID) -> LessonProgress:
        """Idempotent — verified by test: calling this twice for the
        same (user_id, lesson_id) never creates a second row. The
        unique(user_id, lesson_id) DB constraint is the real safety net
        (protects even against a race between two concurrent requests);
        this existence check is the fast, common-case path that avoids
        relying on catching an IntegrityError under normal conditions."""
        if self.lesson_repo.get_by_id(lesson_id) is None:
            raise LessonNotFoundForProgressException("Dars topilmadi")

        existing = self.repo.get_for_user_and_lesson(user_id, lesson_id)
        if existing is not None:
            return existing

        progress = LessonProgress(user_id=user_id, lesson_id=lesson_id, completed_at=datetime.now(timezone.utc))
        self.repo.create(progress)
        log_action(self.repo.db, action="lesson.completed", user_id=user_id, entity_type="lesson_progress", entity_id=progress.id)
        self.repo.db.commit()
        return progress

    def get_my_progress(self, user_id: uuid.UUID) -> MyProgressOut:
        """user_id always comes from the authenticated caller (see
        router.py) — never from a request parameter, so a student can
        never read anyone else's progress (Phase 4's core requirement)."""
        my_progress = self.repo.list_for_user(user_id)
        total_lessons = self.repo.count_all_lessons()
        completed_count = len(my_progress)
        percentage = round((completed_count / total_lessons) * 100, 1) if total_lessons > 0 else 0.0
        return MyProgressOut(
            completed_lessons=completed_count,
            total_lessons=total_lessons,
            percentage=percentage,
            completed_lesson_ids=[p.lesson_id for p in my_progress],
        )
