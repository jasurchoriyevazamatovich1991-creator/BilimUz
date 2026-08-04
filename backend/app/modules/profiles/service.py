"""
Business logic for profiles. Reads UserRepository, SchoolRepository,
LearningCenterRepository — all read-only, unmodified (same one-directional
dependency pattern as topics -> subjects/grades).

Lazy get-or-create: a Profile row is created on first access (GET/PATCH
/profiles/me) rather than at registration time — this deliberately avoids
touching `auth/service.py` (stable since Sprint 4's Auth Cutover), per
"do not modify other modules unless required."
"""
import uuid

from app.core.audit import log_action
from app.modules.learning_centers.repository import LearningCenterRepository
from app.modules.profiles.exceptions import (
    InvalidLearningCenterReferenceException,
    InvalidSchoolReferenceException,
    ProfileNotFoundException,
)
from app.modules.profiles.models import Profile
from app.modules.profiles.repository import ProfileRepository
from app.modules.profiles.schemas import ProfileListParams, ProfileOut, ProfileUpdateRequest
from app.modules.schools.repository import SchoolRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


class ProfileService:
    def __init__(
        self,
        repository: ProfileRepository,
        user_repository: UserRepository,
        school_repository: SchoolRepository,
        learning_center_repository: LearningCenterRepository,
    ):
        self.repo = repository
        self.user_repo = user_repository
        self.school_repo = school_repository
        self.learning_center_repo = learning_center_repository

    def get_profile(self, target_user_id: uuid.UUID) -> ProfileOut:
        user = self._require_user(target_user_id)
        profile = self._get_or_create(target_user_id)
        return ProfileOut.compose(user, profile)

    def update_profile(self, target_user_id: uuid.UUID, data: ProfileUpdateRequest, actor_id: uuid.UUID) -> ProfileOut:
        user = self._require_user(target_user_id)
        profile = self._get_or_create(target_user_id)

        updates = data.model_dump(exclude_unset=True)
        self._validate_references(updates)
        updates["updated_by"] = actor_id
        self.repo.update(profile, updates)
        log_action(
            self.repo.db, action="profile.updated", user_id=actor_id,
            entity_type="profile", entity_id=profile.id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return ProfileOut.compose(user, profile)

    def list_profiles(self, params: ProfileListParams) -> tuple[list[ProfileOut], int]:
        profiles, total = self.repo.list(params)
        composed = [ProfileOut.compose(u, p) for p, u in self._pair_with_users(profiles)]
        return composed, total

    def _pair_with_users(self, profiles: list[Profile]) -> list[tuple[Profile, User]]:
        pairs = []
        for profile in profiles:
            user = self.user_repo.get_by_id(profile.user_id)
            if user is not None:  # a profile whose user was hard-deleted (shouldn't happen, CASCADE) — skip defensively
                pairs.append((profile, user))
        return pairs

    def _get_or_create(self, user_id: uuid.UUID) -> Profile:
        profile = self.repo.get_by_user_id(user_id)
        if profile is not None:
            return profile
        profile = Profile(user_id=user_id, created_by=user_id)
        self.repo.create(profile)
        self.repo.commit()
        return profile

    def _require_user(self, user_id: uuid.UUID) -> User:
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise ProfileNotFoundException("Foydalanuvchi topilmadi")
        return user

    def _validate_references(self, updates: dict) -> None:
        if "school_id" in updates and updates["school_id"] is not None:
            if self.school_repo.get_by_id(updates["school_id"]) is None:
                raise InvalidSchoolReferenceException("Ko'rsatilgan maktab (school_id) mavjud emas")
        if "learning_center_id" in updates and updates["learning_center_id"] is not None:
            if self.learning_center_repo.get_by_id(updates["learning_center_id"]) is None:
                raise InvalidLearningCenterReferenceException("Ko'rsatilgan o'quv markazi (learning_center_id) mavjud emas")
