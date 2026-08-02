"""
HTTP layer for /api/v1/results/*. Per the approved Sprint 7 scope, this
router intentionally has NO public/authenticated ranking-read endpoint
(no GET /results/ranking) — only the calculation engine's trigger
(POST /results/ranking/recompute, Admin-only). Reading a leaderboard is
future work.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.results.dependencies import get_ranking_service, get_result_service
from app.modules.results.schemas import (
    CreateResultRequest,
    RankingRecomputeRequest,
    RankingRecomputeResponse,
    ResultListParams,
    ResultOut,
)
from app.modules.results.service import RankingService, ResultService
from app.modules.users.models import User

router = APIRouter(prefix="/results", tags=["Results"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a result from a finished attempt",
    description="Idempotent on attempt_id — calling twice returns the same Result. "
                "409 if the attempt hasn't finished yet (submitted/auto_finished only).",
)
def create_result(
    data: CreateResultRequest,
    service: ResultService = Depends(get_result_service),
    user: User = Depends(get_current_user),
):
    result = service.create_result(data.attempt_id, user_id=user.id)
    return success_response(ResultOut.model_validate(result), "Natija yaratildi.")


@router.get(
    "/me",
    summary="List my results",
    description="Paginated list of the current user's own results, optionally filtered by test_id.",
)
def list_my_results(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    test_id: uuid.UUID | None = Query(default=None),
    sort: str = Query(default="-created_at"),
    service: ResultService = Depends(get_result_service),
    user: User = Depends(get_current_user),
):
    params = ResultListParams(page=page, per_page=per_page, test_id=test_id, sort=sort)
    items, total = service.list_my_results(user.id, params)
    data = {
        "items": [ResultOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Mening natijalarim.")


@router.get(
    "/{result_id}",
    summary="Get a result by ID",
    description="404 if not found or not yours.",
)
def get_result(
    result_id: uuid.UUID,
    service: ResultService = Depends(get_result_service),
    user: User = Depends(get_current_user),
):
    result = service.get_result(result_id, user_id=user.id)
    return success_response(ResultOut.model_validate(result), "Natija topildi.")


@router.post(
    "/ranking/recompute",
    summary="Recompute the ranking engine for a subject + period",
    description="Calculation engine only — no read endpoint exists yet for the computed ranking "
                "(deferred to a future sprint, see docs/Sprint7_..._Architecture.md). Tie-break order: "
                "higher score, then shorter completion time, then earlier completion timestamp.",
)
def recompute_ranking(
    data: RankingRecomputeRequest,
    service: RankingService = Depends(get_ranking_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    ranked_count = service.recompute(data.subject_id, data.period)
    response = RankingRecomputeResponse(subject_id=data.subject_id, period=data.period, ranked_count=ranked_count)
    return success_response(response, "Reyting qayta hisoblandi.")
