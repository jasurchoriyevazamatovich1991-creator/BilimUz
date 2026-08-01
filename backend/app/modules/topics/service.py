"""
Business logic for topic management. Validates subject_id/grade_id
references using the existing, unmodified SubjectRepository and
GradeRepository (read-only reuse — same pattern as roles/repository.py
reading users.models for referential checks). This is a one-directional
dependency (topics → subjects, topics → grades), never the reverse.
"""
import uuid

from app.core.audit import log_action
from app.modules.grades.repository import GradeRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.topics.exceptions import (
    InvalidGradeReferenceException,
    InvalidSubjectReferenceException,
    TopicNotFoundException,
)
from app.modules.topics.models import Topic
from app.modules.topics.repository import TopicRepository
from app.modules.topics.schemas import TopicCreateRequest, TopicListParams, TopicUpdateRequest


class TopicService:
    def __init__(self, repository: TopicRepository, subject_repository: SubjectRepository, grade_repository: GradeRepository):
        self.repo = repository
        self.subject_repo = subject_repository
        self.grade_repo = grade_repository

    def get_topic(self, topic_id: uuid.UUID) -> Topic:
        topic = self.repo.get_by_id(topic_id)
        if topic is None:
            raise TopicNotFoundException("Mavzu topilmadi")
        return topic

    def list_topics(self, params: TopicListParams) -> tuple[list[Topic], int]:
        return self.repo.list(params)

    def create_topic(self, data: TopicCreateRequest, actor_id: uuid.UUID) -> Topic:
        if self.subject_repo.get_by_id(data.subject_id) is None:
            raise InvalidSubjectReferenceException("Ko'rsatilgan fan (subject_id) mavjud emas")
        if data.grade_id is not None and self.grade_repo.get_by_id(data.grade_id) is None:
            raise InvalidGradeReferenceException("Ko'rsatilgan sinf/daraja (grade_id) mavjud emas")

        topic = Topic(
            subject_id=data.subject_id,
            grade_id=data.grade_id,
            title=data.title,
            description=data.description,
            order_number=data.order_number,
            created_by=actor_id,
        )
        self.repo.create(topic)
        log_action(self.repo.db, action="topic.created", user_id=actor_id, entity_type="topic", entity_id=topic.id)
        self.repo.commit()
        return topic

    def update_topic(self, topic_id: uuid.UUID, data: TopicUpdateRequest, actor_id: uuid.UUID) -> Topic:
        topic = self.get_topic(topic_id)
        updates = data.model_dump(exclude_unset=True)

        if "grade_id" in updates and updates["grade_id"] is not None:
            if self.grade_repo.get_by_id(updates["grade_id"]) is None:
                raise InvalidGradeReferenceException("Ko'rsatilgan sinf/daraja (grade_id) mavjud emas")

        updates["updated_by"] = actor_id
        self.repo.update(topic, updates)
        log_action(
            self.repo.db, action="topic.updated", user_id=actor_id,
            entity_type="topic", entity_id=topic_id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return topic

    def delete_topic(self, topic_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        topic = self.get_topic(topic_id)
        self.repo.soft_delete(topic)
        log_action(self.repo.db, action="topic.deleted", user_id=actor_id, entity_type="topic", entity_id=topic_id)
        self.repo.commit()
