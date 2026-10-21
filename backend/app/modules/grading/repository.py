"""Task 5 — data access for rubrics, reviews and the grading queue.
Cross-module reads (attempts, questions, tests) are read-only."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.attempts.models import TestAttempt
from app.modules.grading.constants import (
    FINISHED_ATTEMPT_STATUSES,
    REVIEW_STATUS_DRAFT,
    REVIEW_STATUS_FINALIZED,
    REVIEW_STATUS_SUPERSEDED,
)
from app.modules.grading.models import GradingRubric, ManualReview
from app.modules.questions.models import Question
from app.modules.results.scaled_scoring import MANUAL_COMPONENTS
from app.modules.tests.models import ExamSection, Test


class RubricRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, rubric_id: uuid.UUID) -> GradingRubric | None:
        return self.db.scalars(select(GradingRubric).where(GradingRubric.id == rubric_id, GradingRubric.deleted_at.is_(None))).first()

    def list_by_ids(self, ids) -> list[GradingRubric]:
        ids = list(ids)
        if not ids:
            return []
        return list(self.db.scalars(select(GradingRubric).where(GradingRubric.id.in_(ids))).all())

    def list(self, component: str | None = None) -> list[GradingRubric]:
        stmt = select(GradingRubric).where(GradingRubric.deleted_at.is_(None))
        if component:
            stmt = stmt.where(GradingRubric.score_component == component)
        return list(self.db.scalars(stmt.order_by(GradingRubric.score_component, GradingRubric.version.desc())).all())

    def get_current(self, component: str) -> GradingRubric | None:
        stmt = (
            select(GradingRubric)
            .where(GradingRubric.score_component == component, GradingRubric.deleted_at.is_(None))
            .order_by(GradingRubric.version.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def max_version(self, component: str) -> int:
        return self.db.execute(select(func.max(GradingRubric.version)).where(GradingRubric.score_component == component)).scalar() or 0

    def create(self, rubric: GradingRubric) -> GradingRubric:
        self.db.add(rubric)
        self.db.flush()
        return rubric

    def commit(self) -> None:
        self.db.commit()


class ReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_item(self, attempt_id: uuid.UUID, question_id: uuid.UUID) -> list[ManualReview]:
        stmt = (
            select(ManualReview)
            .where(ManualReview.attempt_id == attempt_id, ManualReview.question_id == question_id, ManualReview.deleted_at.is_(None))
            .order_by(ManualReview.revision_number, ManualReview.created_at)
        )
        return list(self.db.scalars(stmt).all())

    def _one(self, attempt_id, question_id, status: str, lock: bool) -> ManualReview | None:
        stmt = select(ManualReview).where(
            ManualReview.attempt_id == attempt_id, ManualReview.question_id == question_id,
            ManualReview.status == status, ManualReview.deleted_at.is_(None),
        )
        if lock:
            stmt = stmt.with_for_update()
        return self.db.scalars(stmt).first()

    def get_draft(self, attempt_id, question_id, lock: bool = False) -> ManualReview | None:
        return self._one(attempt_id, question_id, REVIEW_STATUS_DRAFT, lock)

    def get_finalized(self, attempt_id, question_id, lock: bool = False) -> ManualReview | None:
        return self._one(attempt_id, question_id, REVIEW_STATUS_FINALIZED, lock)

    def list_finalized_for_attempt(self, attempt_id: uuid.UUID) -> list[ManualReview]:
        stmt = select(ManualReview).where(
            ManualReview.attempt_id == attempt_id, ManualReview.status == REVIEW_STATUS_FINALIZED, ManualReview.deleted_at.is_(None),
        )
        return list(self.db.scalars(stmt).all())

    def list_open_for_attempts(self, attempt_ids: list[uuid.UUID]) -> list[ManualReview]:
        """Drafts and finalized (not superseded) reviews — for queue status."""
        if not attempt_ids:
            return []
        stmt = select(ManualReview).where(
            ManualReview.attempt_id.in_(attempt_ids), ManualReview.status != REVIEW_STATUS_SUPERSEDED,
            ManualReview.deleted_at.is_(None),
        )
        return list(self.db.scalars(stmt).all())

    def create(self, review: ManualReview) -> ManualReview:
        self.db.add(review)
        self.db.flush()
        return review

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()


class GradingQueueRepository:
    """Read-only queries to find manually graded items."""

    def __init__(self, db: Session):
        self.db = db

    def manual_questions(self, test_id: uuid.UUID | None = None) -> list[tuple[Question, ExamSection, Test]]:
        stmt = (
            select(Question, ExamSection, Test)
            .join(ExamSection, ExamSection.id == Question.section_id)
            .join(Test, Test.id == ExamSection.test_id)
            .where(
                Question.deleted_at.is_(None), ExamSection.deleted_at.is_(None), Test.deleted_at.is_(None),
                Question.test_id == Test.id, Test.scoring_profile.is_not(None),
                ExamSection.score_component.in_(MANUAL_COMPONENTS),
            )
        )
        if test_id is not None:
            stmt = stmt.where(Test.id == test_id)
        return list(self.db.execute(stmt).all())

    def finished_attempts(self, test_ids) -> list[TestAttempt]:
        test_ids = list(test_ids)
        if not test_ids:
            return []
        stmt = (
            select(TestAttempt)
            .where(TestAttempt.test_id.in_(test_ids), TestAttempt.status.in_(FINISHED_ATTEMPT_STATUSES))
            .order_by(TestAttempt.finish_time.desc().nulls_last(), TestAttempt.id)
        )
        return list(self.db.scalars(stmt).all())
