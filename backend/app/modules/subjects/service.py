"""
Business logic for the subjects module. Enforces uniqueness, soft-delete
semantics, and sort-field allowlisting — never trusts the repository or
router to do it.
"""
import uuid

from app.modules.subjects.constants import ALLOWED_SORT_FIELDS, DEFAULT_SORT_FIELD
from app.modules.subjects.exceptions import SubjectAlreadyExistsException, SubjectNotFoundException
from app.modules.subjects.models import Subject
from app.modules.subjects.repository import SubjectRepository
from app.modules.subjects.schemas import SubjectCreateRequest, SubjectListParams, SubjectUpdateRequest


class SubjectService:
    def __init__(self, repository: SubjectRepository):
        self.repo = repository

    def list_subjects(self, params: SubjectListParams) -> tuple[list[Subject], int]:
        params.sort = self._safe_sort_field(params.sort)
        return self.repo.list(params)

    def get_subject(self, subject_id: uuid.UUID) -> Subject:
        subject = self.repo.get_by_id(subject_id)
        if subject is None:
            raise SubjectNotFoundException("Fan topilmadi")
        return subject

    def create_subject(self, data: SubjectCreateRequest, actor_id: uuid.UUID) -> Subject:
        if self.repo.get_by_name(data.name):
            raise SubjectAlreadyExistsException("Bu nomdagi fan allaqachon mavjud")

        subject = Subject(name=data.name, icon=data.icon, color=data.color, created_by=actor_id)
        self.repo.create(subject)
        self.repo.commit()
        return subject

    def update_subject(self, subject_id: uuid.UUID, data: SubjectUpdateRequest, actor_id: uuid.UUID) -> Subject:
        subject = self.get_subject(subject_id)
        updates = data.model_dump(exclude_unset=True)

        if "name" in updates and updates["name"] != subject.name:
            if self.repo.get_by_name(updates["name"], exclude_id=subject_id):
                raise SubjectAlreadyExistsException("Bu nomdagi fan allaqachon mavjud")

        updates["updated_by"] = actor_id
        self.repo.update(subject, updates)
        self.repo.commit()
        return subject

    def delete_subject(self, subject_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        subject = self.get_subject(subject_id)
        self.repo.soft_delete(subject, deleted_by=actor_id)
        self.repo.commit()

    def _safe_sort_field(self, sort: str) -> str:
        field_name = sort.lstrip("-")
        return sort if field_name in ALLOWED_SORT_FIELDS else DEFAULT_SORT_FIELD
