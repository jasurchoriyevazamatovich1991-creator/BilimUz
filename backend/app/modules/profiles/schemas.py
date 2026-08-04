"""
Pydantic v2 request/response contracts for the profiles module.

ProfileOut is the module's key design decision (Variant A, approved):
it COMPOSES fields from both User and Profile rather than duplicating
storage. first_name/last_name/phone/gender/birth_date/image are read
from User (single source of truth); bio/address/telegram/instagram/
website/school_id/learning_center_id are read from Profile.
"""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.profiles.validators import validate_address, validate_bio, validate_social_handle, validate_website


class ProfileUpdateRequest(BaseModel):
    """Only Profile-owned fields — never first_name/last_name/etc.,
    which belong to the `users` module and are not editable here (per
    Variant A: this module never writes to User)."""
    bio: str | None = None
    address: str | None = None
    telegram: str | None = None
    instagram: str | None = None
    website: str | None = None
    school_id: uuid.UUID | None = None
    learning_center_id: uuid.UUID | None = None

    @field_validator("bio")
    @classmethod
    def _bio(cls, v: str | None) -> str | None:
        return validate_bio(v)

    @field_validator("address")
    @classmethod
    def _address(cls, v: str | None) -> str | None:
        return validate_address(v)

    @field_validator("telegram", "instagram")
    @classmethod
    def _social(cls, v: str | None) -> str | None:
        return validate_social_handle(v)

    @field_validator("website")
    @classmethod
    def _website(cls, v: str | None) -> str | None:
        return validate_website(v)


class ProfileOut(BaseModel):
    # From User (single source of truth — never stored here)
    user_id: uuid.UUID
    first_name: str
    last_name: str
    phone: str | None
    gender: str | None
    birth_date: date | None
    image: str | None

    # From Profile
    bio: str | None
    address: str | None
    telegram: str | None
    instagram: str | None
    website: str | None
    school_id: uuid.UUID | None
    learning_center_id: uuid.UUID | None
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def compose(cls, user, profile) -> "ProfileOut":
        """The one place User and Profile data are merged — every
        service method returns through this, so there's exactly one
        composition path to keep consistent."""
        return cls(
            user_id=user.id, first_name=user.first_name, last_name=user.last_name,
            phone=user.phone, gender=user.gender, birth_date=user.birth_date, image=user.image,
            bio=profile.bio, address=profile.address, telegram=profile.telegram,
            instagram=profile.instagram, website=profile.website,
            school_id=profile.school_id, learning_center_id=profile.learning_center_id,
            status=profile.status, created_at=profile.created_at, updated_at=profile.updated_at,
        )


class ProfileListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    school_id: uuid.UUID | None = None
    learning_center_id: uuid.UUID | None = None
