"""
Business logic for certificate issuance, templates, and public
verification. Reads ResultRepository (results module) read-only.
pdf_url is always None on creation — out of scope for Sprint 7, never a
silent fake value.
"""
import uuid

from app.core.audit import log_action
from app.modules.certificates.exceptions import (
    CannotCertifyFailedResultException,
    CertificateNotFoundException,
    InvalidVerificationCodeException,
    TemplateNotFoundException,
)
from app.modules.certificates.models import Certificate, CertificateTemplate, CertificateVerification
from app.modules.certificates.repository import CertificateRepository, TemplateRepository, VerificationRepository
from app.modules.certificates.schemas import TemplateCreateRequest, VerificationResultOut
from app.modules.certificates.validators import generate_certificate_number, generate_verification_code
from app.modules.results.repository import ResultRepository


class CertificateService:
    def __init__(
        self,
        repository: CertificateRepository,
        verification_repository: VerificationRepository,
        result_repository: ResultRepository,
    ):
        self.repo = repository
        self.verification_repo = verification_repository
        self.result_repo = result_repository

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
        self.repo.commit()
        certificate.verification_code = verification.verification_code  # already created above, no second query needed
        return certificate

    def get(self, certificate_id: uuid.UUID, user_id: uuid.UUID) -> Certificate:
        certificate = self.repo.get_by_id(certificate_id)
        if certificate is None or certificate.user_id != user_id:
            raise CertificateNotFoundException("Sertifikat topilmadi")
        return self._with_verification_code(certificate)

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
