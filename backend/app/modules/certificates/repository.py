"""Data-access layer for CertificateTemplate, Certificate,
CertificateVerification — three repositories in one file, same cohesive-
module reasoning as questions/repository.py."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.certificates.models import Certificate, CertificateTemplate, CertificateVerification


class CertificateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, certificate_id: uuid.UUID) -> Certificate | None:
        stmt = select(Certificate).where(Certificate.id == certificate_id, Certificate.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_user_and_test(self, user_id: uuid.UUID, test_id: uuid.UUID):
        """Idempotency check per the approved (user_id, test_id) key.

        Sprint 72 (CONC-1) — now a direct column filter against
        Certificate.test_id (migration 0018's denormalized column,
        backed by uq_certificates_user_id_test_id) instead of a join
        through `results`. Same result set as before (test_id is
        always copied from the linked Result.test_id at issuance — see
        CertificateService.issue() — so this is not a behavior change,
        only a simpler/faster query against the now-indexed column)."""
        stmt = select(Certificate).where(
            Certificate.user_id == user_id, Certificate.test_id == test_id, Certificate.deleted_at.is_(None)
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

    def insert_if_not_exists(self, certificate: Certificate) -> Certificate | None:
        """Sprint 72 (CONC-1) — the actual concurrency-safe INSERT for
        CertificateService.issue(), reusing this project's own
        established atomic-upsert idiom (StatisticsRepository.
        upsert_after_result(), RankingRepository.upsert()) instead of
        an application-level SAVEPOINT/except IntegrityError: that
        approach was tried first and rejected during this sprint's own
        test run — it introduced this codebase's only nested
        transaction, which broke the real-PostgreSQL integration test
        suite's pg_session rollback-isolation fixture (conftest.py
        explicitly documents nested application-level savepoints as
        unsafe to combine with its join_transaction_mode=
        "create_savepoint" session).

        `certificate` is a plain, not-yet-session-tracked Certificate
        built by the caller (its id must already be set, since a
        Core-level INSERT needs an explicit value to return on a
        no-op conflict). Returns the freshly-fetched, fully session-
        tracked row on success (re-querying by id rather than reusing
        the transient input object — same reasoning as
        StatisticsRepository.upsert_after_result()'s own re-fetch), or
        None if a concurrent writer already holds this (user_id,
        test_id) — ON CONFLICT DO NOTHING means no exception, no
        poisoned transaction, nothing for the caller to catch."""
        stmt = (
            pg_insert(Certificate)
            .values(
                id=certificate.id, user_id=certificate.user_id, result_id=certificate.result_id,
                test_id=certificate.test_id, template_id=certificate.template_id,
                certificate_number=certificate.certificate_number, pdf_url=certificate.pdf_url,
            )
            .on_conflict_do_nothing(constraint="uq_certificates_user_id_test_id")
            .returning(Certificate.id)
        )
        row = self.db.execute(stmt).first()
        self.db.flush()
        if row is None:
            return None
        return self.get_by_id(row[0])

    def update_pdf_url(self, certificate: Certificate, pdf_url: str) -> Certificate:
        certificate.pdf_url = pdf_url
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
