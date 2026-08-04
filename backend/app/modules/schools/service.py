"""Business logic for school management. No uniqueness constraint on
`name` (schema has none, matches reality — two towns can each have a
"1-maktab") — this is the one deliberate difference from `grades`'
unique-name rule, not an oversight."""
import uuid

from app.core.audit import log_action
from app.modules.schools.exceptions import SchoolNotFoundException
from app.modules.schools.models import School
from app.modules.schools.repository import SchoolRepository
from app.modules.schools.schemas import SchoolCreateRequest, SchoolListParams, SchoolUpdateRequest


class SchoolService:
    def __init__(self, repository: SchoolRepository):
        self.repo = repository

    def get_school(self, school_id: uuid.UUID) -> School:
        school = self.repo.get_by_id(school_id)
        if school is None:
            raise SchoolNotFoundException("Maktab topilmadi")
        return school

    def list_schools(self, params: SchoolListParams) -> tuple[list[School], int]:
        return self.repo.list(params)

    def create_school(self, data: SchoolCreateRequest, actor_id: uuid.UUID) -> School:
        school = School(
            name=data.name, region=data.region, district=data.district,
            address=data.address, phone=data.phone, created_by=actor_id,
        )
        self.repo.create(school)
        log_action(self.repo.db, action="school.created", user_id=actor_id, entity_type="school", entity_id=school.id)
        self.repo.commit()
        return school

    def update_school(self, school_id: uuid.UUID, data: SchoolUpdateRequest, actor_id: uuid.UUID) -> School:
        school = self.get_school(school_id)
        updates = data.model_dump(exclude_unset=True)
        updates["updated_by"] = actor_id
        self.repo.update(school, updates)
        log_action(
            self.repo.db, action="school.updated", user_id=actor_id,
            entity_type="school", entity_id=school_id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return school

    def delete_school(self, school_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        school = self.get_school(school_id)
        self.repo.soft_delete(school)
        log_action(self.repo.db, action="school.deleted", user_id=actor_id, entity_type="school", entity_id=school_id)
        self.repo.commit()
