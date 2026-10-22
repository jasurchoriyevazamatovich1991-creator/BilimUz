"""Task 10 — list `sort` parameters resolve only to real, non-credential columns."""
import app.main  # noqa: F401  — registers every mapper (User -> Role, …)
from app.core.sorting import sortable_column
from app.modules.lessons.models import Lesson
from app.modules.users.models import User


def test_real_columns_are_sortable():
    assert sortable_column(Lesson, "title", Lesson.created_at) is Lesson.title
    assert sortable_column(User, "last_name", User.created_at) is User.last_name


def test_attributes_that_are_not_columns_fall_back_to_the_default():
    for name in ("__class__", "__init__", "metadata", "topic", "registry", "", "title; DROP TABLE lessons"):
        assert sortable_column(Lesson, name, Lesson.created_at) is Lesson.created_at


def test_credential_columns_are_never_sortable():
    assert sortable_column(User, "password_hash", User.created_at) is User.created_at
