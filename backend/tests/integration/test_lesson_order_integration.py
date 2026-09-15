"""
Sprint 40 Phase 3 — Integration Test 1: Lesson/Topic persistence and
order_number, including the UNIQUE(topic_id, order_number) constraint.

This is EXACTLY the kind of behavior the Sprint 40 audit identified as
impossible to verify with mocks: a real PostgreSQL UNIQUE constraint
violation (IntegrityError), not a Python-level check.

Uses ONLY existing models/services — no new business logic invented.
"""
import uuid

from app.modules.lessons.exceptions import DuplicateOrderNumberException
from app.modules.lessons.models import Lesson
from app.modules.lessons.repository import LessonRepository
from app.modules.lessons.schemas import LessonCreateRequest
from app.modules.lessons.service import LessonService
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.topics.models import Topic
from app.modules.topics.repository import TopicRepository
from app.modules.users.models import User, UserStatus


def _make_actor(pg_session) -> uuid.UUID:
    """A real User row — Lesson.created_by is a genuine FK to users.id,
    enforced by real PostgreSQL (unlike the mock-based unit tests, which
    never actually check this)."""
    role = pg_session.query(Role).filter(Role.name == "Teacher").one()
    user = User(
        role_id=role.id, first_name="Integration", last_name="Actor",
        email=f"actor-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return user.id


def _make_subject_and_topic(pg_session) -> Topic:
    subject = Subject(name=f"Integration Subject {uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    topic = Topic(subject_id=subject.id, title="Integration Topic")
    pg_session.add(topic)
    pg_session.flush()
    return topic


def test_lesson_order_number_persists_to_real_postgres(pg_session):
    topic = _make_subject_and_topic(pg_session)
    service = LessonService(LessonRepository(pg_session), TopicRepository(pg_session))
    actor_id = _make_actor(pg_session)

    lesson = service.create_lesson(
        LessonCreateRequest(topic_id=topic.id, title="Dars 1", content="Matn", order_number=0),
        actor_id=actor_id,
    )

    # Re-fetch from a FRESH query (not the same Python object) — proves
    # the value is actually in the real table, not just held in memory.
    reloaded = pg_session.query(Lesson).filter(Lesson.id == lesson.id).one()
    assert reloaded.order_number == 0
    assert reloaded.topic_id == topic.id


def test_lesson_order_number_auto_assigns_next_when_omitted(pg_session):
    topic = _make_subject_and_topic(pg_session)
    service = LessonService(LessonRepository(pg_session), TopicRepository(pg_session))
    actor_id = _make_actor(pg_session)

    first = service.create_lesson(LessonCreateRequest(topic_id=topic.id, title="Birinchi", content="A"), actor_id=actor_id)
    second = service.create_lesson(LessonCreateRequest(topic_id=topic.id, title="Ikkinchi", content="B"), actor_id=actor_id)

    assert first.order_number == 0
    assert second.order_number == 1


def test_unique_topic_id_order_number_is_enforced_by_real_postgres(pg_session):
    """The exact scenario mock-based tests structurally cannot verify —
    a real DB-level UNIQUE constraint violation. Two lessons in the SAME
    topic with an explicit, identical order_number must be rejected."""
    topic = _make_subject_and_topic(pg_session)
    service = LessonService(LessonRepository(pg_session), TopicRepository(pg_session))
    actor_id = _make_actor(pg_session)

    service.create_lesson(
        LessonCreateRequest(topic_id=topic.id, title="Birinchi", content="A", order_number=5), actor_id=actor_id,
    )

    try:
        service.create_lesson(
            LessonCreateRequest(topic_id=topic.id, title="Ikkinchi", content="B", order_number=5), actor_id=actor_id,
        )
        assert False, "expected DuplicateOrderNumberException from the real UNIQUE constraint"
    except DuplicateOrderNumberException:
        pass

    # The rejected insert must not have left a partial row behind.
    count = pg_session.query(Lesson).filter(Lesson.topic_id == topic.id, Lesson.order_number == 5).count()
    assert count == 1


def test_two_different_topics_can_each_have_order_number_zero(pg_session):
    """The UNIQUE constraint is scoped to (topic_id, order_number), not
    order_number alone — this must NOT raise."""
    subject = Subject(name=f"Integration Subject {uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    topic_a = Topic(subject_id=subject.id, title="Mavzu A")
    topic_b = Topic(subject_id=subject.id, title="Mavzu B")
    pg_session.add_all([topic_a, topic_b])
    pg_session.flush()

    service = LessonService(LessonRepository(pg_session), TopicRepository(pg_session))
    actor_id = _make_actor(pg_session)

    lesson_a = service.create_lesson(LessonCreateRequest(topic_id=topic_a.id, title="A dars", content="x", order_number=0), actor_id=actor_id)
    lesson_b = service.create_lesson(LessonCreateRequest(topic_id=topic_b.id, title="B dars", content="x", order_number=0), actor_id=actor_id)

    assert lesson_a.order_number == 0
    assert lesson_b.order_number == 0
