"""Data-access layer. Only SQLAlchemy here — no business rules."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.tests.models import Test, ExamModule, ExamSection
from app.modules.tests.schemas import TestListParams


class TestRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, test_id: uuid.UUID) -> Test | None:
        stmt = select(Test).where(Test.id == test_id, Test.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: TestListParams) -> tuple[list[Test], int]:
        stmt = select(Test).where(Test.deleted_at.is_(None))
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = self._apply_sort(stmt, params.sort)
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: TestListParams):
        if params.search:
            stmt = stmt.where(Test.title.ilike(f"%{params.search}%"))
        if params.subject_id:
            stmt = stmt.where(Test.subject_id == params.subject_id)
        if params.grade_id:
            stmt = stmt.where(Test.grade_id == params.grade_id)
        if params.topic_id:
            stmt = stmt.where(Test.topic_id == params.topic_id)
        if params.difficulty:
            stmt = stmt.where(Test.difficulty == params.difficulty)
        if params.status:
            stmt = stmt.where(Test.status == params.status)
        return stmt

    def _apply_sort(self, stmt, sort: str):
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = getattr(Test, field_name, Test.created_at)
        return stmt.order_by(column.desc() if descending else column.asc())

    def create(self, test: Test) -> Test:
        self.db.add(test)
        self.db.flush()
        return test

    def update(self, test: Test, data: dict) -> Test:
        for field, value in data.items():
            setattr(test, field, value)
        self.db.flush()
        return test

    def increment_question_count(self, test_id: uuid.UUID, delta: int) -> None:
        """Called by the `questions` module (read+write reuse of this
        repository, not duplicated logic) whenever a question is added
        or removed, so `tests.question_count` never drifts from reality."""
        test = self.get_by_id(test_id)
        if test is not None:
            test.question_count = max(0, test.question_count + delta)
            self.db.flush()

    def soft_delete(self, test: Test) -> None:
        test.deleted_at = datetime.now(timezone.utc)
        test.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()


class ExamModuleRepository:
    """Sprint 50 — new, minimal repository for module execution. Reads
    ExamModule/ExamSection only; ExamSection/ExamModule creation is out
    of this sprint's scope (they're already created by whoever
    configures the exam — Sprint 45/46's own scope)."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, module_id: uuid.UUID) -> ExamModule | None:
        return self.db.get(ExamModule, module_id)

    def list_for_test(self, test_id: uuid.UUID) -> list[ExamModule]:
        """All modules across all of a Test's sections, ordered by
        (section.order_number, module.order_number) — the deterministic
        execution order Sprint 45/46's own UNIQUE(section_id/test_id,
        order_number) constraints already guarantee is well-defined."""
        stmt = (
            select(ExamModule)
            .join(ExamSection, ExamModule.section_id == ExamSection.id)
            .where(ExamSection.test_id == test_id, ExamModule.deleted_at.is_(None), ExamSection.deleted_at.is_(None))
            .order_by(ExamSection.order_number, ExamModule.order_number)
        )
        return list(self.db.scalars(stmt).all())

    def has_modules(self, test_id: uuid.UUID) -> bool:
        """Backward-compatibility gate: a Test with zero ExamModule rows
        (every existing Physics/generic test) must take the legacy,
        unmodified execution path — see AttemptService.start_attempt()."""
        stmt = (
            select(ExamModule.id)
            .join(ExamSection, ExamModule.section_id == ExamSection.id)
            .where(ExamSection.test_id == test_id, ExamModule.deleted_at.is_(None), ExamSection.deleted_at.is_(None))
            .limit(1)
        )
        return self.db.scalars(stmt).first() is not None

    def list_for_section(self, section_id: uuid.UUID) -> list[ExamModule]:
        stmt = select(ExamModule).where(ExamModule.section_id == section_id, ExamModule.deleted_at.is_(None)).order_by(ExamModule.order_number)
        return list(self.db.scalars(stmt).all())

    def create(self, module: ExamModule) -> ExamModule:
        self.db.add(module)
        self.db.flush()
        return module

    def update(self, module: ExamModule, data: dict) -> ExamModule:
        for field, value in data.items():
            setattr(module, field, value)
        self.db.flush()
        return module

    def commit(self) -> None:
        self.db.commit()


class ExamSectionRepository:
    """Sprint 51 — new, for the Admin Configuration API. Mirrors
    ExamModuleRepository's own shape exactly."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, section_id: uuid.UUID) -> ExamSection | None:
        return self.db.get(ExamSection, section_id)

    def list_for_test(self, test_id: uuid.UUID) -> list[ExamSection]:
        stmt = select(ExamSection).where(ExamSection.test_id == test_id, ExamSection.deleted_at.is_(None)).order_by(ExamSection.order_number)
        return list(self.db.scalars(stmt).all())

    def create(self, section: ExamSection) -> ExamSection:
        self.db.add(section)
        self.db.flush()
        return section

    def update(self, section: ExamSection, data: dict) -> ExamSection:
        for field, value in data.items():
            setattr(section, field, value)
        self.db.flush()
        return section

    def commit(self) -> None:
        self.db.commit()
