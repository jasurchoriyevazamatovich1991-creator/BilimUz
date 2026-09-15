"""
Sprint 40 Phase 3 — Integration Test 2: Lesson Progress persistence,
idempotency, and the real UNIQUE(user_id, lesson_id) constraint.
"""
import uuid

from app.modules.lessons.models import Lesson
from app.modules.lessons.repository import LessonRepository
from app.modules.progress.models import LessonProgress
from app.modules.progress.repository import LessonProgressRepository
from app.modules.progress.service import ProgressService
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.topics.models import Topic
from app.modules.users.models import User, UserStatus


def _make_student(pg_session) -> uuid.UUID:
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(
        role_id=role.id, first_name="Integration", last_name="Student",
        email=f"student-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_lesson(pg_session) -> uuid.UUID:
    subject = Subject(name=f"Integration Subject {uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    topic = Topic(subject_id=subject.id, title="Integration Topic")
    pg_session.add(topic)
    pg_session.flush()
    lesson = Lesson(topic_id=topic.id, title="Integration Lesson", content="Matn", order_number=0)
    pg_session.add(lesson)
    pg_session.flush()
    return lesson.id


def test_lesson_progress_persists_to_real_postgres(pg_session):
    student_id = _make_student(pg_session)
    lesson_id = _make_lesson(pg_session)
    service = ProgressService(LessonProgressRepository(pg_session), LessonRepository(pg_session))

    service.complete_lesson(student_id, lesson_id)

    reloaded = pg_session.query(LessonProgress).filter(
        LessonProgress.user_id == student_id, LessonProgress.lesson_id == lesson_id,
    ).one()
    assert reloaded.completed_at is not None


def test_completing_the_same_lesson_twice_does_not_create_a_duplicate_row(pg_session):
    """Verifies BOTH the service's own existence-check AND (implicitly)
    that the real UNIQUE(user_id, lesson_id) constraint would back it up
    — mock tests can only verify the former."""
    student_id = _make_student(pg_session)
    lesson_id = _make_lesson(pg_session)
    service = ProgressService(LessonProgressRepository(pg_session), LessonRepository(pg_session))

    service.complete_lesson(student_id, lesson_id)
    service.complete_lesson(student_id, lesson_id)  # second call — must be a no-op, not an error

    count = pg_session.query(LessonProgress).filter(
        LessonProgress.user_id == student_id, LessonProgress.lesson_id == lesson_id,
    ).count()
    assert count == 1


def test_unique_user_lesson_constraint_is_enforced_by_real_postgres(pg_session):
    """Bypasses the service's own existence-check entirely (inserting
    directly) to prove the DB-level constraint itself — not just the
    application-level guard — actually exists and works."""
    student_id = _make_student(pg_session)
    lesson_id = _make_lesson(pg_session)
    from datetime import datetime, timezone

    pg_session.add(LessonProgress(user_id=student_id, lesson_id=lesson_id, completed_at=datetime.now(timezone.utc)))
    pg_session.flush()

    from sqlalchemy.exc import IntegrityError
    pg_session.add(LessonProgress(user_id=student_id, lesson_id=lesson_id, completed_at=datetime.now(timezone.utc)))
    try:
        pg_session.flush()
        assert False, "expected a real IntegrityError from UNIQUE(user_id, lesson_id)"
    except IntegrityError:
        pg_session.rollback()


def test_two_different_students_can_each_complete_the_same_lesson(pg_session):
    lesson_id = _make_lesson(pg_session)
    student_a = _make_student(pg_session)
    student_b = _make_student(pg_session)
    service = ProgressService(LessonProgressRepository(pg_session), LessonRepository(pg_session))

    service.complete_lesson(student_a, lesson_id)
    service.complete_lesson(student_b, lesson_id)

    count = pg_session.query(LessonProgress).filter(LessonProgress.lesson_id == lesson_id).count()
    assert count == 2
