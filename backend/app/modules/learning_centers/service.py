"""Business logic for learning center management. No uniqueness
constraint on `name` (schema has none), same reasoning as schools."""
import uuid

from app.core.audit import log_action
from app.modules.learning_centers.exceptions import LearningCenterNotFoundException
from app.modules.learning_centers.models import LearningCenter
from app.modules.learning_centers.repository import LearningCenterRepository
from app.modules.learning_centers.schemas import LearningCenterCreateRequest, LearningCenterListParams, LearningCenterUpdateRequest


class LearningCenterService:
    def __init__(self, repository: LearningCenterRepository):
        self.repo = repository

    def get_center(self, center_id: uuid.UUID) -> LearningCenter:
        center = self.repo.get_by_id(center_id)
        if center is None:
            raise LearningCenterNotFoundException("O'quv markazi topilmadi")
        return center

    def list_centers(self, params: LearningCenterListParams) -> tuple[list[LearningCenter], int]:
        return self.repo.list(params)

    def create_center(self, data: LearningCenterCreateRequest, actor_id: uuid.UUID) -> LearningCenter:
        center = LearningCenter(
            name=data.name, owner_name=data.owner_name, phone=data.phone, region=data.region, created_by=actor_id,
        )
        self.repo.create(center)
        log_action(self.repo.db, action="learning_center.created", user_id=actor_id, entity_type="learning_center", entity_id=center.id)
        self.repo.commit()
        return center

    def update_center(self, center_id: uuid.UUID, data: LearningCenterUpdateRequest, actor_id: uuid.UUID) -> LearningCenter:
        center = self.get_center(center_id)
        updates = data.model_dump(exclude_unset=True)
        updates["updated_by"] = actor_id
        self.repo.update(center, updates)
        log_action(
            self.repo.db, action="learning_center.updated", user_id=actor_id,
            entity_type="learning_center", entity_id=center_id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return center

    def delete_center(self, center_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        center = self.get_center(center_id)
        self.repo.soft_delete(center)
        log_action(self.repo.db, action="learning_center.deleted", user_id=actor_id, entity_type="learning_center", entity_id=center_id)
        self.repo.commit()
