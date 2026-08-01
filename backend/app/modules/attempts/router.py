"""
HTTP layer for /api/v1/attempts/*. Every endpoint requires authentication
— there is no public access to any attempt data. Ownership is enforced
inside the service layer (AttemptNotFoundException doubles as "not
yours"), not here — the router never trusts a path parameter alone.

No role restrictions beyond "authenticated" — any logged-in user (Student,
Applicant, etc.) can take a test; this is intentionally different from
tests/questions, which are Admin/Teacher-authored content.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.attempts.dependencies import get_attempt_service
from app.modules.attempts.schemas import (
    AttemptDetailOut,
    AttemptListParams,
    AttemptOut,
    SaveAnswerRequest,
    StartAttemptRequest,
    SubmitResultOut,
)
from app.modules.attempts.service import AttemptService
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User

router = APIRouter(prefix="/attempts", tags=["Attempts"])


@router.post(
    "/start",
    status_code=status.HTTP_201_CREATED,
    summary="Start a test attempt",
    description="Creates a new attempt: validates the test is published, enforces the max-attempts "
                "limit, randomizes question order if the test's shuffle_questions is true, and "
                "computes the expiry timestamp from the test's duration. 422 if the test isn't "
                "published; 409 if the attempt limit is already reached.",
)
def start_attempt(
    data: StartAttemptRequest,
    service: AttemptService = Depends(get_attempt_service),
    user: User = Depends(get_current_user),
):
    attempt = service.start_attempt(data.test_id, user_id=user.id)
    return success_response(AttemptOut.model_validate(attempt), "Urinish boshlandi.")


@router.get(
    "/me",
    summary="List my attempts",
    description="Paginated list of the current user's own attempts, optionally filtered by test_id/status.",
)
def list_my_attempts(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    test_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    service: AttemptService = Depends(get_attempt_service),
    user: User = Depends(get_current_user),
):
    params = AttemptListParams(page=page, per_page=per_page, test_id=test_id, status=status_filter)
    items, total = service.list_my_attempts(user.id, params)
    data = {
        "items": [AttemptOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Mening urinishlarim.")


@router.get(
    "/{attempt_id}",
    summary="Resume / view an attempt",
    description="Returns full state for an active attempt: questions in the persisted order, "
                "which are already answered — NEVER which answer is correct. If the timer has "
                "expired since the last request, this call lazily auto-finishes the attempt first.",
)
def get_attempt(
    attempt_id: uuid.UUID,
    service: AttemptService = Depends(get_attempt_service),
    user: User = Depends(get_current_user),
):
    detail: AttemptDetailOut = service.get_attempt_detail(attempt_id, user_id=user.id)
    return success_response(detail, "Urinish holati.")


@router.patch(
    "/{attempt_id}/answer",
    summary="Save an answer (auto-save)",
    description="Upserts the answer for one question. Safe to call repeatedly (e.g. on every option "
                "click) — always overwrites the previous answer for that question. 409 if the attempt "
                "is no longer active (submitted, auto-finished, or just expired in this same request).",
)
def save_answer(
    attempt_id: uuid.UUID,
    data: SaveAnswerRequest,
    service: AttemptService = Depends(get_attempt_service),
    user: User = Depends(get_current_user),
):
    service.save_answer(attempt_id, user_id=user.id, question_id=data.question_id, selected_option=data.selected_option)
    return success_response(None, "Javob saqlandi.")


@router.post(
    "/{attempt_id}/submit",
    summary="Submit an attempt",
    description="Finalizes the attempt: scores every answered question, computes score/percentage, "
                "sets status='submitted'. Unanswered questions score zero. Cannot be called twice.",
)
def submit_attempt(
    attempt_id: uuid.UUID,
    service: AttemptService = Depends(get_attempt_service),
    user: User = Depends(get_current_user),
):
    result: SubmitResultOut = service.submit_attempt(attempt_id, user_id=user.id)
    return success_response(result, "Urinish yakunlandi.")


@router.get(
    "/{attempt_id}/result",
    summary="Get the result of a finished attempt",
    description="409 if the attempt hasn't finished yet (result data must never leak before submit/auto-finish).",
)
def get_result(
    attempt_id: uuid.UUID,
    service: AttemptService = Depends(get_attempt_service),
    user: User = Depends(get_current_user),
):
    result: SubmitResultOut = service.get_result(attempt_id, user_id=user.id)
    return success_response(result, "Natija.")
