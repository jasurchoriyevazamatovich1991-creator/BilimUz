"""Request/response contracts for the isolated Refresh Token API. Same
expiration-metadata shape as login/schemas.py — kept as a separate
definition (not imported from there) since each Sprint 3 step is a
self-contained module per the step-by-step build instructions."""
from datetime import datetime

from pydantic import BaseModel


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str  # rotated — the old one is revoked, this is new
    token_type: str = "bearer"
    access_token_expires_in: int
    access_token_expires_at: datetime
    refresh_token_expires_in: int
    refresh_token_expires_at: datetime
