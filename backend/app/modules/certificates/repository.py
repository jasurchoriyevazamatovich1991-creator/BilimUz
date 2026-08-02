"""Data-access layer for CertificateTemplate, Certificate,
CertificateVerification — three repositories in one file, same cohesive-
module reasoning as questions/repository.py."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.certificates.models import Certificate, CertificateTemplate, CertificateVerification


class CertificateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, certificate_id: uuid.UUID) -> Certificate | None:
        stmt = select(Certificate).where(Certificate.id == certificate_id, Certificate.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_user_and_test(self, user_id: uuid.UUID, test_id: uuid.UUID):
        """Idempotency check per the approved (user_id, test_id) key —
        joins through `results` (read-only) since certificates has no
        direct test_id column."""
        from app.modules.results.models import Result
        stmt = (
            select(Certificate)
            .join(Result, Result.id == Certificate.result_id)
            .where(Certificate.user_id == user_id, Result.test_id == test_id, Certificate.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID, page: int, per_page: int) -> tuple[list[Certificate], int]:
        stmt = select(Certificate).where(Certificate.user_id == user_id, Certificate.deleted_at.is_(None))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Certificate.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def create(self, certificate: Certificate) -> Certificate:
        self.db.add(certificate)
        self.db.flush()
        return certificate

    def commit(self) -> None:
        self.db.commit()


class TemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, template_id: uuid.UUID) -> CertificateTemplate | None:
        stmt = select(CertificateTemplate).where(CertificateTemplate.id == template_id, CertificateTemplate.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active(self) -> list[CertificateTemplate]:
        stmt = select(CertificateTemplate).where(CertificateTemplate.status == "active", CertificateTemplate.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def create(self, template: CertificateTemplate) -> CertificateTemplate:
        self.db.add(template)
        self.db.flush()
        return template

    def commit(self) -> None:
        self.db.commit()


class VerificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_certificate_id(self, certificate_id: uuid.UUID) -> CertificateVerification | None:
        stmt = select(CertificateVerification).where(CertificateVerification.certificate_id == certificate_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_code(self, code: str) -> CertificateVerification | None:
        stmt = select(CertificateVerification).where(CertificateVerification.verification_code == code, CertificateVerification.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, verification: CertificateVerification) -> CertificateVerification:
        self.db.add(verification)
        self.db.flush()
        return verification

    def record_check(self, verification: CertificateVerification, ip: str | None) -> None:
        verification.verified_count += 1
        verification.last_verified_at = datetime.now(timezone.utc)
        verification.last_verified_ip = ip
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
