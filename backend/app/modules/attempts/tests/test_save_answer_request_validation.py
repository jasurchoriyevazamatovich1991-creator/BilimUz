"""Sprint 73 — VAL-1. Pure Pydantic schema tests — no DB/HTTP needed,
SaveAnswerRequest is a plain BaseModel."""
import uuid

import pytest
from pydantic import ValidationError

from app.modules.attempts.schemas import SaveAnswerRequest


def test_text_answer_at_the_length_limit_is_accepted():
    request = SaveAnswerRequest(question_id=uuid.uuid4(), text_answer="a" * 10_000)
    assert len(request.text_answer) == 10_000


def test_text_answer_over_the_length_limit_is_rejected():
    with pytest.raises(ValidationError):
        SaveAnswerRequest(question_id=uuid.uuid4(), text_answer="a" * 10_001)


def test_text_answer_none_is_still_accepted_unaffected_by_the_new_limit():
    request = SaveAnswerRequest(question_id=uuid.uuid4(), text_answer=None)
    assert request.text_answer is None


def test_short_text_answer_is_unaffected():
    request = SaveAnswerRequest(question_id=uuid.uuid4(), text_answer="A short essay answer.")
    assert request.text_answer == "A short essay answer."
