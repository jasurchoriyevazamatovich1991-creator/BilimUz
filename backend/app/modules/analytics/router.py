"""
HTTP layer for /api/v1/analytics/*. Own-data endpoints require only
authentication; other-user and recompute endpoints require Admin/Super
Admin. No endpoint here is public — analytics is personal/administrative
data, unlike tests/subjects' public browsing.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.schemas import success_response
from app.modules.analytics.dependencies import get_analytics_service
from app.modules.analytics.schemas import (
    DailyStatOut,
    MonthlyStatOut,
    RecomputeDailyRequest,
    RecomputeMonthlyRequest,
    RecomputeResponse,
)
from app.modules.analytics.service import AnalyticsService
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.users.models import User

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/me/daily",
    summary="My daily activity",
    description="Daily test-taking activity for the current user, optionally scoped to one subject. "
                "Date range capped at 365 days.",
)
def get_my_daily(
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    subject_id: uuid.UUID | None = Query(default=None),
    service: AnalyticsService = Depends(get_analytics_service),
    user: User = Depends(get_current_user),
):
    rows = service.get_my_daily(user.id, date_from, date_to, subject_id)
    return success_response([DailyStatOut.model_validate(r) for r in rows], "Kunlik faollik.")


@router.get(
    "/me/monthly",
    summary="My monthly rollup",
    description="Monthly aggregated statistics for the current user, built from daily_statistics via recompute.",
)
def get_my_monthly(
    service: AnalyticsService = Depends(get_analytics_service),
    user: User = Depends(get_current_user),
):
    rows = service.get_my_monthly(user.id)
    return success_response([MonthlyStatOut.model_validate(r) for r in rows], "Oylik statistika.")


@router.get(
    "/users/{user_id}/daily",
    summary="A specific user's daily activity",
    description="Admin/Super Admin only — same shape as /me/daily but for any user.",
)
def get_user_daily(
    user_id: uuid.UUID,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    subject_id: uuid.UUID | None = Query(default=None),
    service: AnalyticsService = Depends(get_analytics_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    rows = service.get_my_daily(user_id, date_from, date_to, subject_id)
    return success_response([DailyStatOut.model_validate(r) for r in rows], "Foydalanuvchi kunlik faolligi.")


@router.post(
    "/recompute/daily",
    summary="Rebuild daily_statistics for a date range from results",
    description="Reads `results` (and each result's attempt answers) directly — independent of the "
                "results module, no data is pushed to analytics. Delete-and-rebuild for the window, "
                "safe to re-run.",
)
def recompute_daily(
    data: RecomputeDailyRequest,
    service: AnalyticsService = Depends(get_analytics_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    count = service.recompute_daily(data.date_from, data.date_to)
    return success_response(RecomputeResponse(buckets_updated=count), "Kunlik statistika qayta hisoblandi.")


@router.post(
    "/recompute/monthly",
    summary="Rebuild monthly_statistics for a month from daily_statistics",
    description="Aggregates the module's own daily_statistics rows — does not re-read `results`.",
)
def recompute_monthly(
    data: RecomputeMonthlyRequest,
    service: AnalyticsService = Depends(get_analytics_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    count = service.recompute_monthly(data.month, data.year)
    return success_response(RecomputeResponse(buckets_updated=count), "Oylik statistika qayta hisoblandi.")
