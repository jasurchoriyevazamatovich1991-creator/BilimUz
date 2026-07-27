"""Business logic for GET /me — deliberately thin. The interesting work
(token verification, user lookup) already happened in dependencies.py by
the time this runs; this just shapes the response."""
from app.modules.auth.me.schemas import MeResponse, RoleInfo
from app.modules.users.models import User


class MeService:
    def get_profile(self, user: User) -> MeResponse:
        role_info = RoleInfo.model_validate(user.role) if user.role is not None else None
        return MeResponse(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            email=user.email,
            status=user.status,
            role=role_info,
            created_at=user.created_at,
        )
