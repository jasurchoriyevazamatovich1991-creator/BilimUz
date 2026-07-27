"""Response contract for GET /me. No password_hash field anywhere in this
file — that's the whole point of the requirement."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class RoleInfo(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    status: str
    role: RoleInfo | None = None  # "if available" — None if the relationship can't be resolved
    created_at: datetime

    model_config = {"from_attributes": True}
