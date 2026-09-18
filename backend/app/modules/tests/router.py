"""
HTTP layer for /api/v1/tests/*. List/get are public (browsing available
tests is part of the public catalog, same as subjects/grades/topics);
write endpoints require Admin, Super Admin, or Teacher.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.tests.dependencies import (
    get_exam_module_service,
    get_exam_section_service,
    get_question_group_service,
    get_test_service,
)
from app.modules.tests.schemas import (
    ExamModuleCreateRequest,
    ExamModuleOut,
    ExamModuleUpdateRequest,
    ExamSectionCreateRequest,
    ExamSectionOut,
    ExamSectionUpdateRequest,
    QuestionGroupCreateRequest,
    QuestionGroupOut,
    QuestionGroupUpdateRequest,
    TestCreateRequest,
    TestListParams,
    TestOut,
    TestPublishRequest,
    TestUpdateRequest,
)
from app.modules.tests.service import ExamModuleService, ExamSectionService, QuestionGroupService, TestService
from app.modules.users.models import User

router = APIRouter(prefix="/tests", tags=["Tests"])


@router.get(
    "",
    summary="List tests",
    description="Paginated, searchable, sortable, filterable (by subject_id, grade_id, topic_id, "
                "difficulty, status) list of tests. Public.",
)
def list_tests(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, description="Case-insensitive substring match on title"),
    subject_id: uuid.UUID | None = Query(default=None),
    grade_id: uuid.UUID | None = Query(default=None),
    topic_id: uuid.UUID | None = Query(default=None),
    difficulty: str | None = Query(default=None, description="easy, medium, or hard"),
    status_filter: str | None = Query(default=None, alias="status", description="draft, published, or archived"),
    sort: str = Query(default="-created_at"),
    service: TestService = Depends(get_test_service),
):
    params = TestListParams(
        page=page, per_page=per_page, search=search, subject_id=subject_id,
        grade_id=grade_id, topic_id=topic_id, difficulty=difficulty, status=status_filter, sort=sort,
    )
    items, total = service.list_tests(params)
    data = {
        "items": [TestOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Testlar ro'yxati.")


# --- Sprint 51: ExamSection Admin Configuration API ---

@router.post(
    "/exam-sections",
    status_code=status.HTTP_201_CREATED,
    summary="Create an exam section",
    description="Sprint 45's generic ExamSection — optional grouping of Questions within a Test "
                "(e.g. SAT's 'Reading and Writing' / 'Math'). 422 if test_id doesn't exist. "
                "409 if order_number is already used by a sibling section of the same test.",
)
def create_exam_section(
    data: ExamSectionCreateRequest,
    service: ExamSectionService = Depends(get_exam_section_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    section = service.create_section(data, actor_id=user.id)
    return success_response(ExamSectionOut.model_validate(section), "Bo'lim yaratildi.")


@router.get(
    "/exam-sections",
    summary="List exam sections for a test",
    description="Ordered by order_number. 422 if test_id doesn't exist.",
)
def list_exam_sections(
    test_id: uuid.UUID = Query(...),
    service: ExamSectionService = Depends(get_exam_section_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    sections = service.list_sections(test_id)
    return success_response([ExamSectionOut.model_validate(s) for s in sections], "Bo'limlar ro'yxati.")


@router.get(
    "/exam-sections/{section_id}",
    summary="Get an exam section by ID",
    description="404 if not found.",
)
def get_exam_section(
    section_id: uuid.UUID,
    service: ExamSectionService = Depends(get_exam_section_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    section = service.get_section(section_id)
    return success_response(ExamSectionOut.model_validate(section), "Bo'lim topildi.")


@router.patch(
    "/exam-sections/{section_id}",
    summary="Update an exam section",
    description="409 if the new order_number is already used by a sibling section of the same test.",
)
def update_exam_section(
    section_id: uuid.UUID,
    data: ExamSectionUpdateRequest,
    service: ExamSectionService = Depends(get_exam_section_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    section = service.update_section(section_id, data, actor_id=user.id)
    return success_response(ExamSectionOut.model_validate(section), "Bo'lim yangilandi.")


# --- Sprint 51: ExamModule Admin Configuration API ---

@router.post(
    "/exam-modules",
    status_code=status.HTTP_201_CREATED,
    summary="Create an exam module",
    description="Sprint 46's generic ExamModule — second hierarchy level under ExamSection "
                "(e.g. SAT's 'Module 1'/'Module 2' within 'Math'). routing_group/routing_variant "
                "(Sprint 48) are generic metadata only — any string value is accepted, no "
                "exam-specific validation. 404 if section_id doesn't exist. 409 if order_number "
                "is already used by a sibling module of the same section.",
)
def create_exam_module(
    data: ExamModuleCreateRequest,
    service: ExamModuleService = Depends(get_exam_module_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    module = service.create_module(data, actor_id=user.id)
    return success_response(ExamModuleOut.model_validate(module), "Modul yaratildi.")


@router.get(
    "/exam-modules",
    summary="List exam modules for a section",
    description="Ordered by order_number. 404 if section_id doesn't exist.",
)
def list_exam_modules(
    section_id: uuid.UUID = Query(...),
    service: ExamModuleService = Depends(get_exam_module_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    modules = service.list_modules(section_id)
    return success_response([ExamModuleOut.model_validate(m) for m in modules], "Modullar ro'yxati.")


@router.get(
    "/exam-modules/{module_id}",
    summary="Get an exam module by ID",
    description="404 if not found.",
)
def get_exam_module(
    module_id: uuid.UUID,
    service: ExamModuleService = Depends(get_exam_module_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    module = service.get_module(module_id)
    return success_response(ExamModuleOut.model_validate(module), "Modul topildi.")


@router.patch(
    "/exam-modules/{module_id}",
    summary="Update an exam module",
    description="409 if the new order_number is already used by a sibling module of the same section.",
)
def update_exam_module(
    module_id: uuid.UUID,
    data: ExamModuleUpdateRequest,
    service: ExamModuleService = Depends(get_exam_module_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    module = service.update_module(module_id, data, actor_id=user.id)
    return success_response(ExamModuleOut.model_validate(module), "Modul yangilandi.")


# --- Sprint 53: QuestionGroup / Stimulus Admin CRUD ---
# IMPORTANT: these static routes MUST be registered before the dynamic
# /{test_id} route below (see Sprint 51's own route-collision fix —
# FastAPI matches routes in registration order, and a dynamic
# /{test_id}: uuid.UUID path parameter would otherwise 422 on
# "question-groups" before ever reaching these handlers).

@router.post(
    "/question-groups",
    status_code=status.HTTP_201_CREATED,
    summary="Create a question group (shared stimulus)",
    description="Sprint 47's generic QuestionGroup — a shared stimulus (e.g. a reading passage or "
                "listening audio transcript) a set of Questions can be grouped under. Deliberately "
                "generic, not exam-specific. 422 if test_id doesn't exist. 404 if module_id doesn't "
                "exist. 422 if module_id doesn't belong to test_id. 409 if order_number is already "
                "used by a sibling group of the same test.",
)
def create_question_group(
    data: QuestionGroupCreateRequest,
    service: QuestionGroupService = Depends(get_question_group_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    group = service.create_group(data, actor_id=user.id)
    return success_response(QuestionGroupOut.model_validate(group), "Guruh yaratildi.")


@router.get(
    "/question-groups",
    summary="List question groups for a test",
    description="Ordered by order_number. Excludes soft-deleted groups. 422 if test_id doesn't exist.",
)
def list_question_groups(
    test_id: uuid.UUID = Query(...),
    service: QuestionGroupService = Depends(get_question_group_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    groups = service.list_groups(test_id)
    return success_response([QuestionGroupOut.model_validate(g) for g in groups], "Guruhlar ro'yxati.")


@router.get(
    "/question-groups/{group_id}",
    summary="Get a question group by ID",
    description="404 if not found or soft-deleted.",
)
def get_question_group(
    group_id: uuid.UUID,
    service: QuestionGroupService = Depends(get_question_group_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    group = service.get_group(group_id)
    return success_response(QuestionGroupOut.model_validate(group), "Guruh topildi.")


@router.patch(
    "/question-groups/{group_id}",
    summary="Update a question group",
    description="test_id can never be changed — a group cannot be moved to another test. "
                "409 if the new order_number is already used by a sibling group of the same test.",
)
def update_question_group(
    group_id: uuid.UUID,
    data: QuestionGroupUpdateRequest,
    service: QuestionGroupService = Depends(get_question_group_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    group = service.update_group(group_id, data, actor_id=user.id)
    return success_response(QuestionGroupOut.model_validate(group), "Guruh yangilandi.")


@router.delete(
    "/question-groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a question group",
    description="Sets deleted_at. Does NOT delete Questions assigned to this group — "
                "Question.group_id is set to NULL (existing ON DELETE SET NULL FK behavior).",
)
def delete_question_group(
    group_id: uuid.UUID,
    service: QuestionGroupService = Depends(get_question_group_service),
    user: User = Depends(require_roles("Admin", "Super Admin")),
):
    service.delete_group(group_id, actor_id=user.id)


@router.get(
    "/{test_id}",
    summary="Get a test by ID",
    description="Returns test metadata (not its questions — see the questions module). 404 if not found.",
)
def get_test(test_id: uuid.UUID, service: TestService = Depends(get_test_service)):
    test = service.get_test(test_id)
    return success_response(TestOut.model_validate(test), "Test topildi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a test",
    description="Creates a test in 'draft' status. Must be published separately (see POST /{id}/publish) "
                "before it becomes visible to students. 422 if subject_id/grade_id/topic_id are invalid.",
)
def create_test(
    data: TestCreateRequest,
    service: TestService = Depends(get_test_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    test = service.create_test(data, actor_id=user.id)
    return success_response(TestOut.model_validate(test), "Test yaratildi.")


@router.patch(
    "/{test_id}",
    summary="Update a test",
    description="Updates test metadata. Does not change status — use POST /{id}/publish for that.",
)
def update_test(
    test_id: uuid.UUID,
    data: TestUpdateRequest,
    service: TestService = Depends(get_test_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    test = service.update_test(test_id, data, actor_id=user.id)
    return success_response(TestOut.model_validate(test), "Test yangilandi.")


@router.post(
    "/{test_id}/publish",
    summary="Publish a test",
    description="Transitions a test from 'draft' to 'published'. Requires at least one question. "
                "409 if the current status doesn't allow this transition.",
)
def publish_test(
    test_id: uuid.UUID,
    _data: TestPublishRequest = TestPublishRequest(),
    service: TestService = Depends(get_test_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    test = service.publish_test(test_id, actor_id=user.id)
    return success_response(TestOut.model_validate(test), "Test e'lon qilindi.")


@router.delete(
    "/{test_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a test",
    description="Marks a test as deleted (deleted_at set, status='archived').",
)
def delete_test(
    test_id: uuid.UUID,
    service: TestService = Depends(get_test_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    service.delete_test(test_id, actor_id=user.id)
