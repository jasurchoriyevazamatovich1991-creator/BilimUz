"""Pydantic v2 request/response contracts for the analytics module."""
import uuid
from datetime import date

from pydantic import BaseModel, model_validator

from app.modules.analytics.validators import validate_date_range


class RecomputeDailyRequest(BaseModel):
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def _validate_range(self) -> "RecomputeDailyRequest":
        validate_date_range(self.date_from, self.date_to)
        return self


class RecomputeMonthlyRequest(BaseModel):
    month: int
    year: int


class RecomputeResponse(BaseModel):
    buckets_updated: int


class DailyStatOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    subject_id: uuid.UUID | None
    stat_date: date
    tests_taken: int
    correct_answers: int
    wrong_answers: int

    model_config = {"from_attributes": True}


class MonthlyStatOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    subject_id: uuid.UUID | None
    month: int
    year: int
    tests_taken: int
    avg_score: float | None

    model_config = {"from_attributes": True}
