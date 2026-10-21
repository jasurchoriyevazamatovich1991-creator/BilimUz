"""
Task 5 — HTTP layer for manual grading (/api/v1/grading/*).

Authorization:
- Grading (queue, submission detail, drafts, finalize, revise) and reading
  rubrics: require_permission('GRADE_SUBMISSIONS') — the project's RBAC
  dependency (permissions module). Migration 0026 grants it to Admin and
  Super Admin only; any other role (e.g. Teacher) must be granted it
  explicitly through Roles/Permissions.
- Publishing rubrics: Admin/Super Admin (require_roles), the same rule as
  every other scoring-configuration endpoint.
Students never reach these endpoints; they see their own finalized grades
only through GET /results/{id}.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.grading.constants import GRADE_SUBMISSIONS_PERMISSION
from app.modules.grading.dependencies import get_grading_service, get_rubric_service
from app.modules.grading.schemas import DraftSaveRequest, ReviewOut, ReviseRequest, RubricCreateRequest, RubricOut
from app.modules.grading.service import GradingService, RubricService
from app.modules.permissions.dependencies import require_permission
from app.modules.users.models import User

router = APIRouter(prefix="/grading", tags=["Grading"])

_grader = require_permission(GRADE_SUBMISSIONS_PERMISSION)


@router.get("/rubrics", summary="List rubric versions (graders and admins)")
def list_rubrics(
    score_component: str | None = Query(default=None),
    service: RubricService = Depends(get_rubric_service),
    _user: User = Depends(_grader),
):
    rows = service.list_rubrics(score_component)
    return success_response([RubricOut.model_validate(r).model_copy(update={"is_current": c}) for r, c in rows], "Rubrikalar.")


@router.post(
    "/rubrics", status_code=status.HTTP_201_CREATED,
    summary="Publish a new rubric version (Admin/Super Admin)",
    description="Versions are immutable; existing reviews keep the version they were graded with. "
                "is_validated=false marks every score produced with it as provisional.",
)
def create_rubric(
    data: RubricCreateRequest,
    service: RubricService = Depends(get_rubric_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    rubric = service.create_rubric(data, actor_id=user.id)
    return success_response(RubricOut.model_validate(rubric).model_copy(update={"is_current": True}), "Rubrika e'lon qilindi.")


@router.get("/submissions", summary="Grading queue (IELTS Writing/Speaking, GRE AWA)")
def list_submissions(
    status_filter: str | None = Query(default=None, alias="status"),
    test_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    service: GradingService = Depends(get_grading_service),
    _user: User = Depends(_grader),
):
    items, total = service.list_queue(status_filter, test_id, page, per_page)
    return success_response({"items": [i.model_dump(mode="json") for i in items], "total": total, "page": page, "per_page": per_page}, "Baholash navbati.")


@router.get("/submissions/{attempt_id}/{question_id}", summary="One response with its rubric and full grading history")
def get_submission(
    attempt_id: uuid.UUID, question_id: uuid.UUID,
    service: GradingService = Depends(get_grading_service),
    _user: User = Depends(_grader),
):
    return success_response(service.get_submission(attempt_id, question_id), "Javob.")


@router.put("/submissions/{attempt_id}/{question_id}/draft", summary="Create or update your draft grade")
def save_draft(
    attempt_id: uuid.UUID, question_id: uuid.UUID, data: DraftSaveRequest,
    service: GradingService = Depends(get_grading_service),
    user: User = Depends(_grader),
):
    review = service.save_draft(attempt_id, question_id, data, grader_id=user.id)
    return success_response(ReviewOut.model_validate(review), "Qoralama saqlandi.")


@router.post("/submissions/{attempt_id}/{question_id}/finalize", summary="Finalize your draft (releases it to the student)")
def finalize(
    attempt_id: uuid.UUID, question_id: uuid.UUID,
    service: GradingService = Depends(get_grading_service),
    user: User = Depends(_grader),
):
    review = service.finalize(attempt_id, question_id, grader_id=user.id)
    return success_response(ReviewOut.model_validate(review), "Baho yakunlandi.")


@router.post(
    "/submissions/{attempt_id}/{question_id}/revise", status_code=status.HTTP_201_CREATED,
    summary="Open an audited correction of a finalized grade",
    description="Creates a new draft (revision n+1) with the same rubric version; the current grade stays "
                "in force until the revision is finalized, then becomes 'superseded' (kept in history).",
)
def revise(
    attempt_id: uuid.UUID, question_id: uuid.UUID, data: ReviseRequest,
    service: GradingService = Depends(get_grading_service),
    user: User = Depends(_grader),
):
    review = service.revise(attempt_id, question_id, data.reason, grader_id=user.id)
    return success_response(ReviewOut.model_validate(review), "Tuzatish qoralamasi ochildi.")
