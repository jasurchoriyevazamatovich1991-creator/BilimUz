"""
Sprint 72 — CONC-1 + TEST-3: Certificate issuance, verification,
ownership, and concurrency, against real PostgreSQL. Alongside (not
replacing) the existing mocked unit tests in test_certificate_service.py.

CONC-1 — audit finding: CertificateService.issue() used an unprotected
check-then-act pattern (CertificateRepository.get_by_user_and_test()
then an unconditional create()). Two concurrent issue() calls for the
same (user_id, test_id) could both take the "not found" branch and
both create a Certificate. Fixed by migration 0018 (a denormalized
Certificate.test_id column + uq_certificates_user_id_test_id) plus
CertificateRepository.insert_if_not_exists() — a single atomic
INSERT ... ON CONFLICT DO NOTHING, the same established pattern as
StatisticsRepository.upsert_after_result()/RankingRepository.upsert()
— with CertificateService.issue() falling back to the existing row
when it returns None (a lost race).

Reuses this codebase's own established real-concurrency pattern (see
test_sprint69_statistics_null_subject_and_concurrency.py) — a separate
sessionmaker bound to the real engine plus real threading.Thread
workers and a write-synchronizing threading.Barrier for the
genuinely-concurrent test; pg_session is used for the sequential ones.
"""
import threading
import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.database import engine
from app.modules.attempts.models import Answer, AttemptStatus, TestAttempt
from app.modules.certificates.exceptions import CannotCertifyFailedResultException, CertificateNotFoundException
from app.modules.certificates.models import Certificate, CertificateVerification
from app.modules.certificates.repository import CertificateRepository, VerificationRepository
from app.modules.certificates.service import CertificateService
from app.modules.grades.models import Grade  # noqa: F401 — side-effect import only: registers Grade
from app.modules.questions.models import Question, QuestionOption
from app.modules.results.models import Result
from app.modules.results.repository import ResultRepository
from app.modules.roles.models import Role
from app.modules.subjects.repository import SubjectRepository
from app.modules.topics.models import Topic  # noqa: F401 — side-effect import only: registers Topic
# with SQLAlchemy's mapper registry before any Test(...) construction
# below — tests.models.Test has nullable FKs to both grades.id and
# topics.id, and this test file (run standalone, as in CI's per-file
# isolation) never otherwise imports either module.
from app.modules.tests.models import Test
from app.modules.tests.repository import TestRepository
from app.modules.uploads.storage import LocalDiskStorage
from app.modules.users.models import User, UserStatus
from app.modules.users.repository import UserRepository


def _make_service(session, storage_dir) -> CertificateService:
    # LocalDiskStorage.__init__ only creates its own base_dir, not the
    # "certificates/" subdirectory _PDF_OBJECT_KEY_TEMPLATE nests PDFs
    # under (service.py) — production relies on that subdirectory
    # already existing under storage/uploads/; a fresh tmp_path here
    # does not have it yet, so it is created explicitly.
    (storage_dir / "certificates").mkdir(parents=True, exist_ok=True)
    return CertificateService(
        CertificateRepository(session), VerificationRepository(session), ResultRepository(session),
        TestRepository(session), SubjectRepository(session), UserRepository(session),
        LocalDiskStorage(base_dir=str(storage_dir)),
    )


def _make_passed_result(session, prefix: str):
    """A user, a 1-question published test, a submitted+passing
    attempt/answer, and the Result it produces — the minimum real
    fixture CertificateService.issue() needs end to end (including
    real PDF generation, which reads test/subject/user off the result
    chain)."""
    role = session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name=prefix, last_name="Cert", email=f"{prefix.lower()}-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    session.add(user)
    test = Test(subject_id=None, title=f"{prefix} Test", duration=30, question_count=1, status="published")
    session.add(test)
    session.flush()
    question = Question(test_id=test.id, question_text="Q", question_type="single_choice", score=1)
    session.add(question)
    session.flush()
    option = QuestionOption(question_id=question.id, option_text="A", is_correct=True)
    session.add(option)
    session.flush()

    from datetime import datetime, timezone
    attempt = TestAttempt(test_id=test.id, user_id=user.id, status=AttemptStatus.SUBMITTED, start_time=datetime.now(timezone.utc), question_order=[question.id])
    session.add(attempt)
    session.flush()
    answer = Answer(attempt_id=attempt.id, question_id=question.id, selected_option=option.id, is_correct=True)
    session.add(answer)
    result = Result(attempt_id=attempt.id, test_id=test.id, user_id=user.id, score=1, percentage=100.0, is_passed=True)
    session.add(result)
    session.flush()
    session.commit()
    return user.id, test.id, result.id


# =====================================================================
# TEST-3.1 — issuance end-to-end: real Certificate + CertificateVerification
# rows, PDF generated, verification code attached.
# =====================================================================

def test_issue_creates_certificate_and_verification(pg_session, tmp_path):
    user_id, test_id, result_id = _make_passed_result(pg_session, "I1")
    service = _make_service(pg_session, tmp_path)

    certificate = service.issue(result_id, user_id=user_id, template_id=None, actor_id=user_id)

    assert certificate.user_id == user_id
    assert certificate.test_id == test_id
    assert certificate.pdf_url is not None
    assert certificate.verification_code  # attached by issue()

    rows = pg_session.execute(select(Certificate).where(Certificate.id == certificate.id)).scalars().all()
    assert len(rows) == 1

    verification_rows = pg_session.execute(
        select(CertificateVerification).where(CertificateVerification.certificate_id == certificate.id)
    ).scalars().all()
    assert len(verification_rows) == 1
    assert verification_rows[0].verification_code == certificate.verification_code


# =====================================================================
# TEST-3.2 — sequential re-issuance for the same (user, test) is
# idempotent: the second call returns the SAME certificate row, never
# creates a second one.
# =====================================================================

def test_sequential_reissue_is_idempotent_and_creates_no_duplicate(pg_session, tmp_path):
    user_id, test_id, result_id = _make_passed_result(pg_session, "I2")
    service = _make_service(pg_session, tmp_path)

    first = service.issue(result_id, user_id=user_id, template_id=None, actor_id=user_id)
    second = service.issue(result_id, user_id=user_id, template_id=None, actor_id=user_id)

    assert first.id == second.id
    rows = pg_session.execute(
        select(Certificate).where(Certificate.user_id == user_id, Certificate.test_id == test_id)
    ).scalars().all()
    assert len(rows) == 1, f"expected exactly 1 certificate after sequential reissue, got {len(rows)}"


# =====================================================================
# TEST-3.3 — ownership: a certificate cannot be fetched by anyone other
# than the user it was issued to (anti-enumeration — same exception
# either way, per CertificateService.get()'s own docstring).
# =====================================================================

def test_get_rejects_non_owner(pg_session, tmp_path):
    user_id, test_id, result_id = _make_passed_result(pg_session, "I3")
    service = _make_service(pg_session, tmp_path)
    certificate = service.issue(result_id, user_id=user_id, template_id=None, actor_id=user_id)

    other_user_id = uuid.uuid4()
    try:
        service.get(certificate.id, other_user_id)
        assert False, "expected CertificateNotFoundException for a non-owner"
    except CertificateNotFoundException:
        pass


# =====================================================================
# TEST-3.4 — a failed (not passed) result can never be certified, even
# against the real DB/service wiring, not just the mocked unit test.
# =====================================================================

def test_issue_rejects_failed_result_against_real_db(pg_session, tmp_path):
    role = pg_session.query(Role).filter(Role.name == "Student").one()
    user = User(role_id=role.id, first_name="I4", last_name="Cert", email=f"i4-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    test = Test(subject_id=None, title="I4 Test", duration=30, question_count=1, status="published")
    pg_session.add(test)
    pg_session.flush()
    from datetime import datetime, timezone
    attempt = TestAttempt(test_id=test.id, user_id=user.id, status=AttemptStatus.SUBMITTED, start_time=datetime.now(timezone.utc), question_order=[])
    pg_session.add(attempt)
    pg_session.flush()
    result = Result(attempt_id=attempt.id, test_id=test.id, user_id=user.id, score=0, percentage=0.0, is_passed=False)
    pg_session.add(result)
    pg_session.flush()
    pg_session.commit()

    service = _make_service(pg_session, tmp_path)
    try:
        service.issue(result.id, user_id=user.id, template_id=None, actor_id=user.id)
        assert False, "expected CannotCertifyFailedResultException"
    except CannotCertifyFailedResultException:
        pass

    rows = pg_session.execute(select(Certificate).where(Certificate.user_id == user.id)).scalars().all()
    assert rows == []


# =====================================================================
# TEST-3.5 (CONC-1's core proof) — two CONCURRENT issue() calls for the
# same (user_id, test_id): exactly one Certificate row, exactly one
# CertificateVerification row, no unhandled exception from either
# thread — the exact race the Sprint 71 audit flagged as reachable via
# a double-click or a retried request.
# =====================================================================

def test_conc1_concurrent_issue_produces_exactly_one_certificate(tmp_path):
    Session = sessionmaker(bind=engine)

    setup = Session()
    try:
        user_id, test_id, result_id = _make_passed_result(setup, "CONC1")
    finally:
        setup.close()

    write_barrier = threading.Barrier(2)
    outcomes = {}

    class _BarrieredCertificateRepository(CertificateRepository):
        def create(self, certificate):
            write_barrier.wait(timeout=10)
            return super().create(certificate)

    def worker(name: str):
        s = Session()
        try:
            storage_dir = tmp_path / name
            (storage_dir / "certificates").mkdir(parents=True, exist_ok=True)
            service = CertificateService(
                _BarrieredCertificateRepository(s), VerificationRepository(s), ResultRepository(s),
                TestRepository(s), SubjectRepository(s), UserRepository(s),
                LocalDiskStorage(base_dir=str(storage_dir)),
            )
            cert = service.issue(result_id, user_id=user_id, template_id=None, actor_id=user_id)
            outcomes[name] = ("OK", cert.id)
        except Exception as e:
            outcomes[name] = ("ERROR", type(e).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("A",))
    t2 = threading.Thread(target=worker, args=("B",))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    try:
        results = [outcomes.get("A"), outcomes.get("B")]
        successes = [r for r in results if r is not None and r[0] == "OK"]
        assert len(successes) == 2, f"expected both concurrent issue() calls to succeed (one via the fast path or the IntegrityError fallback), got {results}"
        # Both callers must agree on exactly the same certificate id —
        # the idempotent-return contract, not two independent rows.
        assert successes[0][1] == successes[1][1], f"concurrent issue() calls returned different certificate ids: {results}"

        verify = Session()
        try:
            cert_rows = verify.execute(
                select(Certificate).where(Certificate.user_id == user_id, Certificate.test_id == test_id)
            ).scalars().all()
            assert len(cert_rows) == 1, f"expected exactly 1 Certificate row, got {len(cert_rows)} — CONC-1 regressed"

            verification_rows = verify.execute(
                select(CertificateVerification).where(CertificateVerification.certificate_id == cert_rows[0].id)
            ).scalars().all()
            assert len(verification_rows) == 1, f"expected exactly 1 CertificateVerification row, got {len(verification_rows)}"
        finally:
            verify.close()
    finally:
        cleanup = Session()
        try:
            from app.core.audit import AuditLog
            cleanup.query(CertificateVerification).filter(
                CertificateVerification.certificate_id.in_(
                    select(Certificate.id).where(Certificate.user_id == user_id)
                )
            ).delete(synchronize_session=False)
            cleanup.query(Certificate).filter(Certificate.user_id == user_id).delete()
            cleanup.query(AuditLog).filter(AuditLog.user_id == user_id).delete()
            cleanup.query(Answer).filter(
                Answer.attempt_id.in_(select(TestAttempt.id).where(TestAttempt.user_id == user_id))
            ).delete(synchronize_session=False)
            cleanup.query(Result).filter(Result.user_id == user_id).delete()
            cleanup.query(TestAttempt).filter(TestAttempt.user_id == user_id).delete()
            cleanup.query(QuestionOption).filter(
                QuestionOption.question_id.in_(select(Question.id).where(Question.test_id == test_id))
            ).delete(synchronize_session=False)
            cleanup.query(Question).filter(Question.test_id == test_id).delete()
            cleanup.query(Test).filter(Test.id == test_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()
