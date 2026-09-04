"""Unit tests for VerificationService (public verification) and the pure
number/code generation functions."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.certificates.exceptions import InvalidVerificationCodeException
from app.modules.certificates.service import VerificationService
from app.modules.certificates.validators import generate_certificate_number, generate_verification_code


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_cert_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_cert_repo):
    return VerificationService(mock_repo, mock_cert_repo)


def test_verify_raises_on_unknown_code(service, mock_repo):
    mock_repo.get_by_code.return_value = None
    with pytest.raises(InvalidVerificationCodeException):
        service.verify("UNKNOWNCODE", ip="127.0.0.1")


def test_verify_increments_count(service, mock_repo, mock_cert_repo):
    verification = MagicMock(certificate_id=uuid.uuid4(), verified_count=2)
    mock_repo.get_by_code.return_value = verification
    mock_cert_repo.get_by_id.return_value = MagicMock(certificate_number="BILIMUZ-2026-ABC12345", status="issued")

    service.verify("SOMECODE12", ip="1.2.3.4")

    mock_repo.record_check.assert_called_once_with(verification, "1.2.3.4")


def test_verify_returns_valid_true_for_issued_certificate(service, mock_repo, mock_cert_repo):
    verification = MagicMock(certificate_id=uuid.uuid4(), verified_count=0)
    mock_repo.get_by_code.return_value = verification
    mock_cert_repo.get_by_id.return_value = MagicMock(certificate_number="BILIMUZ-2026-XYZ98765", status="issued")

    result = service.verify("SOMECODE12", ip=None)
    assert result.is_valid is True


def test_verify_response_contains_only_the_three_approved_pii_free_fields(service, mock_repo, mock_cert_repo):
    """The public endpoint must never leak student PII — asserted
    directly against the response object's field set, not just by
    convention. VerificationResultOut is unchanged by this fix; this
    test exists so any FUTURE accidental field addition breaks loudly."""
    verification = MagicMock(certificate_id=uuid.uuid4(), verified_count=5)
    mock_repo.get_by_code.return_value = verification
    mock_cert_repo.get_by_id.return_value = MagicMock(
        certificate_number="BILIMUZ-2026-PII0000",
        status="issued",
        user_id=uuid.uuid4(),  # exists on the underlying Certificate — must NOT leak into the response
    )

    result = service.verify("SOMECODE12", ip="9.9.9.9")

    assert set(result.model_dump().keys()) == {"certificate_number", "is_valid", "verified_count"}
    assert not hasattr(result, "user_id")
    assert not hasattr(result, "verification_code")  # the code itself is the lookup key, not echoed back


def test_certificate_number_has_expected_prefix_and_year():
    number = generate_certificate_number()
    assert number.startswith("BILIMUZ-")
    parts = number.split("-")
    assert len(parts) == 3
    assert parts[1].isdigit()


def test_verification_code_is_not_the_same_format_as_certificate_number():
    code = generate_verification_code()
    number = generate_certificate_number()
    assert code != number
    assert "-" not in code


def test_generated_values_are_unique_across_calls():
    codes = {generate_verification_code() for _ in range(50)}
    assert len(codes) == 50  # no collisions in 50 draws
