"""
HTTP layer for /api/v1/progress/*.

Only GET /progress/me lives here. The completion action itself
(POST /lessons/{id}/complete) lives on the LESSONS router — completing
IS an action on a lesson resource (matches REST convention), even
though its service logic lives in this module. This keeps the route
surface intuitive (a student completes a LESSON, not a "progress")
while the underlying LessonProgress persistence stays in its own
module, same separation notifications/certificates already use.
"""
from fastapi import APIRouter, Depends

from app.core.schemas import success_response
from app.modules.auth.dependencies import get_current_user
from app.modules.progress.dependencies import get_progress_service
from app.modules.progress.service import ProgressService
from app.modules.users.models import User

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.get(
    "/me",
    summary="Get my lesson completion progress",
    description="Aggregate counts (completed/total/percentage) plus the list of completed lesson IDs, "
                "for the authenticated student only — user_id is always derived from the JWT, never a "
                "request parameter, so a student can never read another student's progress.",
)
def get_my_progress(
    service: ProgressService = Depends(get_progress_service),
    user: User = Depends(get_current_user),
):
    result = service.get_my_progress(user.id)
    return success_response(result, "Progress olingan.")
