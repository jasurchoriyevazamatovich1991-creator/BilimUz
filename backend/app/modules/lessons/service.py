"""
Business logic for lesson management. Validates topic_id references using
the existing, unmodified TopicRepository (read-only reuse, one-directional
dependency lessons → topics, same pattern as topics → subjects/grades).
"""
import uuid

from app.core.audit import log_action
from app.modules.lessons.exceptions import (
    EmptyLessonContentException,
    InvalidTopicReferenceException,
    LessonNotFoundException,
)
from app.modules.lessons.models import Lesson
from app.modules.lessons.repository import LessonRepository
from app.modules.lessons.schemas import LessonCreateRequest, LessonListParams, LessonUpdateRequest
from app.modules.topics.repository import TopicRepository


class LessonService:
    def __init__(self, repository: LessonRepository, topic_repository: TopicRepository):
        self.repo = repository
        self.topic_repo = topic_repository

    def get_lesson(self, lesson_id: uuid.UUID) -> Lesson:
        lesson = self.repo.get_by_id(lesson_id)
        if lesson is None:
            raise LessonNotFoundException("Dars topilmadi")
        return lesson

    def list_lessons(self, params: LessonListParams) -> tuple[list[Lesson], int]:
        return self.repo.list(params)

    def create_lesson(self, data: LessonCreateRequest, actor_id: uuid.UUID) -> Lesson:
        if self.topic_repo.get_by_id(data.topic_id) is None:
            raise InvalidTopicReferenceException("Ko'rsatilgan mavzu (topic_id) mavjud emas")

        lesson = Lesson(
            topic_id=data.topic_id,
            title=data.title,
            video=data.video,
            pdf=data.pdf,
            content=data.content,
            created_by=actor_id,
        )
        self.repo.create(lesson)
        log_action(self.repo.db, action="lesson.created", user_id=actor_id, entity_type="lesson", entity_id=lesson.id)
        self.repo.commit()
        return lesson

    def update_lesson(self, lesson_id: uuid.UUID, data: LessonUpdateRequest, actor_id: uuid.UUID) -> Lesson:
        lesson = self.get_lesson(lesson_id)
        updates = data.model_dump(exclude_unset=True)

        self._reject_if_would_leave_empty_content(lesson, updates)

        updates["updated_by"] = actor_id
        self.repo.update(lesson, updates)
        log_action(
            self.repo.db, action="lesson.updated", user_id=actor_id,
            entity_type="lesson", entity_id=lesson_id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return lesson

    def delete_lesson(self, lesson_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        lesson = self.get_lesson(lesson_id)
        self.repo.soft_delete(lesson)
        log_action(self.repo.db, action="lesson.deleted", user_id=actor_id, entity_type="lesson", entity_id=lesson_id)
        self.repo.commit()

    def _reject_if_would_leave_empty_content(self, lesson: Lesson, updates: dict) -> None:
        """An update must not result in a lesson with zero content fields.
        Merges the incoming update onto the current state before checking,
        since a PATCH only carries the fields the caller wants to change."""
        final_video = updates.get("video", lesson.video)
        final_pdf = updates.get("pdf", lesson.pdf)
        final_content = updates.get("content", lesson.content)
        if not (final_video or final_pdf or final_content):
            raise EmptyLessonContentException(
                "Dars kamida bitta mazmun turiga ega bo'lishi kerak: video, pdf yoki content"
            )
