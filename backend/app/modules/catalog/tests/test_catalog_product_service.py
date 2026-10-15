"""Unit tests for CatalogProductService — repository mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.modules.catalog.exceptions import (
    CatalogProductAlreadyExistsException,
    CatalogProductNotFoundException,
    InvalidGradeReferenceException,
    InvalidSubjectReferenceException,
)
from app.modules.catalog.schemas import CatalogProductCreateRequest, CatalogProductUpdateRequest
from app.modules.catalog.service import CatalogProductService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return CatalogProductService(mock_repo)


# --- schema-level validation (fails before the service is ever reached) ---

def test_grade_subscription_requires_grade_id_only():
    with pytest.raises(ValidationError):
        CatalogProductCreateRequest(product_type="grade_subscription", name="3-sinf", price=1000)


def test_grade_subscription_rejects_subject_id_also_set():
    with pytest.raises(ValidationError):
        CatalogProductCreateRequest(
            product_type="grade_subscription", grade_id=uuid.uuid4(), subject_id=uuid.uuid4(),
            name="3-sinf", price=1000,
        )


def test_mock_test_requires_subject_id_only():
    with pytest.raises(ValidationError):
        CatalogProductCreateRequest(product_type="mock_test", name="Fizika mock testlari", price=1000)


def test_mock_test_rejects_grade_id_also_set():
    with pytest.raises(ValidationError):
        CatalogProductCreateRequest(
            product_type="mock_test", subject_id=uuid.uuid4(), grade_id=uuid.uuid4(),
            name="Fizika mock testlari", price=1000,
        )


def test_course_rejects_any_ref():
    with pytest.raises(ValidationError):
        CatalogProductCreateRequest(product_type="course", grade_id=uuid.uuid4(), name="IELTS", price=1000)


def test_course_with_no_ref_is_valid():
    req = CatalogProductCreateRequest(product_type="course", name="IELTS Prep", price=200000)
    assert req.grade_id is None and req.subject_id is None


def test_negative_price_rejected():
    with pytest.raises(ValidationError):
        CatalogProductCreateRequest(product_type="course", name="IELTS Prep", price=-1)


def test_zero_duration_days_rejected():
    with pytest.raises(ValidationError):
        CatalogProductCreateRequest(product_type="course", name="IELTS Prep", price=1000, duration_days=0)


def test_duration_days_none_is_allowed():
    req = CatalogProductCreateRequest(product_type="course", name="IELTS Prep", price=1000, duration_days=None)
    assert req.duration_days is None


def test_update_rejects_arbitrary_status():
    with pytest.raises(ValidationError):
        CatalogProductUpdateRequest(status="banana")


# --- service-level behavior ---

def test_create_grade_subscription_rejects_missing_grade(service, mock_repo):
    mock_repo.grade_exists.return_value = False
    data = CatalogProductCreateRequest(product_type="grade_subscription", grade_id=uuid.uuid4(), name="3-sinf", price=1000)
    with pytest.raises(InvalidGradeReferenceException):
        service.create_product(data, actor_id=uuid.uuid4())


def test_create_grade_subscription_rejects_duplicate_grade(service, mock_repo):
    mock_repo.grade_exists.return_value = True
    mock_repo.get_by_grade_id.return_value = MagicMock()
    data = CatalogProductCreateRequest(product_type="grade_subscription", grade_id=uuid.uuid4(), name="3-sinf", price=1000)
    with pytest.raises(CatalogProductAlreadyExistsException):
        service.create_product(data, actor_id=uuid.uuid4())


def test_create_grade_subscription_succeeds(service, mock_repo):
    mock_repo.grade_exists.return_value = True
    mock_repo.get_by_grade_id.return_value = None
    data = CatalogProductCreateRequest(
        product_type="grade_subscription", grade_id=uuid.uuid4(), name="3-sinf obunasi", price=150000, duration_days=30,
    )
    product = service.create_product(data, actor_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()
    assert product.product_type == "grade_subscription"
    assert product.duration_days == 30


def test_create_mock_test_rejects_missing_subject(service, mock_repo):
    mock_repo.subject_exists.return_value = False
    data = CatalogProductCreateRequest(product_type="mock_test", subject_id=uuid.uuid4(), name="Fizika mock testlari", price=50000)
    with pytest.raises(InvalidSubjectReferenceException):
        service.create_product(data, actor_id=uuid.uuid4())


def test_create_mock_test_rejects_duplicate_subject(service, mock_repo):
    mock_repo.subject_exists.return_value = True
    mock_repo.get_by_subject_id.return_value = MagicMock()
    data = CatalogProductCreateRequest(product_type="mock_test", subject_id=uuid.uuid4(), name="Fizika mock testlari", price=50000)
    with pytest.raises(CatalogProductAlreadyExistsException):
        service.create_product(data, actor_id=uuid.uuid4())


def test_create_mock_test_succeeds(service, mock_repo):
    """One mock_test product per subject/exam direction — e.g. one
    Physics product grants every published Physics mock test, not one
    test at a time (spec §1)."""
    mock_repo.subject_exists.return_value = True
    mock_repo.get_by_subject_id.return_value = None
    data = CatalogProductCreateRequest(product_type="mock_test", subject_id=uuid.uuid4(), name="IELTS mock testlari", price=80000)
    product = service.create_product(data, actor_id=uuid.uuid4())
    assert product.product_type == "mock_test"
    assert product.subject_id == data.subject_id
    assert product.grade_id is None


def test_create_course_does_not_check_grade_or_subject_existence(service, mock_repo):
    """Course products carry no ref this phase — creating one must not
    even attempt a grade/subject existence lookup."""
    data = CatalogProductCreateRequest(product_type="course", name="IELTS Prep", price=200000)
    product = service.create_product(data, actor_id=uuid.uuid4())
    mock_repo.grade_exists.assert_not_called()
    mock_repo.subject_exists.assert_not_called()
    mock_repo.commit.assert_called_once()
    assert product.product_type == "course"


def test_get_product_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(CatalogProductNotFoundException):
        service.get_product(uuid.uuid4())


def test_update_product_leaves_product_type_untouched(service, mock_repo):
    """product_type/grade_id/subject_id have no corresponding field in
    CatalogProductUpdateRequest at all — this is a schema-level
    guarantee, asserted here against the actual update payload the
    repository receives."""
    product = MagicMock(id=uuid.uuid4())
    mock_repo.get_by_id.return_value = product
    service.update_product(product.id, CatalogProductUpdateRequest(status="published"), actor_id=uuid.uuid4())
    called_updates = mock_repo.update.call_args[0][1]
    assert "product_type" not in called_updates
    assert "grade_id" not in called_updates
    assert "subject_id" not in called_updates
    assert called_updates["status"] == "published"
