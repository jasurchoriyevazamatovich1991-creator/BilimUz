"""
Business logic for certificate issuance, templates, and public
verification. Reads ResultRepository (results module) read-only.
pdf_url is always None on creation — out of scope for Sprint 7, never a
silent fake value.

Sprint 43: PDF generation is added, synchronous, reusing the existing
StorageBackend abstraction (no new storage system) — see
CertificateService._generate_and_store_pdf().
"""
import io
import uuid
from datetime import date

from app.core.audit import log_action
from app.core.config import get_settings
from app.modules.certificates.exceptions import (
    CannotCertifyFailedResultException,
    CertificateNotFoundException,
    InvalidVerificationCodeException,
    TemplateNotFoundException,
)
from app.modules.certificates.models import Certificate, CertificateTemplate, CertificateVerification
from app.modules.certificates.pdf_generator import generate_certificate_pdf
from app.modules.certificates.repository import CertificateRepository, TemplateRepository, VerificationRepository
from app.modules.certificates.schemas import TemplateCreateRequest, VerificationResultOut
from app.modules.certificates.validators import generate_certificate_number, generate_verification_code
from app.modules.results.repository import ResultRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.tests.repository import TestRepository
from app.modules.uploads.storage import StorageBackend
from app.modules.users.repository import UserRepository

# Deterministic — the same certificate always maps to the same object
# key, so regenerating a PDF overwrites the existing R2 object in place
# rather than creating an orphan (Sprint 43's explicit idempotency
# requirement). certificate.id is already a globally-unique UUID, the
# same trust/uniqueness level this codebase already gives upload_id.
_PDF_OBJECT_KEY_TEMPLATE = "certificates/{certificate_id}.pdf"

# PRESIGNED_DOWNLOAD_TTL_SECONDS: how long a single GET /certificates/{id}/download
# response's signed URL stays valid. 15 minutes — long enough for the
# browser to actually fetch/open the PDF, short enough that a leaked
# URL (e.g. in a browser history or a proxy log) doesn't stay valid
# indefinitely. Same order of magnitude as uploads' own presigned URLs.
PRESIGNED_DOWNLOAD_TTL_SECONDS = 900


class CertificateService:
    def __init__(
        self,
        repository: CertificateRepository,
        verification_repository: VerificationRepository,
        result_repository: ResultRepository,
        test_repository: TestRepository,
        subject_repository: SubjectRepository,
        user_repository: UserRepository,
        storage: StorageBackend,
    ):
        self.repo = repository
        self.verification_repo = verification_repository
        self.result_repo = result_repository
        self.test_repo = test_repository
        self.subject_repo = subject_repository
        self.user_repo = user_repository
        self.storage = storage

    def _with_verification_code(self, certificate: Certificate) -> Certificate:
        """Attaches the linked CertificateVerification's code as a
        transient (non-persisted, non-mapped) attribute so CertificateOut
        can read it via from_attributes=True. Certificate has no DB
        column or ORM relationship for this — setting a plain Python
        attribute here is invisible to SQLAlchemy's flush/commit, so
        this can never accidentally get written to the database.
        """
        verification = self.verification_repo.get_by_certificate_id(certificate.id)
        certificate.verification_code = verification.verification_code if verification else ""
        return certificate

    def _generate_and_store_pdf(self, certificate: Certificate, verification_code: str) -> str:
        """The single place PDF bytes are built and saved — reused by
        both issue() (first-time generation) and get_download_url()'s
        on-demand-recovery path, per this sprint's explicit
        'reuse a single PDF generation method' requirement.

        Every field pulled from Test/Subject/User is read defensively
        (None-safe) — a certificate's linked rows are expected to exist.
        Result_id/user_id are the only certificates.* required foreign
        keys, but test_id/subject_id come from the joined Result/Test
        which themselves have nullable subject_id (verified in Sprint 41
        audit) — subject_name can legitimately be absent."""
        result = self.result_repo.get_by_id(certificate.result_id)
        test = self.test_repo.get_by_id(result.test_id) if result else None
        subject = self.subject_repo.get_by_id(test.subject_id) if (test and test.subject_id) else None
        user = self.user_repo.get_by_id(certificate.user_id)

        student_full_name = f"{user.first_name} {user.last_name}".strip() if user else ""
        settings = get_settings()
        frontend_base = settings.ALLOWED_ORIGINS[0] if settings.ALLOWED_ORIGINS else ""
        verification_url = f"{frontend_base}/certificates/verify?code={verification_code}"

        pdf_bytes = generate_certificate_pdf(
            certificate_number=certificate.certificate_number,
            student_full_name=student_full_name,
            test_title=test.title if test else "",
            subject_name=subject.name if subject else None,
            score=float(result.score) if result else None,
            percentage=float(result.percentage) if result else None,
            issue_date=certificate.created_at.date().isoformat() if certificate.created_at else date.today().isoformat(),
            verification_code=verification_code,
            verification_url=verification_url,
        )

        object_key = _PDF_OBJECT_KEY_TEMPLATE.format(certificate_id=certificate.id)
        self.storage.save(object_key, io.BytesIO(pdf_bytes))
        return object_key

    def issue(self, result_id: uuid.UUID, user_id: uuid.UUID, template_id: uuid.UUID | None, actor_id: uuid.UUID) -> Certificate:
        result = self.result_repo.get_by_id(result_id)
        if result is None or result.user_id != user_id:
            raise CertificateNotFoundException("Natija topilmadi")
        if not result.is_passed:
            raise CannotCertifyFailedResultException("Faqat muvaffaqiyatli natija uchun sertifikat berish mumkin")

        existing = self.repo.get_by_user_and_test(user_id, result.test_id)
        if existing:
            return self._with_verification_code(existing)

        certificate = Certificate(
            user_id=user_id, result_id=result_id, template_id=template_id,
            certificate_number=generate_certificate_number(), pdf_url=None,
        )
        self.repo.create(certificate)
        verification = self.verification_repo.create(CertificateVerification(
            certificate_id=certificate.id, verification_code=generate_verification_code(),
        ))
        log_action(self.repo.db, action="certificate.issued", user_id=actor_id, entity_type="certificate", entity_id=certificate.id)

        # Synchronous PDF generation (Sprint 43) — this project has no
        # background-job architecture, and introducing one just for this
        # feature is explicitly out of scope for this sprint.
        object_key = self._generate_and_store_pdf(certificate, verification.verification_code)
        self.repo.update_pdf_url(certificate, object_key)

        self.repo.commit()
        certificate.verification_code = verification.verification_code  # already created above, no second query needed
        return certificate

    def get(self, certificate_id: uuid.UUID, user_id: uuid.UUID) -> Certificate:
        certificate = self.repo.get_by_id(certificate_id)
        if certificate is None or certificate.user_id != user_id:
            raise CertificateNotFoundException("Sertifikat topilmadi")
        return self._with_verification_code(certificate)

    def get_download_url(self, certificate_id: uuid.UUID, user_id: uuid.UUID) -> str:
        """Sprint 43. Same anti-enumeration shape as get(): a
        certificate that doesn't exist or isn't the caller's own raises
        the identical CertificateNotFoundException either way — the
        caller can never distinguish 'no such certificate' from 'exists,
        but isn't yours'.

        If pdf_url is None (a previous generation attempt never
        completed, or this is an older certificate issued before Sprint
        43), the PDF is generated on demand here rather than failing —
        this sprint's explicit preferred behavior for resilience."""
        certificate = self.repo.get_by_id(certificate_id)
        if certificate is None or certificate.user_id != user_id:
            raise CertificateNotFoundException("Sertifikat topilmadi")

        verification = self.verification_repo.get_by_certificate_id(certificate.id)
        verification_code = verification.verification_code if verification else ""

        if certificate.pdf_url is None:
            object_key = self._generate_and_store_pdf(certificate, verification_code)
            self.repo.update_pdf_url(certificate, object_key)
            self.repo.commit()
        else:
            # Deterministic key — regenerating (e.g. a future "resend"
            # feature) would overwrite the SAME object_key already
            # stored in pdf_url, never creating an orphan. Nothing to do
            # here for the already-generated case; the existing key is
            # reused as-is.
            object_key = certificate.pdf_url

        return self.storage.create_presigned_download(object_key, PRESIGNED_DOWNLOAD_TTL_SECONDS)

    def list_mine(self, user_id: uuid.UUID, page: int, per_page: int) -> tuple[list[Certificate], int]:
        items, total = self.repo.list_for_user(user_id, page, per_page)
        items = [self._with_verification_code(c) for c in items]
        return items, total


class TemplateService:
    def __init__(self, repository: TemplateRepository):
        self.repo = repository

    def create_template(self, data: TemplateCreateRequest, actor_id: uuid.UUID) -> CertificateTemplate:
        template = CertificateTemplate(name=data.name, design=data.design, created_by=actor_id)
        self.repo.create(template)
        self.repo.commit()
        return template

    def list_templates(self) -> list[CertificateTemplate]:
        return self.repo.list_active()

    def get_template(self, template_id: uuid.UUID) -> CertificateTemplate:
        template = self.repo.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundException("Shablon topilmadi")
        return template


class VerificationService:
    def __init__(self, repository: VerificationRepository, certificate_repository: CertificateRepository):
        self.repo = repository
        self.cert_repo = certificate_repository

    def verify(self, code: str, ip: str | None) -> VerificationResultOut:
        verification = self.repo.get_by_code(code)
        if verification is None:
            raise InvalidVerificationCodeException("Tekshiruv kodi noto'g'ri")

        certificate = self.cert_repo.get_by_id(verification.certificate_id)
        self.repo.record_check(verification, ip)
        self.repo.commit()

        return VerificationResultOut(
            certificate_number=certificate.certificate_number if certificate else "",
            is_valid=certificate is not None and certificate.status == "issued",
            verified_count=verification.verified_count,
        )
