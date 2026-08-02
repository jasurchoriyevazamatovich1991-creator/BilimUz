"""Pydantic v2 request/response contracts for the results module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.results.validators import validate_ranking_period


class CreateResultRequest(BaseModel):
    attempt_id: uuid.UUID


class ResultOut(BaseModel):
    id: uuid.UUID
    attempt_id: uuid.UUID
    user_id: uuid.UUID
    test_id: uuid.UUID
    score: float
    percentage: float
    is_passed: bool | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResultListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    test_id: uuid.UUID | None = None
    sort: str = "-created_at"


class RankingRecomputeRequest(BaseModel):
    subject_id: uuid.UUID | None = None
    period: str = "all_time"

    @field_validator("period")
    @classmethod
    def _period(cls, v: str) -> str:
        return validate_ranking_period(v)


class RankingRecomputeResponse(BaseModel):
    subject_id: uuid.UUID | None
    period: str
    ranked_count: int
