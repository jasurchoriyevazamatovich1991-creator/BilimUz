"""Business logic for grade management. Same shape as roles/subjects
services — uniqueness enforced case-insensitively, soft delete, audit log."""
import uuid

from app.core.audit import log_action
from app.modules.grades.exceptions import GradeAlreadyExistsException, GradeNotFoundException
from app.modules.grades.models import Grade
from app.modules.grades.repository import GradeRepository
from app.modules.grades.schemas import GradeCreateRequest, GradeListParams, GradeUpdateRequest


class GradeService:
    def __init__(self, repository: GradeRepository):
        self.repo = repository

    def get_grade(self, grade_id: uuid.UUID) -> Grade:
        grade = self.repo.get_by_id(grade_id)
        if grade is None:
            raise GradeNotFoundException("Sinf/daraja topilmadi")
        return grade

    def list_grades(self, params: GradeListParams) -> tuple[list[Grade], int]:
        return self.repo.list(params)

    def create_grade(self, data: GradeCreateRequest, actor_id: uuid.UUID) -> Grade:
        if self.repo.get_by_name(data.name):
            raise GradeAlreadyExistsException("Bu nomdagi sinf/daraja allaqachon mavjud")

        grade = Grade(name=data.name, created_by=actor_id)
        self.repo.create(grade)
        log_action(self.repo.db, action="grade.created", user_id=actor_id, entity_type="grade", entity_id=grade.id)
        self.repo.commit()
        return grade

    def update_grade(self, grade_id: uuid.UUID, data: GradeUpdateRequest, actor_id: uuid.UUID) -> Grade:
        grade = self.get_grade(grade_id)
        updates = data.model_dump(exclude_unset=True)
        updates["updated_by"] = actor_id
        self.repo.update(grade, updates)
        log_action(
            self.repo.db, action="grade.updated", user_id=actor_id,
            entity_type="grade", entity_id=grade_id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return grade

    def delete_grade(self, grade_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        grade = self.get_grade(grade_id)
        self.repo.soft_delete(grade)
        log_action(self.repo.db, action="grade.deleted", user_id=actor_id, entity_type="grade", entity_id=grade_id)
        self.repo.commit()
