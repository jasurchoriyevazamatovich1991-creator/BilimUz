"""
Schema-level validation tests — these catch bugs BEFORE they reach the
service layer. BUG-002 (unrestricted status) is regression-tested here.
"""
import pytest
from pydantic import ValidationError

from app.modules.subjects.schemas import SubjectUpdateRequest


@pytest.mark.parametrize("status_value", ["active", "inactive", "archived"])
def test_accepts_allowed_status_values(status_value):
    req = SubjectUpdateRequest(status=status_value)
    assert req.status == status_value


def test_rejects_arbitrary_status_value():
    """Regression test for BUG-002: status was previously unrestricted."""
    with pytest.raises(ValidationError):
        SubjectUpdateRequest(status="banana")


def test_status_none_is_allowed_when_not_updating_it():
    req = SubjectUpdateRequest(name="Fizika")
    assert req.status is None
