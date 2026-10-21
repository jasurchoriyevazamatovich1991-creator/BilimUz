"""
Task 5 — manual grading workflow for IELTS Writing, IELTS Speaking and
GRE Analytical Writing.

Lifecycle of one item (attempt, question):
  pending --save_draft--> draft --finalize--> finalized
  finalized --revise(reason)--> draft (revision n+1, copies scores)
                               --finalize--> finalized; previous -> superseded
Every row is kept; nothing is overwritten after finalization. Finalizing
refreshes the attempt's Result (manual sections + overall) when it exists.

Identity and state always come from the server: grader_id is the caller,
rubric_id is the current rubric (or, for a revision, the revised review's
rubric), status/revision fields are set here only.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.core.audit import log_action
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.attempts.scoring import is_auto_gradable
from app.modules.grading import rules
from app.modules.grading.constants import (
    FINISHED_ATTEMPT_STATUSES,
    QUEUE_STATUS_DRAFT,
    QUEUE_STATUS_FINALIZED,
    QUEUE_STATUS_PENDING,
    QUEUE_STATUSES,
    REVIEW_STATUS_DRAFT,
    REVIEW_STATUS_FINALIZED,
    REVIEW_STATUS_SUPERSEDED,
)
from app.modules.grading.exceptions import (
    GradingItemNotFoundException,
    InvalidCriterionScoresException,
    InvalidRubricException,
    RubricNotConfiguredException,
    ReviewStateConflictException,
)
from app.modules.grading.models import GradingRubric, ManualReview
from app.modules.grading.repository import GradingQueueRepository, ReviewRepository, RubricRepository
from app.modules.grading.schemas import (
    DraftSaveRequest,
    QueueItemOut,
    ReviewOut,
    RubricCreateRequest,
    RubricOut,
    SubmissionDetailOut,
)
from app.modules.questions.repository import QuestionRepository
from app.modules.results.scaled_scoring import COMPONENTS, MANUAL_COMPONENTS
from app.modules.results.service import ResultService
from app.modules.tests.repository import ExamSectionRepository, TestRepository


class RubricService:
    def __init__(self, repo: RubricRepository):
        self.repo = repo

    def list_rubrics(self, component: str | None) -> list[tuple[GradingRubric, bool]]:
        rubrics = self.repo.list(component)
        newest: dict = {}
        for r in rubrics:
            if r.score_component not in newest or r.version > newest[r.score_component].version:
                newest[r.score_component] = r
        current_ids = {r.id for r in newest.values()}
        return [(r, r.id in current_ids) for r in rubrics]

    def create_rubric(self, data: RubricCreateRequest, actor_id: uuid.UUID) -> GradingRubric:
        try:
            criteria = rules.validate_rubric(
                data.score_component, [c.model_dump() for c in data.criteria], data.rounding,
            )
        except rules.InvalidRubric as exc:
            raise InvalidRubricException(str(exc))
        rubric = GradingRubric(
            score_component=data.score_component, version=self.repo.max_version(data.score_component) + 1,
            name=data.name.strip(), criteria=criteria, rounding=data.rounding, instructions=data.instructions,
            is_validated=data.is_validated, created_by=actor_id,
        )
        self.repo.create(rubric)
        log_action(self.repo.db, action="grading_rubric.published", user_id=actor_id, entity_type="grading_rubric",
                   entity_id=rubric.id, metadata={"component": rubric.score_component, "version": rubric.version})
        self.repo.commit()
        return rubric


class GradingService:
    def __init__(
        self,
        rubric_repo: RubricRepository,
        review_repo: ReviewRepository,
        queue_repo: GradingQueueRepository,
        attempt_repo: AttemptRepository,
        answer_repo: AnswerRepository,
        question_repo: QuestionRepository,
        section_repo: ExamSectionRepository,
        test_repo: TestRepository,
        module_execution: ModuleExecutionService | None,
        result_service: ResultService,
    ):
        self.rubric_repo = rubric_repo
        self.review_repo = review_repo
        self.queue_repo = queue_repo
        self.attempt_repo = attempt_repo
        self.answer_repo = answer_repo
        self.question_repo = question_repo
        self.section_repo = section_repo
        self.test_repo = test_repo
        self.module_execution = module_execution
        self.result_service = result_service

    # --- item resolution ---------------------------------------------------

    def _delivered_ids(self, attempt) -> set:
        if self.module_execution is not None:
            ids = self.module_execution.get_effective_question_ids(attempt.id)
            if ids is not None:
                return set(ids)
        return set(attempt.question_order or [])

    def _resolve_item(self, attempt_id: uuid.UUID, question_id: uuid.UUID):
        """(attempt, question, section, test) for a gradable item, else 404:
        finished attempt, question delivered to it, in an active section of
        a manual component matching the test's scoring profile, and not an
        auto-graded question type."""
        attempt = self.attempt_repo.get_by_id(attempt_id)
        question = self.question_repo.get_by_id(question_id)
        if attempt is None or question is None or attempt.status not in FINISHED_ATTEMPT_STATUSES:
            raise GradingItemNotFoundException("Baholanadigan javob topilmadi")
        if question.test_id != attempt.test_id or question.section_id is None or is_auto_gradable(question):
            raise GradingItemNotFoundException("Baholanadigan javob topilmadi")
        section = self.section_repo.get_by_id(question.section_id)
        test = self.test_repo.get_by_id(attempt.test_id)
        if section is None or section.deleted_at is not None or test is None:
            raise GradingItemNotFoundException("Baholanadigan javob topilmadi")
        spec = COMPONENTS.get(section.score_component) if section.score_component else None
        if section.score_component not in MANUAL_COMPONENTS or spec is None or spec.profile != test.scoring_profile:
            raise GradingItemNotFoundException("Baholanadigan javob topilmadi")
        if question.id not in self._delivered_ids(attempt):
            raise GradingItemNotFoundException("Baholanadigan javob topilmadi")
        return attempt, question, section, test

    # --- read --------------------------------------------------------------

    def _review_out(self, review: ManualReview, versions: dict) -> ReviewOut:
        out = ReviewOut.model_validate(review)
        return out.model_copy(update={"rubric_version": versions.get(review.rubric_id)})

    @staticmethod
    def _rubric_out(rubric: GradingRubric, is_current: bool) -> RubricOut:
        return RubricOut.model_validate(rubric).model_copy(update={"is_current": is_current})

    @staticmethod
    def _queue_status(open_reviews: list[ManualReview]) -> str:
        statuses = {r.status for r in open_reviews}
        if REVIEW_STATUS_FINALIZED in statuses:
            return QUEUE_STATUS_FINALIZED
        if REVIEW_STATUS_DRAFT in statuses:
            return QUEUE_STATUS_DRAFT
        return QUEUE_STATUS_PENDING

    def list_queue(self, status: str | None, test_id: uuid.UUID | None, page: int, per_page: int) -> tuple[list[QueueItemOut], int]:
        if status is not None and status not in QUEUE_STATUSES:
            raise GradingItemNotFoundException("Noma'lum holat filtri")
        rows = [(q, s, t) for q, s, t in self.queue_repo.manual_questions(test_id)
                if not is_auto_gradable(q) and COMPONENTS[s.score_component].profile == t.scoring_profile]
        by_test: dict = {}
        for q, s, t in rows:
            by_test.setdefault(t.id, []).append((q, s, t))
        attempts = self.queue_repo.finished_attempts(by_test.keys())
        open_reviews: dict = {}
        for r in self.review_repo.list_open_for_attempts([a.id for a in attempts]):
            open_reviews.setdefault((r.attempt_id, r.question_id), []).append(r)

        items = []
        for attempt in attempts:
            delivered = self._delivered_ids(attempt)
            for q, s, t in by_test.get(attempt.test_id, []):
                if q.id not in delivered:
                    continue
                reviews = open_reviews.get((attempt.id, q.id), [])
                item_status = self._queue_status(reviews)
                if status is not None and item_status != status:
                    continue
                finalized = next((r for r in reviews if r.status == REVIEW_STATUS_FINALIZED), None)
                items.append(QueueItemOut(
                    attempt_id=attempt.id, question_id=q.id, test_id=t.id, test_title=t.title,
                    section_name=s.name, score_component=s.score_component, status=item_status,
                    finished_at=attempt.finish_time,
                    reported_score=float(finalized.reported_score) if finalized is not None else None,
                ))
        total = len(items)
        start = (page - 1) * per_page
        return items[start:start + per_page], total

    def get_submission(self, attempt_id: uuid.UUID, question_id: uuid.UUID) -> SubmissionDetailOut:
        attempt, question, section, test = self._resolve_item(attempt_id, question_id)
        reviews = self.review_repo.list_for_item(attempt_id, question_id)
        rubric_ids = {r.rubric_id for r in reviews}
        current = self.rubric_repo.get_current(section.score_component)
        if current is not None:
            rubric_ids.add(current.id)
        rubrics = {r.id: r for r in self.rubric_repo.list_by_ids(rubric_ids)}
        versions = {rid: r.version for rid, r in rubrics.items()}
        # The rubric a grader works with: the open draft's, else the
        # current finalized review's, else the component's current one.
        open_review = next((r for r in reviews if r.status == REVIEW_STATUS_DRAFT), None) or \
            next((r for r in reviews if r.status == REVIEW_STATUS_FINALIZED), None)
        working = rubrics.get(open_review.rubric_id) if open_review is not None else current
        answer = next((a for a in self.answer_repo.list_for_attempt(attempt_id) if a.question_id == question_id), None)
        return SubmissionDetailOut(
            attempt_id=attempt_id, question_id=question_id, test_title=test.title, section_name=section.name,
            score_component=section.score_component, question_text=question.question_text,
            question_type=question.question_type, response_text=answer.text_answer if answer else None,
            has_audio=answer is not None and answer.audio_upload_id is not None,
            status=self._queue_status([r for r in reviews if r.status != REVIEW_STATUS_SUPERSEDED]),
            rubric=self._rubric_out(working, current is not None and working.id == current.id) if working is not None else None,
            reviews=[self._review_out(r, versions) for r in reviews],
        )

    # --- write -------------------------------------------------------------

    def _validated_scores(self, rubric: GradingRubric, scores: dict, require_all: bool) -> dict:
        try:
            return rules.validate_scores(rubric.criteria, scores, require_all)
        except rules.InvalidCriterionScores as exc:
            raise InvalidCriterionScoresException(str(exc))

    def save_draft(self, attempt_id: uuid.UUID, question_id: uuid.UUID, data: DraftSaveRequest, grader_id: uuid.UUID) -> ManualReview:
        _, question, section, _ = self._resolve_item(attempt_id, question_id)
        draft = self.review_repo.get_draft(attempt_id, question_id, lock=True)
        if draft is None:
            if self.review_repo.get_finalized(attempt_id, question_id) is not None:
                raise ReviewStateConflictException("Bu javob allaqachon yakuniy baholangan — tuzatish uchun 'revise' dan foydalaning")
            rubric = self.rubric_repo.get_current(section.score_component)
            if rubric is None:
                raise RubricNotConfiguredException("Bu komponent uchun rubrika hali sozlanmagan")
            scores = self._validated_scores(rubric, data.criterion_scores, require_all=False)
            draft = self.review_repo.create(ManualReview(
                attempt_id=attempt_id, question_id=question.id, section_id=section.id, rubric_id=rubric.id,
                grader_id=grader_id, status=REVIEW_STATUS_DRAFT, criterion_scores=scores,
                feedback=data.feedback, internal_notes=data.internal_notes, revision_number=1,
            ))
        else:
            if draft.grader_id != grader_id:
                raise ReviewStateConflictException("Bu qoralama boshqa baholovchiga tegishli")
            rubric = self.rubric_repo.get_by_id(draft.rubric_id)
            draft.criterion_scores = self._validated_scores(rubric, data.criterion_scores, require_all=False)
            draft.feedback = data.feedback
            draft.internal_notes = data.internal_notes
            self.review_repo.flush()
        log_action(self.review_repo.db, action="manual_review.draft_saved", user_id=grader_id, entity_type="manual_review", entity_id=draft.id)
        self.review_repo.commit()
        return draft

    def finalize(self, attempt_id: uuid.UUID, question_id: uuid.UUID, grader_id: uuid.UUID) -> ManualReview:
        _, _, section, _ = self._resolve_item(attempt_id, question_id)
        draft = self.review_repo.get_draft(attempt_id, question_id, lock=True)
        if draft is None:
            raise ReviewStateConflictException("Yakunlash uchun avval qoralama saqlang")
        if draft.grader_id != grader_id:
            raise ReviewStateConflictException("Bu qoralama boshqa baholovchiga tegishli")
        rubric = self.rubric_repo.get_by_id(draft.rubric_id)
        scores = self._validated_scores(rubric, draft.criterion_scores, require_all=True)
        total, reported = rules.compute_answer_score(section.score_component, rubric.criteria, rubric.rounding, scores)

        previous = self.review_repo.get_finalized(attempt_id, question_id, lock=True)
        if previous is not None:
            # Free the "one finalized" slot BEFORE promoting the revision.
            previous.status = REVIEW_STATUS_SUPERSEDED
            self.review_repo.flush()
        draft.criterion_scores = scores
        draft.criterion_total = Decimal(rules.decimal_text(total))
        draft.reported_score = Decimal(rules.decimal_text(reported))
        draft.is_provisional = not rubric.is_validated
        draft.status = REVIEW_STATUS_FINALIZED
        draft.finalized_at = datetime.now(timezone.utc)
        self.review_repo.flush()
        self.result_service.refresh_manual_scores(attempt_id)
        log_action(self.review_repo.db, action="manual_review.finalized", user_id=grader_id, entity_type="manual_review",
                   entity_id=draft.id, metadata={"revision_number": draft.revision_number,
                                                 "supersedes_id": str(draft.supersedes_id) if draft.supersedes_id else None,
                                                 "reported_score": str(draft.reported_score)})
        self.review_repo.commit()
        return draft

    def revise(self, attempt_id: uuid.UUID, question_id: uuid.UUID, reason: str, grader_id: uuid.UUID) -> ManualReview:
        """Opens an audited correction of a finalized grade as a new draft.
        Uses the SAME rubric version as the grade being corrected, so a
        later rubric change never silently re-scores it."""
        self._resolve_item(attempt_id, question_id)
        finalized = self.review_repo.get_finalized(attempt_id, question_id, lock=True)
        if finalized is None:
            raise ReviewStateConflictException("Tuzatish uchun yakuniy baho mavjud emas")
        if self.review_repo.get_draft(attempt_id, question_id) is not None:
            raise ReviewStateConflictException("Bu javob uchun ochiq qoralama allaqachon bor")
        revision = self.review_repo.create(ManualReview(
            attempt_id=attempt_id, question_id=question_id, section_id=finalized.section_id, rubric_id=finalized.rubric_id,
            grader_id=grader_id, status=REVIEW_STATUS_DRAFT, criterion_scores=dict(finalized.criterion_scores),
            feedback=finalized.feedback, internal_notes=finalized.internal_notes,
            revision_number=finalized.revision_number + 1, supersedes_id=finalized.id, revision_reason=reason.strip(),
        ))
        log_action(self.review_repo.db, action="manual_review.revision_opened", user_id=grader_id, entity_type="manual_review",
                   entity_id=revision.id, metadata={"supersedes_id": str(finalized.id), "reason": reason.strip()[:200]})
        self.review_repo.commit()
        return revision


    def open_response_audio(self, attempt_id: uuid.UUID, question_id: uuid.UUID, attempt_service):
        """Task 6 — the student's recorded Speaking response for a gradable
        item. Same item checks as every other grading endpoint (finished
        attempt, delivered manual question), then the attempts module's
        own private-storage reader."""
        self._resolve_item(attempt_id, question_id)
        return attempt_service.open_answer_audio(attempt_id, question_id)
