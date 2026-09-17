"""
Data-access layer for Question, QuestionOption, QuestionMedia — three
repositories in one file, same cohesive-module reasoning as
permissions/repository.py's PermissionRepository + RolePermissionRepository.
"""
from __future__ import annotations  # Sprint 39 Phase 3C fix — see note below

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.questions.models import Question, QuestionMedia, QuestionOption
from app.modules.questions.schemas import QuestionListParams

# Sprint 39 Phase 3C bug fix: QuestionRepository defines a method named
# `list` (below), which — without `from __future__ import annotations`
# above — shadows the builtin `list` inside this class's own namespace
# for every method defined AFTER it. Any `-> list[X]` return annotation
# appearing later in the same class body (list_all_for_test,
# list_for_question) then tried to subscript that METHOD object instead
# of the builtin type, raising `TypeError: 'function' object is not
# subscriptable` at import time — this broke the entire
# attempts -> questions import chain, blocking backend startup.
# `from __future__ import annotations` (PEP 563) makes every annotation
# in this file lazy (stored as a string, never evaluated at class-body
# execution time), which eliminates the collision without renaming
# `list()`, without changing any call site
# (questions/service.py's `self.repo.list(params)`,
# attempts/service.py's `self.question_repo.list_all_for_test(...)`),
# and without touching the database schema.


class QuestionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, question_id: uuid.UUID) -> Question | None:
        stmt = (
            select(Question)
            .where(Question.id == question_id, Question.deleted_at.is_(None))
            .options(selectinload(Question.options), selectinload(Question.media))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_ids(self, question_ids: list[uuid.UUID]) -> list[Question]:
        """Sprint 37 — bulk fetch for Result Analysis question review,
        avoiding one query per question. Same selectinload(options)
        pattern as get_by_id() above, so each returned Question already
        has its options loaded — no separate OptionRepository call
        needed for this feature."""
        if not question_ids:
            return []
        stmt = (
            select(Question)
            .where(Question.id.in_(question_ids), Question.deleted_at.is_(None))
            .options(selectinload(Question.options))
        )
        return list(self.db.execute(stmt).scalars().all())

    def list(self, params: QuestionListParams) -> tuple[list[Question], int]:
        stmt = select(Question).where(Question.deleted_at.is_(None))
        if params.test_id:
            stmt = stmt.where(Question.test_id == params.test_id)
        if params.difficulty:
            stmt = stmt.where(Question.difficulty == params.difficulty)
        if params.status:
            stmt = stmt.where(Question.status == params.status)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        descending = params.sort.startswith("-")
        field_name = params.sort.lstrip("-")
        column = getattr(Question, field_name, Question.created_at)
        stmt = stmt.order_by(column.desc() if descending else column.asc())
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)
        stmt = stmt.options(selectinload(Question.options), selectinload(Question.media))

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def count_for_test(self, test_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Question).where(
            Question.test_id == test_id, Question.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one()

    def list_all_for_test(self, test_id: uuid.UUID) -> list[Question]:
        """Unpaginated — used by the `attempts` module to snapshot every
        question for randomization at attempt-start. Distinct from list()
        (paginated, for the content-authoring browse view) on purpose:
        an attempt must never silently miss a question because it fell
        on 'page 2'."""
        stmt = select(Question).where(Question.test_id == test_id, Question.deleted_at.is_(None))
        return list(self.db.scalars(stmt).all())

    def list_by_module(self, module_id: uuid.UUID) -> list[Question]:
        """Sprint 50 — module-scoped equivalent of list_all_for_test(),
        same unpaginated reasoning: a modular attempt must never
        silently miss a question."""
        stmt = select(Question).where(Question.module_id == module_id, Question.deleted_at.is_(None))
        return list(self.db.scalars(stmt).all())
        stmt = (
            select(Question)
            .where(Question.test_id == test_id, Question.deleted_at.is_(None))
            .order_by(Question.created_at.asc())
            .options(selectinload(Question.options))
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, question: Question) -> Question:
        self.db.add(question)
        self.db.flush()
        return question

    def update(self, question: Question, data: dict) -> Question:
        for field, value in data.items():
            setattr(question, field, value)
        self.db.flush()
        return question

    def soft_delete(self, question: Question) -> None:
        question.deleted_at = datetime.now(timezone.utc)
        question.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()


class OptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, option_id: uuid.UUID) -> QuestionOption | None:
        stmt = select(QuestionOption).where(QuestionOption.id == option_id, QuestionOption.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_question(self, question_id: uuid.UUID) -> list[QuestionOption]:
        stmt = select(QuestionOption).where(
            QuestionOption.question_id == question_id, QuestionOption.deleted_at.is_(None)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, option: QuestionOption) -> QuestionOption:
        self.db.add(option)
        self.db.flush()
        return option

    def update(self, option: QuestionOption, data: dict) -> QuestionOption:
        for field, value in data.items():
            setattr(option, field, value)
        self.db.flush()
        return option

    def soft_delete(self, option: QuestionOption) -> None:
        option.deleted_at = datetime.now(timezone.utc)
        option.status = "archived"
        self.db.flush()


class MediaRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, media_id: uuid.UUID) -> QuestionMedia | None:
        stmt = select(QuestionMedia).where(QuestionMedia.id == media_id, QuestionMedia.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, media: QuestionMedia) -> QuestionMedia:
        self.db.add(media)
        self.db.flush()
        return media

    def soft_delete(self, media: QuestionMedia) -> None:
        media.deleted_at = datetime.now(timezone.utc)
        media.status = "archived"
        self.db.flush()
