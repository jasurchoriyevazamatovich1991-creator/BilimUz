"""
Request/response contracts for the isolated Login API. LoginResponse
carries explicit expiration metadata (both a relative "seconds from now"
value and an absolute timestamp) — deliberately not a bare TokenPair,
since this step's requirement explicitly asks for expiration metadata
that Step 2's TokenPair (Step 2 is 'completed', not modified here) does
not carry.
"""
from datetime import datetime

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expires_in: int   # seconds from issuance until expiry
    access_token_expires_at: datetime
    refresh_token_expires_in: int
    refresh_token_expires_at: datetime
