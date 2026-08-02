"""FastAPI dependency wiring for the certificates module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.certificates.repository import CertificateRepository, TemplateRepository, VerificationRepository
from app.modules.certificates.service import CertificateService, TemplateService, VerificationService
from app.modules.results.repository import ResultRepository


def get_certificate_repository(db: Session = Depends(get_db)) -> CertificateRepository:
    return CertificateRepository(db)


def get_verification_repository(db: Session = Depends(get_db)) -> VerificationRepository:
    return VerificationRepository(db)


def get_template_repository(db: Session = Depends(get_db)) -> TemplateRepository:
    return TemplateRepository(db)


def get_certificate_service(
    repo: CertificateRepository = Depends(get_certificate_repository),
    verification_repo: VerificationRepository = Depends(get_verification_repository),
    db: Session = Depends(get_db),
) -> CertificateService:
    return CertificateService(repo, verification_repo, ResultRepository(db))


def get_template_service(repo: TemplateRepository = Depends(get_template_repository)) -> TemplateService:
    return TemplateService(repo)


def get_verification_service(
    repo: VerificationRepository = Depends(get_verification_repository),
    cert_repo: CertificateRepository = Depends(get_certificate_repository),
) -> VerificationService:
    return VerificationService(repo, cert_repo)
