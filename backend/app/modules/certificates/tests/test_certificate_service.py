"""Unit tests for CertificateService — all repositories mocked, no real DB."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.certificates.exceptions import CannotCertifyFailedResultException, CertificateNotFoundException
from app.modules.certificates.service import CertificateService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_verification_repo():
    return MagicMock()


@pytest.fixture
def mock_result_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_verification_repo, mock_result_repo):
    return CertificateService(mock_repo, mock_verification_repo, mock_result_repo)


def test_issue_rejects_failed_result(service, mock_result_repo):
    user_id = uuid.uuid4()
    mock_result_repo.get_by_id.return_value = MagicMock(user_id=user_id, is_passed=False)
    with pytest.raises(CannotCertifyFailedResultException):
        service.issue(uuid.uuid4(), user_id=user_id, template_id=None, actor_id=user_id)


def test_issue_rejects_wrong_owner(service, mock_result_repo):
    mock_result_repo.get_by_id.return_value = MagicMock(user_id=uuid.uuid4(), is_passed=True)
    with pytest.raises(CertificateNotFoundException):
        service.issue(uuid.uuid4(), user_id=uuid.uuid4(), template_id=None, actor_id=uuid.uuid4())


def test_issue_is_idempotent_per_user_and_test(service, mock_repo, mock_result_repo):
    """The key check: idempotency is (user_id, test_id) via the result,
    not result_id — get_by_user_and_test must be called with the
    result's test_id, not the result_id itself."""
    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    result_id = uuid.uuid4()
    mock_result_repo.get_by_id.return_value = MagicMock(user_id=user_id, is_passed=True, test_id=test_id)
    existing = MagicMock()
    mock_repo.get_by_user_and_test.return_value = existing

    certificate = service.issue(result_id, user_id=user_id, template_id=None, actor_id=user_id)

    mock_repo.get_by_user_and_test.assert_called_once_with(user_id, test_id)
    assert certificate is existing
    mock_repo.create.assert_not_called()


def test_issue_succeeds_with_pdf_url_none(service, mock_repo, mock_result_repo, mock_verification_repo):
    user_id = uuid.uuid4()
    mock_result_repo.get_by_id.return_value = MagicMock(user_id=user_id, is_passed=True, test_id=uuid.uuid4())
    mock_repo.get_by_user_and_test.return_value = None

    certificate = service.issue(uuid.uuid4(), user_id=user_id, template_id=None, actor_id=user_id)

    assert certificate.pdf_url is None
    mock_repo.create.assert_called_once()
    mock_verification_repo.create.assert_called_once()


def test_issue_generates_distinct_number_and_code(service, mock_repo, mock_result_repo, mock_verification_repo):
    user_id = uuid.uuid4()
    mock_result_repo.get_by_id.return_value = MagicMock(user_id=user_id, is_passed=True, test_id=uuid.uuid4())
    mock_repo.get_by_user_and_test.return_value = None

    service.issue(uuid.uuid4(), user_id=user_id, template_id=None, actor_id=user_id)

    created_cert = mock_repo.create.call_args[0][0]
    created_verification = mock_verification_repo.create.call_args[0][0]
    assert created_cert.certificate_number != created_verification.verification_code


def test_get_raises_when_not_owned(service, mock_repo):
    mock_repo.get_by_id.return_value = MagicMock(user_id=uuid.uuid4())
    with pytest.raises(CertificateNotFoundException):
        service.get(uuid.uuid4(), user_id=uuid.uuid4())


# --- verification_code attachment (this fix) ---

def test_issue_attaches_verification_code_from_the_just_created_verification(service, mock_repo, mock_result_repo, mock_verification_repo):
    """issue() should NOT need a second verification_repo lookup — the
    code comes straight from the CertificateVerification object it just
    created in this same call."""
    user_id = uuid.uuid4()
    mock_result_repo.get_by_id.return_value = MagicMock(user_id=user_id, is_passed=True, test_id=uuid.uuid4())
    mock_repo.get_by_user_and_test.return_value = None
    mock_verification_repo.create.return_value = MagicMock(verification_code="ABC123XYZ")

    certificate = service.issue(uuid.uuid4(), user_id=user_id, template_id=None, actor_id=user_id)

    assert certificate.verification_code == "ABC123XYZ"
    mock_verification_repo.get_by_certificate_id.assert_not_called()


def test_issue_attaches_verification_code_on_idempotent_reissue(service, mock_repo, mock_result_repo, mock_verification_repo):
    """The idempotent-reissue branch (existing certificate) must ALSO
    carry a verification_code — a second GET/POST for an already-issued
    certificate should not silently drop this field."""
    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    mock_result_repo.get_by_id.return_value = MagicMock(user_id=user_id, is_passed=True, test_id=test_id)
    existing = MagicMock(id=uuid.uuid4())
    mock_repo.get_by_user_and_test.return_value = existing
    mock_verification_repo.get_by_certificate_id.return_value = MagicMock(verification_code="EXISTING-CODE")

    certificate = service.issue(uuid.uuid4(), user_id=user_id, template_id=None, actor_id=user_id)

    assert certificate.verification_code == "EXISTING-CODE"
    mock_verification_repo.get_by_certificate_id.assert_called_once_with(existing.id)


def test_get_attaches_verification_code(service, mock_repo, mock_verification_repo):
    user_id = uuid.uuid4()
    certificate = MagicMock(id=uuid.uuid4(), user_id=user_id)
    mock_repo.get_by_id.return_value = certificate
    mock_verification_repo.get_by_certificate_id.return_value = MagicMock(verification_code="GET-CODE-1")

    result = service.get(certificate.id, user_id=user_id)

    assert result.verification_code == "GET-CODE-1"


def test_list_mine_attaches_verification_code_to_every_item(service, mock_repo, mock_verification_repo):
    user_id = uuid.uuid4()
    cert_a, cert_b = MagicMock(id=uuid.uuid4()), MagicMock(id=uuid.uuid4())
    mock_repo.list_for_user.return_value = ([cert_a, cert_b], 2)
    mock_verification_repo.get_by_certificate_id.side_effect = [
        MagicMock(verification_code="CODE-A"),
        MagicMock(verification_code="CODE-B"),
    ]

    items, total = service.list_mine(user_id, page=1, per_page=20)

    assert [c.verification_code for c in items] == ["CODE-A", "CODE-B"]
    assert total == 2


def test_get_verification_code_defaults_to_empty_string_when_no_verification_record_exists(service, mock_repo, mock_verification_repo):
    """Defensive case — should never happen in practice (issue() always
    creates one), but must not crash if it somehow did."""
    user_id = uuid.uuid4()
    certificate = MagicMock(id=uuid.uuid4(), user_id=user_id)
    mock_repo.get_by_id.return_value = certificate
    mock_verification_repo.get_by_certificate_id.return_value = None

    result = service.get(certificate.id, user_id=user_id)

    assert result.verification_code == ""
