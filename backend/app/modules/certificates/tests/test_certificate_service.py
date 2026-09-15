"""Unit tests for CertificateService — all repositories mocked, no real DB."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.certificates.exceptions import CannotCertifyFailedResultException, CertificateNotFoundException
from app.modules.certificates.pdf_generator import generate_certificate_pdf
from app.modules.certificates.service import CertificateService
from app.modules.roles.models import Role  # noqa: F401 — side-effect import only: registers Role with
# SQLAlchemy's mapper registry before any Certificate(...)/User-adjacent construction below,
# needed because this test file's own isolated import chain never otherwise imports roles/models.py
# (production always does, transitively, via app.main's full router tree).


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_verification_repo():
    return MagicMock()


@pytest.fixture
def mock_result_repo():
    repo = MagicMock()
    # Sensible default so PDF-generation code (which reads test/subject/
    # user off of the result) doesn't crash in tests that only care
    # about issue()'s pass/fail or idempotency behavior and override
    # get_by_id with their own MagicMock() anyway (which itself returns
    # more MagicMocks for every attribute access — safe by construction).
    return repo


@pytest.fixture
def mock_test_repo():
    return MagicMock()


@pytest.fixture
def mock_subject_repo():
    return MagicMock()


@pytest.fixture
def mock_user_repo():
    repo = MagicMock()
    repo.get_by_id.return_value = MagicMock(first_name="Aziz", last_name="Karimov")
    return repo


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.create_presigned_download.return_value = "https://signed.example.com/certificates/fake.pdf"
    return storage


@pytest.fixture
def service(mock_repo, mock_verification_repo, mock_result_repo, mock_test_repo, mock_subject_repo, mock_user_repo, mock_storage):
    return CertificateService(
        mock_repo, mock_verification_repo, mock_result_repo,
        mock_test_repo, mock_subject_repo, mock_user_repo, mock_storage,
    )


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


# --- Sprint 43: Certificate PDF generation & download ---

def test_pdf_generator_produces_a_real_nonempty_pdf():
    """A. PDF generation — valid input produces real, non-empty,
    well-formed PDF bytes (not just 'some bytes exist')."""
    pdf_bytes = generate_certificate_pdf(
        certificate_number="CERT-2026-00042", student_full_name="Dilnoza Yusupova",
        test_title="Matematika DTM", subject_name="Matematika", score=85.0, percentage=92.5,
        issue_date="2026-09-15", verification_code="VERIFYCODE1",
        verification_url="http://localhost:5173/certificates/verify?code=VERIFYCODE1",
    )
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")


def test_pdf_generator_handles_missing_optional_fields_safely():
    """A. subject_name/score/percentage are legitimately optional
    (Sprint 41 audit: Test.subject_id is nullable) — must not crash."""
    pdf_bytes = generate_certificate_pdf(
        certificate_number="CERT-2026-00043", student_full_name="Bekzod Toshev",
        test_title="Umumiy test", subject_name=None, score=None, percentage=None,
        issue_date="2026-09-15", verification_code="VERIFYCODE2",
        verification_url="http://localhost:5173/certificates/verify?code=VERIFYCODE2",
    )
    assert pdf_bytes.startswith(b"%PDF")


def test_issue_generates_and_saves_pdf_then_updates_pdf_url(service, mock_repo, mock_result_repo, mock_verification_repo, mock_storage):
    """B. A passing Result issues a certificate, generates its PDF,
    saves it via the existing storage abstraction, and updates
    pdf_url — all in the one issue() call."""
    user_id = uuid.uuid4()
    mock_result_repo.get_by_id.return_value = MagicMock(user_id=user_id, is_passed=True, test_id=uuid.uuid4(), score=80.0, percentage=88.0)
    mock_repo.get_by_user_and_test.return_value = None
    mock_verification_repo.create.return_value = MagicMock(verification_code="ISSUECODE1")

    service.issue(uuid.uuid4(), user_id=user_id, template_id=None, actor_id=user_id)

    mock_storage.save.assert_called_once()
    saved_key = mock_storage.save.call_args[0][0]
    assert saved_key.startswith("certificates/") and saved_key.endswith(".pdf")
    mock_repo.update_pdf_url.assert_called_once()


def test_issue_rejects_failed_result_generates_no_pdf(service, mock_result_repo, mock_storage):
    """C. A failed Result must not reach PDF generation at all."""
    user_id = uuid.uuid4()
    mock_result_repo.get_by_id.return_value = MagicMock(user_id=user_id, is_passed=False)

    with pytest.raises(CannotCertifyFailedResultException):
        service.issue(uuid.uuid4(), user_id=user_id, template_id=None, actor_id=user_id)

    mock_storage.save.assert_not_called()


def test_issue_idempotent_reissue_does_not_generate_a_second_pdf(service, mock_repo, mock_result_repo, mock_storage):
    """D. Calling issue() twice for the same (user, test) returns the
    existing certificate without creating a duplicate or a second PDF."""
    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    mock_result_repo.get_by_id.return_value = MagicMock(user_id=user_id, is_passed=True, test_id=test_id)
    existing = MagicMock(id=uuid.uuid4())
    mock_repo.get_by_user_and_test.return_value = existing

    service.issue(uuid.uuid4(), user_id=user_id, template_id=None, actor_id=user_id)

    mock_repo.create.assert_not_called()
    mock_storage.save.assert_not_called()


def test_download_url_owner_gets_signed_url(service, mock_repo, mock_verification_repo, mock_storage):
    """E. Owner can download — a signed URL is generated through the
    existing storage abstraction's create_presigned_download()."""
    user_id = uuid.uuid4()
    certificate = MagicMock(id=uuid.uuid4(), user_id=user_id, pdf_url="certificates/abc123.pdf")
    mock_repo.get_by_id.return_value = certificate
    mock_verification_repo.get_by_certificate_id.return_value = MagicMock(verification_code="DLCODE1")

    url = service.get_download_url(certificate.id, user_id=user_id)

    assert url == "https://signed.example.com/certificates/fake.pdf"
    mock_storage.create_presigned_download.assert_called_once_with("certificates/abc123.pdf", 900)


def test_download_url_non_owner_gets_same_not_found_as_get(service, mock_repo):
    """E. Non-owner receives the identical CertificateNotFoundException
    shape as GET /certificates/{id} — no enumeration signal."""
    certificate = MagicMock(id=uuid.uuid4(), user_id=uuid.uuid4())
    mock_repo.get_by_id.return_value = certificate

    with pytest.raises(CertificateNotFoundException):
        service.get_download_url(certificate.id, user_id=uuid.uuid4())


def test_download_url_nonexistent_certificate_gets_not_found(service, mock_repo):
    """E. A made-up certificate_id behaves identically to a real one
    owned by someone else — same exception either way."""
    mock_repo.get_by_id.return_value = None

    with pytest.raises(CertificateNotFoundException):
        service.get_download_url(uuid.uuid4(), user_id=uuid.uuid4())


def test_download_url_missing_pdf_generates_on_demand(service, mock_repo, mock_result_repo, mock_verification_repo, mock_storage):
    """F. certificate.pdf_url is None (e.g. a pre-Sprint-43 certificate,
    or a previous generation attempt that never completed) — the PDF is
    generated on demand rather than failing, per this sprint's
    preferred resilience behavior."""
    user_id = uuid.uuid4()
    certificate = MagicMock(id=uuid.uuid4(), user_id=user_id, pdf_url=None, result_id=uuid.uuid4())
    mock_repo.get_by_id.return_value = certificate
    mock_verification_repo.get_by_certificate_id.return_value = MagicMock(verification_code="RECOVER1")
    mock_result_repo.get_by_id.return_value = MagicMock(test_id=uuid.uuid4(), score=70.0, percentage=75.0)

    url = service.get_download_url(certificate.id, user_id=user_id)

    mock_storage.save.assert_called_once()
    mock_repo.update_pdf_url.assert_called_once()
    assert url == "https://signed.example.com/certificates/fake.pdf"


def test_download_url_reuses_existing_object_key_no_orphan(service, mock_repo, mock_verification_repo, mock_storage):
    """D/F. When pdf_url already exists, get_download_url() must NOT
    regenerate/re-save the PDF — the deterministic key is reused as-is,
    so no duplicate/orphan object is ever created just from a download
    request."""
    user_id = uuid.uuid4()
    certificate = MagicMock(id=uuid.uuid4(), user_id=user_id, pdf_url="certificates/existing.pdf")
    mock_repo.get_by_id.return_value = certificate
    mock_verification_repo.get_by_certificate_id.return_value = MagicMock(verification_code="EXIST1")

    service.get_download_url(certificate.id, user_id=user_id)

    mock_storage.save.assert_not_called()
    mock_repo.update_pdf_url.assert_not_called()
