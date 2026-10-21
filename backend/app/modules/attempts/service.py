"""
Business logic for the Test Engine's attempt lifecycle — start, save
answer, submit, lazy auto-finish, resume, result. See
docs/Sprint6_TestEngine_Architecture.md for the full design rationale
behind every decision referenced in the comments below.

Reads (never writes to) TestRepository, QuestionRepository, and
OptionRepository — all read-only, unmodified except for the one additive
method (QuestionRepository.list_all_for_test) documented in the
questions module's git history for this sprint.
"""
import io
import uuid
from datetime import datetime, timezone
from typing import BinaryIO

from app.core.audit import log_action
from app.modules.attempts.exceptions import (
    InvalidSpeakingAudioException,
    SpeakingAudioNotAllowedException,
    SpeakingAudioNotFoundException,
    SpeakingAudioTooLargeException,
    AttemptMediaNotFoundException,
    AttemptMediaUnavailableException,
    AttemptNotActiveException,
    AttemptNotFoundException,
    ExamNotCompleteException,
    InvalidNumericAnswerException,
    InvalidOptionReferenceException,
    InvalidQuestionReferenceException,
    MaxAttemptsExceededException,
    MockTestAccessDeniedException,
    ModuleNotFoundForAttemptException,
    ResultNotAvailableException,
    TestNotPublishedException,
)
from app.modules.attempts.constants import (
    ACTIVE_STATUSES,
    DEFAULT_MAX_ATTEMPTS,
    SPEAKING_AUDIO_EXTENSION_MIME,
    SPEAKING_AUDIO_MAX_BYTES,
    SPEAKING_AUDIO_MIME_TYPES,
    SPEAKING_COMPONENT,
)
from app.modules.attempts.models import AttemptStatus, TestAttempt
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.attempts.scoring import DEFAULT_SCORING_STRATEGY, is_auto_gradable
from app.modules.attempts.schemas import (
    AnsweredQuestionState,
    AttemptDetailOut,
    AttemptGroupMediaOut,
    AttemptMediaOut,
    AttemptMediaViewUrlOut,
    AttemptListParams,
    AttemptOut,
    ModuleForAttemptOut,
    OptionForAttemptOut,
    QuestionForAttemptOut,
    SubmitResultOut,
)
from app.modules.attempts.validators import build_question_order, compute_expiry, is_expired
from app.modules.questions.answer_matching import InvalidNumericAnswer, grade_short_answer
from app.modules.questions.repository import MediaRepository, OptionRepository, QuestionRepository
from app.modules.uploads.constants import FILE_TYPE_AUDIO, PRESIGNED_DOWNLOAD_TTL_SECONDS, UPLOAD_STATUS_READY
from app.modules.uploads.models import Upload
from app.modules.uploads.repository import UploadRepository
from app.modules.uploads.storage import StorageBackend
from app.modules.tests.repository import ExamSectionRepository, QuestionGroupMediaRepository, QuestionGroupRepository, TestRepository


class AttemptService:
    def __init__(
        self,
        repository: AttemptRepository,
        answer_repository: AnswerRepository,
        test_repository: TestRepository,
        question_repository: QuestionRepository,
        option_repository: OptionRepository,
        module_execution_service: "ModuleExecutionService | None" = None,
        module_repository: "ExamModuleRepository | None" = None,
        section_repository: "ExamSectionRepository | None" = None,
        question_group_repository: "QuestionGroupRepository | None" = None,
        entitlement_service: "EntitlementService | None" = None,
        media_repository: "MediaRepository | None" = None,
        upload_repository: "UploadRepository | None" = None,
        storage: "StorageBackend | None" = None,
        group_media_repository: "QuestionGroupMediaRepository | None" = None,
    ):
        self.repo = repository
        self.answer_repo = answer_repository
        self.test_repo = test_repository
        self.question_repo = question_repository
        self.option_repo = option_repository
        # Sprint 50 — both optional, default None. Every existing
        # caller (all pre-Sprint-50 tests, and any future caller that
        # doesn't need module execution) that constructs AttemptService
        # with only the original 5 arguments is completely unaffected —
        # module_execution/is_modular_test() below is the only place
        # that ever reads these, and it degrades to the exact legacy
        # (non-modular) behavior when they're None.
        self.module_execution = module_execution_service
        self.module_repo = module_repository
        # Sprint A (post-75) — same optional/default-None pattern as
        # module_execution_service/module_repository above. Only read by
        # get_module_for_attempt(); every existing caller/test
        # constructing AttemptService without it is unaffected.
        self.section_repo = section_repository
        # Sprint 77 — same optional/default-None pattern. Only read by
        # get_attempt_detail()'s group-context enrichment; a caller/test
        # that omits it simply gets group_id/group_title/stimulus_text
        # left None on every question (the exact pre-Sprint-77 shape).
        self.group_repo = question_group_repository
        # Mock Test Entitlements feature — optional, default None,
        # same established pattern as every other optional dependency
        # above. None means this check is skipped entirely (the exact
        # pre-feature behavior) — only the real FastAPI dependency path
        # (attempts/dependencies.py's get_attempt_service) always wires
        # a real EntitlementService, so production requests are always
        # checked; existing unit tests that construct AttemptService
        # with only the original 5 arguments are unaffected.
        self.entitlement_service = entitlement_service
        # Task 1 (exam media delivery) — optional, same backward-compatible
        # constructor pattern as every dependency above. With
        # media_repository None, every question is delivered with
        # media=[] (the exact pre-Task-1 payload) and the media view-url
        # method reports not-found. Only the real FastAPI wiring
        # (attempts/dependencies.py) supplies all three.
        self.media_repo = media_repository
        self.upload_repo = upload_repository
        self.storage = storage
        # Task 3 — optional like the three above; None = group media is
        # never served (view-url reports not-found).
        self.group_media_repo = group_media_repository

    # --- Start ---------------------------------------------------------

    def start_attempt(self, test_id: uuid.UUID, user_id: uuid.UUID) -> TestAttempt:
        test = self.test_repo.get_by_id(test_id)
        if test is None:
            raise TestNotPublishedException("Test topilmadi yoki e'lon qilinmagan")
        if test.status != "published":
            raise TestNotPublishedException("Faqat e'lon qilingan testlarga urinish boshlash mumkin")

        # Mock Test Entitlements feature (spec §1/§6/§10) — a test with
        # is_mock_test=True requires an active entitlement for its own
        # subject_id (guaranteed non-NULL by
        # ck_tests_mock_test_requires_subject, migration 0021) before a
        # NEW attempt may start. This is a hard 403, not a frontend-only
        # filter — "Direct backend API requests cannot bypass
        # entitlement restrictions." Does not affect any non-mock test
        # (is_mock_test defaults False for every existing row) and does
        # not affect an attempt already in progress — only starting a
        # new one (see entitlements/README.md for why that scope was
        # chosen).
        if test.is_mock_test and self.entitlement_service is not None:
            if not self.entitlement_service.has_mock_test_access(user_id, test.subject_id):
                raise MockTestAccessDeniedException(
                    "Bu mock test uchun faol ruxsat (entitlement) yo'q — avval mos fan/yo'nalish bo'yicha sotib olish kerak"
                )

        # Sprint 45 — test.max_attempts (nullable) overrides the
        # platform default when a Test opts in; every existing test has
        # max_attempts = NULL, so this is byte-identical behavior to
        # before this sprint for all of them.
        effective_max_attempts = test.max_attempts if test.max_attempts is not None else DEFAULT_MAX_ATTEMPTS

        # Sprint 60 — S60-A. Serializes the count -> check -> create
        # critical section below for this exact (user_id, test_id) pair
        # via a transaction-scoped PostgreSQL advisory lock (released
        # automatically at self.repo.commit() below, or on rollback if
        # MaxAttemptsExceededException is raised and the session is
        # closed without committing). Without this, two concurrent
        # start_attempt() calls could both read the same
        # count_for_user_and_test() value before either commits its
        # create(), letting both through even when only one attempt
        # remains. See AttemptRepository.acquire_start_attempt_lock().
        self.repo.acquire_start_attempt_lock(user_id, test_id)
        existing = self.repo.count_for_user_and_test(user_id, test_id)
        if existing >= effective_max_attempts:
            raise MaxAttemptsExceededException(f"Bu test uchun maksimal urinishlar soni ({effective_max_attempts}) tugagan")

        questions = self.question_repo.list_all_for_test(test_id)
        # Sprint 78 — group_ids passed alongside question_ids (zero new
        # queries: question.group_id is a plain column already loaded
        # on these same Question rows) so that when shuffle_questions
        # is True, a QuestionGroup's member questions are shuffled as
        # one contiguous block rather than scattered individually. A
        # non-modular test is the only place this ever applies — see
        # build_question_order()'s own docstring for why the modular
        # per-module path (ModuleExecutionService._create_module_progress())
        # is unaffected (it always passes shuffle=False already).
        question_ids = build_question_order(
            [q.id for q in questions], shuffle=test.shuffle_questions, group_ids=[q.group_id for q in questions],
        )

        now = datetime.now(timezone.utc)
        attempt = TestAttempt(
            user_id=user_id, test_id=test_id, start_time=now,
            expires_at=compute_expiry(now, test.duration),
            question_order=question_ids, status=AttemptStatus.IN_PROGRESS,
        )
        self.repo.create(attempt)

        # Sprint 50 — the ONLY branch point in this method. A Test with
        # zero ExamModule rows (every existing Physics/generic test)
        # never reaches this block's body: has_modules() returns False,
        # and self.module_repo/self.module_execution being None (the
        # legacy AttemptService construction) short-circuits the same
        # way. TestAttempt.question_order above is still populated
        # exactly as before regardless — existing endpoints/tests that
        # read it are unaffected either way.
        if self.module_repo is not None and self.module_execution is not None and self.module_repo.has_modules(test_id):
            self.module_execution.initialize_first_module(attempt)

        log_action(self.repo.db, action="attempt.started", user_id=user_id, entity_type="test_attempt", entity_id=attempt.id)
        self.repo.commit()
        return attempt

    # --- Resume / view ---------------------------------------------------

    def get_attempt(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> TestAttempt:
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        self._auto_finish_active_module_if_expired(attempt)
        return attempt

    def get_attempt_detail(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> AttemptDetailOut:
        attempt = self.get_attempt(attempt_id, user_id)

        # Sprint 57 — question DELIVERY now follows the same
        # active-module boundary that save_answer() already enforces via
        # validate_question_in_module() (see below). Before this fix,
        # this method always used the whole-test attempt.question_order
        # regardless of which module was active, so a modular attempt
        # leaked every future module's question content immediately
        # after start_attempt. Non-modular attempts (module_execution is
        # None) and the same edge case save_answer() already tolerates
        # (module execution configured but no active AttemptModuleProgress
        # row right now) are completely unaffected — both fall through to
        # the original attempt.question_order behavior, unchanged.
        effective_question_order, active_module_id, active_module_expires_at = self._resolve_delivery(attempt)

        # ATT-N1 (Sprint 72) — a single batched fetch instead of one
        # get_by_id() round trip per question (each of which itself
        # issued 3 queries: base row + selectinload(options) +
        # selectinload(media)). list_by_ids() only selectinloads
        # .options (no .media), which is safe here since
        # _to_question_view() below never reads question.media.
        # Order is preserved explicitly via the dict lookup below,
        # and a hard-deleted question (missing from the dict) is
        # skipped exactly as the old `if q is not None` filter did.
        questions_by_id = {q.id: q for q in self.question_repo.list_by_ids(effective_question_order)}
        questions = [questions_by_id[qid] for qid in effective_question_order if qid in questions_by_id]
        answers = {a.question_id: a for a in self.answer_repo.list_for_attempt(attempt_id)}

        # Sprint 77 — one batched QuestionGroup fetch for every distinct
        # group_id referenced by `questions` above (already scoped to
        # effective_question_order — the active module for a modular
        # attempt, the whole attempt otherwise), never one query per
        # question. Because the group_ids collected here come only from
        # questions this student was already about to receive, a group
        # belonging to a future module, another test, or another
        # attempt can never be looked up through this path — there is
        # no endpoint or query that takes a caller-supplied group_id.
        # list_active_by_ids() excludes soft-deleted rows, so a deleted
        # group's stimulus never resurfaces even if a question's
        # group_id still points at it (SET NULL only fires on a hard
        # delete). self.group_repo is None for any caller/test that
        # doesn't pass it in — every question then gets the same
        # all-None group fields as before this sprint.
        group_ids = {q.group_id for q in questions if q.group_id is not None}
        groups_by_id = {g.id: g for g in self.group_repo.list_active_by_ids(list(group_ids))} if self.group_repo is not None and group_ids else {}

        media_by_question = self._delivered_media_by_question(questions)
        capabilities = self._question_capabilities(attempt, questions)
        question_views = [self._to_question_view(q, groups_by_id, media_by_question, capabilities) for q in questions if q is not None]
        answered_states = [
            AnsweredQuestionState(
                question_id=qid, is_answered=qid in answers,
                selected_option=answers[qid].selected_option if qid in answers else None,
                selected_options=answers[qid].selected_options if qid in answers else None,
                # Sprint 68 — additive, see schemas.AnsweredQuestionState
                # docstring. Needed so the student UI can resume a
                # previously-typed short_answer/essay answer.
                text_answer=answers[qid].text_answer if qid in answers else None,
                # Task 6 — only a flag; the audio itself is streamed by its
                # own owner-checked endpoint.
                has_audio=qid in answers and answers[qid].audio_upload_id is not None,
            )
            for qid in effective_question_order
        ]
        delivered = set(effective_question_order)
        return AttemptDetailOut(
            **AttemptOut.model_validate(attempt).model_dump(), questions=question_views, answered=answered_states,
            module_id=active_module_id, module_expires_at=active_module_expires_at,
            marked_question_ids=[q for q in self._marked_ids(attempt) if q in delivered],
        )

    # --- Task 6: mark for review -------------------------------------------

    @staticmethod
    def _marked_ids(attempt) -> list:
        marked = attempt.review_marked_question_ids
        return list(marked) if isinstance(marked, (list, tuple)) else []

    def set_review_mark(self, attempt_id: uuid.UUID, question_id: uuid.UUID, user_id: uuid.UUID, marked: bool) -> list[uuid.UUID]:
        """Flags/unflags a question for later review. Owner only (404),
        active attempt only (409 — lazy expiry runs first), and only for a
        question the attempt is currently delivering (422). Never touches
        the Answer row, so an answer is never created, changed or cleared.
        Returns the attempt's current marks within the delivery scope."""
        attempt = self.get_attempt(attempt_id, user_id)
        attempt = self._lock_attempt(attempt)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Bu urinish allaqachon yakunlangan")
        delivered, _, _ = self._resolve_delivery(attempt)
        if question_id not in set(delivered):
            raise InvalidQuestionReferenceException("Bu savol ushbu urinishga tegishli emas")
        current = [q for q in self._marked_ids(attempt) if q != question_id]
        if marked:
            current.append(question_id)
        attempt.review_marked_question_ids = current
        self.repo.commit()
        delivered_set = set(delivered)
        return [q for q in current if q in delivered_set]

    # --- Task 6: IELTS Speaking audio ---------------------------------------

    def _question_capabilities(self, attempt, questions) -> dict:
        """{question_id: (calculator_enabled, accepts_audio)} from each
        question's section — one sections query per attempt."""
        if self.section_repo is None:
            return {}
        sections = {s.id: s for s in self.section_repo.list_for_test(attempt.test_id)}
        test = self.test_repo.get_by_id(attempt.test_id)
        profile = getattr(test, "scoring_profile", None)
        out = {}
        for q in questions:
            section = sections.get(q.section_id) if q.section_id is not None else None
            if section is None:
                continue
            accepts_audio = (
                section.score_component == SPEAKING_COMPONENT and profile == "ielts" and not is_auto_gradable(q)
            )
            out[q.id] = (bool(section.calculator_enabled is True), accepts_audio)
        return out

    def _speaking_question(self, attempt, question_id: uuid.UUID):
        delivered, _, _ = self._resolve_delivery(attempt)
        if question_id not in set(delivered):
            raise InvalidQuestionReferenceException("Bu savol ushbu urinishga tegishli emas")
        question = self.question_repo.get_by_id(question_id)
        if question is None or not self._question_capabilities(attempt, [question]).get(question.id, (False, False))[1]:
            raise SpeakingAudioNotAllowedException("Bu savolga ovozli javob qabul qilinmaydi (faqat IELTS Speaking)")
        return question

    def upload_speaking_audio(
        self, attempt_id: uuid.UUID, question_id: uuid.UUID, user_id: uuid.UUID,
        stream: BinaryIO, content_type: str, declared_size: int | None,
    ):
        """Stores the student's recorded Speaking response for their OWN
        active attempt. Server-side checks: ownership (404), lazy expiry +
        active status (409), question delivered (422) and Speaking-eligible
        (422), MIME allowlist (422), non-empty (422) and size limit (413 —
        enforced on the bytes actually read, not only the declared size).
        Saved through the configured StorageBackend as a private Upload
        owned by the student; re-recording replaces (and removes) the
        previous file. Returns the Upload."""
        if self.storage is None or self.upload_repo is None:
            raise SpeakingAudioNotAllowedException("Ovozli javob saqlash sozlanmagan")
        attempt = self.get_attempt(attempt_id, user_id)
        attempt = self._lock_attempt(attempt)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Bu urinish allaqachon yakunlangan")
        self._speaking_question(attempt, question_id)

        mime = (content_type or "").split(";")[0].strip().lower()
        extension = SPEAKING_AUDIO_MIME_TYPES.get(mime)
        if extension is None:
            raise InvalidSpeakingAudioException("Audio formati qo'llab-quvvatlanmaydi (webm, ogg, mp4, mp3, wav)")
        if declared_size is not None and declared_size > SPEAKING_AUDIO_MAX_BYTES:
            raise SpeakingAudioTooLargeException("Audio hajmi 20 MB dan oshmasligi kerak")
        data = stream.read(SPEAKING_AUDIO_MAX_BYTES + 1)
        if len(data) > SPEAKING_AUDIO_MAX_BYTES:
            raise SpeakingAudioTooLargeException("Audio hajmi 20 MB dan oshmasligi kerak")
        if not data:
            raise InvalidSpeakingAudioException("Audio fayl bo'sh")

        file_url = self.storage.save(f"speaking-{uuid.uuid4()}{extension}", io.BytesIO(data))
        try:
            upload = self.upload_repo.create(Upload(
                user_id=user_id, file_name=f"speaking-{question_id}{extension}", file_url=file_url,
                file_type=FILE_TYPE_AUDIO, size_bytes=len(data), status=UPLOAD_STATUS_READY,
            ))
            existing = self.answer_repo.get(attempt_id, question_id)
            previous = self.upload_repo.get_by_id(existing.audio_upload_id) if existing is not None and existing.audio_upload_id else None
            # Only the audio reference is written: a typed text answer for
            # the same question (existing workflow) is left untouched.
            self.answer_repo.upsert(attempt_id, question_id, {"audio_upload_id": upload.id, "is_correct": None})
            if previous is not None:
                self.upload_repo.soft_delete(previous)
            log_action(self.repo.db, action="attempt.speaking_audio_uploaded", user_id=user_id, entity_type="answer",
                       entity_id=attempt_id, metadata={"question_id": str(question_id), "size_bytes": len(data)})
            self.repo.commit()
        except Exception:
            self.storage.delete(file_url)  # never leave an orphaned file behind a failed write
            raise
        if previous is not None:
            self.storage.delete(previous.file_url)
        return upload

    def open_own_speaking_audio(self, attempt_id: uuid.UUID, question_id: uuid.UUID, user_id: uuid.UUID):
        """(upload, stream, mime) of the caller's OWN recording for this
        question (404 for anyone else / no recording)."""
        attempt = self._get_owned_attempt(attempt_id, user_id)
        return self.open_answer_audio(attempt.id, question_id)

    def open_answer_audio(self, attempt_id: uuid.UUID, question_id: uuid.UUID):
        """Reads a stored Speaking recording. NO authorization of its own:
        callers must have authorized the caller first (owner check above,
        or the grading module's permission + item checks)."""
        if self.storage is None or self.upload_repo is None:
            raise SpeakingAudioNotFoundException("Ovozli javob topilmadi")
        answer = self.answer_repo.get(attempt_id, question_id)
        upload = self.upload_repo.get_by_id(answer.audio_upload_id) if answer is not None and answer.audio_upload_id else None
        if upload is None:
            raise SpeakingAudioNotFoundException("Ovozli javob topilmadi")
        mime = next((m for ext, m in SPEAKING_AUDIO_EXTENSION_MIME.items() if upload.file_name.endswith(ext)), "application/octet-stream")
        return upload, self.storage.read(upload.file_url), mime

    def list_my_attempts(self, user_id: uuid.UUID, params: AttemptListParams) -> tuple[list[TestAttempt], int]:
        return self.repo.list_for_user(user_id, params)

    # --- Answer ------------------------------------------------------------

    def save_answer(
        self, attempt_id: uuid.UUID, user_id: uuid.UUID, question_id: uuid.UUID,
        selected_option: uuid.UUID | None, selected_options: list[uuid.UUID] | None = None,
        text_answer: str | None = None,
    ) -> None:
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        self._auto_finish_active_module_if_expired(attempt)

        # Sprint 82 — Package 1 (answer-saving concurrency). Lock the
        # attempt row BEFORE the active-status check and the answer
        # upsert below — the same "lock BEFORE the active-status check"
        # convention _lock_attempt() already documents and every other
        # finalize-triggering call site in this file already follows
        # (submit_attempt(), _auto_finish_if_expired(),
        # _auto_finish_active_module_if_expired(), submit_module()'s
        # final-module branch). save_answer() was the one entry point
        # that still read the attempt via the unlocked
        # _get_owned_attempt() path and never re-checked under a lock,
        # so a concurrent submit_attempt()/submit_module()/auto-finish
        # (in a different DB session/transaction) could finalize and
        # commit AFTER this method's own unlocked status check passed
        # but BEFORE its answer_repo.upsert()+commit() below — silently
        # persisting an Answer against an attempt that was already
        # scored, which the already-committed score/percentage would
        # never reflect. Each AnswerRepository.upsert() call for a
        # single (attempt_id, question_id) pair was already atomic
        # (Sprint 58 — INSERT ... ON CONFLICT DO UPDATE), so that part
        # was never the problem; this closes the attempt-status race,
        # not the per-row write race. Only this one attempt's row is
        # locked (keyed by its own primary key), so concurrent
        # save_answer calls for a DIFFERENT attempt are never affected
        # — this does not serialize unrelated attempts.
        attempt = self._lock_attempt(attempt)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Bu urinish allaqachon yakunlangan")
        if question_id not in (attempt.question_order or []):
            raise InvalidQuestionReferenceException("Bu savol ushbu urinishga tegishli emas")

        # Sprint 50 — additional, module-scoped validation. A complete
        # no-op for non-modular attempts (self.module_execution is None,
        # or this attempt simply has no active module progress row —
        # the legacy TestAttempt.question_order check above already
        # covers everything for those).
        if self.module_execution is not None:
            active_progress = self.module_execution.get_active_module_progress(attempt_id)
            if active_progress is not None:
                self.module_execution.validate_question_in_module(active_progress, question_id)

        question = self.question_repo.get_by_id(question_id)
        # Sprint 66 — short_answer/essay have no automatic-correctness
        # determination anywhere in the codebase (see scoring.py's
        # AUTO_GRADABLE_QUESTION_TYPES). Persist the submitted free text
        # via the same generic upsert path used by every other question
        # type, leave is_correct NULL (not False — NULL means "awaiting
        # grading", not "wrong"), and return before the choice-scoring
        # branches below, which don't apply to this question type.
        # Task 2 — a short_answer question with a configured answer key
        # is graded here, at save time, exactly like the choice types
        # below grade theirs. An empty answer is "unanswered" (NULL), and
        # a non-numeric answer to a numeric question is REJECTED (422,
        # nothing written — the previously saved answer stays) instead of
        # being stored as wrong: a formatting slip must never cost points
        # silently. The answer key is read from the DB row only; nothing
        # the client sends can influence it.
        if question is not None and question.question_type == "short_answer" and is_auto_gradable(question):
            try:
                is_correct = grade_short_answer(
                    text_answer, question.answer_format, question.accepted_answers,
                    question.case_sensitive, question.numeric_tolerance,
                )
            except InvalidNumericAnswer as exc:
                raise InvalidNumericAnswerException(str(exc))
            self.answer_repo.upsert(attempt_id, question_id, {"text_answer": text_answer, "is_correct": is_correct})
            self.repo.commit()
            return

        if question is not None and not is_auto_gradable(question):
            self.answer_repo.upsert(attempt_id, question_id, {"text_answer": text_answer, "is_correct": None})
            self.repo.commit()
            return

        if question is not None and question.question_type == "multiple_choice":
            # Sprint 30 — the only new branch. single_choice/true_false
            # below is byte-for-byte the original Sprint 6 logic.
            is_correct = self._check_options(question_id, selected_options or [])
            # Sprint 58 — a single atomic upsert replaces the old
            # get()-then-create()/update() check-then-act. The old code
            # had no path that expected the losing side's INSERT to be
            # rejected by uq_answers_attempt_question — a UNIQUE
            # constraint on (attempt_id, question_id) that has existed
            # in the database since migration 0001 (never a new
            # migration for this sprint; see AnswerRepository.upsert()).
            self.answer_repo.upsert(attempt_id, question_id, {"selected_options": selected_options, "selected_option": None, "is_correct": is_correct})
            self.repo.commit()
            return

        is_correct = self._check_option(question_id, selected_option)
        self.answer_repo.upsert(attempt_id, question_id, {"selected_option": selected_option, "is_correct": is_correct})
        self.repo.commit()

    # --- Submit / result -----------------------------------------------------

    def submit_attempt(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> SubmitResultOut:
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        self._auto_finish_active_module_if_expired(attempt)

        # Sprint 59 — the attempt row is locked BEFORE the active-status
        # check and BEFORE _finalize()'s score/percentage write, closing
        # the race the unlocked _get_owned_attempt() left open: two
        # concurrent submit_attempt() calls (or this call racing
        # _auto_finish_if_expired(), now itself lock-safe below) could
        # both observe ACTIVE_STATUSES and both finalize/commit,
        # producing duplicate "attempt.submitted" audit-log rows and a
        # last-write-wins race on score/percentage. See _lock_attempt().
        attempt = self._lock_attempt(attempt)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Bu urinish allaqachon yakunlangan")

        # Sprint 61 — S61-C. A modular attempt must go through
        # submit_module()'s own per-module completion flow, not finalize
        # early via this whole-attempt endpoint while modules remain.
        # is_exam_complete() (module_execution_service.py) already
        # returns True vacuously for a non-modular test (it has no
        # ExamModule rows to be incomplete), so this never affects any
        # non-modular attempt or any AttemptService built without a
        # module_execution_service (the pre-Sprint-50 5-arg legacy
        # construction still used by existing unit tests).
        if self.module_execution is not None and not self.module_execution.is_exam_complete(attempt):
            raise ExamNotCompleteException("Barcha modullar yakunlanmaguncha butun urinishni yakunlab bo'lmaydi")

        self._finalize(attempt, AttemptStatus.SUBMITTED)
        log_action(self.repo.db, action="attempt.submitted", user_id=user_id, entity_type="test_attempt", entity_id=attempt_id)
        self.repo.commit()
        return self._build_result(attempt)

    def get_result(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> SubmitResultOut:
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        # Sprint 82 — Package 2 (result retrieval and expiration). This
        # call was missing here — every other attempt-lifecycle entry
        # point (get_attempt(), save_answer(), submit_attempt(),
        # submit_module()) already calls both
        # _auto_finish_if_expired() (whole-attempt expiry) AND
        # _auto_finish_active_module_if_expired() (per-module expiry,
        # Sprint 79) before doing anything else. get_result() only had
        # the first. For a modular test whose active module's own
        # (shorter) expires_at has passed while the whole-attempt
        # Test.duration/TestAttempt.expires_at has NOT — the normal
        # configuration for a modular test, see Sprint 79's own CRITICAL
        # finding — _auto_finish_if_expired() alone is a no-op (the
        # whole-attempt deadline genuinely hasn't passed), so the
        # attempt stayed ACTIVE_STATUSES forever unless some OTHER
        # endpoint happened to be called first to trigger the
        # module-level check. A student who only ever polled
        # GET /attempts/{id}/result would see "natija hali tayyor emas"
        # (ResultNotAvailableException) indefinitely, even though the
        # exact same expired attempt would have been correctly
        # auto-finished by a GET /attempts/{id} call instead — an
        # inconsistency between two read endpoints for the same
        # underlying state. Reusing the existing, already-idempotent
        # method (a no-op when there is no active module or it has not
        # actually expired — see its own docstring) means repeated
        # get_result() calls remain safe with no duplicate side effects,
        # exactly as they already were for _auto_finish_if_expired().
        self._auto_finish_active_module_if_expired(attempt)
        if attempt.status in ACTIVE_STATUSES:
            raise ResultNotAvailableException("Urinish hali yakunlanmagan")
        return self._build_result(attempt)

    # --- Sprint 50: modular execution ---------------------------------

    def submit_module(self, attempt_id: uuid.UUID, module_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """Requires self.module_execution to be configured (see
        get_attempt_service's Sprint 50 wiring) — this method has no
        meaning for a non-modular AttemptService construction and is
        never called for one (no router path reaches it without a
        module_id in the URL)."""
        attempt = self._get_owned_attempt(attempt_id, user_id)
        self._auto_finish_if_expired(attempt)
        self._auto_finish_active_module_if_expired(attempt)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Bu urinish allaqachon yakunlangan")

        progress = self.module_execution.get_owned_module_progress(attempt, module_id)
        outcome = self.module_execution.submit_module(attempt, progress)

        if outcome["completed"]:
            # Sprint 59 — same lock as submit_attempt()/_auto_finish_if_expired(),
            # applied to the final-module completion path. Unlike
            # submit_attempt() (which raises when the lock reveals the
            # attempt was already finalized by a genuine race), this
            # branch must NOT raise here: module_execution.submit_module()
            # above has already committed the module's own submission —
            # an exception at this later step would leave the module
            # marked submitted while the outer call fails, an
            # inconsistent partial state. If a concurrent submit_attempt()
            # (or another completion path) already finalized the attempt
            # by the time this lock is acquired, we simply skip
            # re-finalizing/re-logging and return the already-committed
            # result — the same idempotent-return pattern
            # ResultService.create_result() uses for its own race.
            attempt = self._lock_attempt(attempt)
            if attempt.status in ACTIVE_STATUSES:
                self._finalize(attempt, AttemptStatus.SUBMITTED)
                log_action(self.repo.db, action="attempt.submitted", user_id=user_id, entity_type="test_attempt", entity_id=attempt_id)
            self.repo.commit()
            result = self._build_result(attempt)
            return {"completed": True, "next_module_id": None, "result": result}

        self.repo.commit()
        return {"completed": False, "next_module_id": outcome["next_module_id"], "result": None}

    # --- Sprint A (post-75): student-scoped module/section metadata ---

    def get_module_for_attempt(self, attempt_id: uuid.UUID, module_id: uuid.UUID, user_id: uuid.UUID) -> ModuleForAttemptOut:
        """Student-scoped module/section name/order lookup — lets the
        frontend build a module navigator without needing the
        Admin/Super-Admin-only /tests/exam-modules endpoints
        (tests/router.py). Reuses
        ModuleExecutionService.get_owned_module_progress() as the exact
        same IDOR guard submit_module() already relies on: a module_id
        with no AttemptModuleProgress row for THIS attempt raises
        ModuleNotFoundForAttemptException (404) regardless of whether
        the module doesn't exist, belongs to a different test, or
        belongs to someone else's attempt — no enumeration signal,
        mirroring every other module-scoped lookup in this service. This
        also means a module is visible here only once execution has
        actually routed the attempt to it (a progress row already
        exists) — an upcoming, unrouted module can never be discovered
        through this endpoint.

        Requires both module_execution and section_repo to be
        configured (the real FastAPI dependency path always wires
        both — see get_attempt_service); either being None means this
        AttemptService was built for a context that doesn't support
        module execution at all (e.g. a pre-Sprint-50 legacy
        construction), so the module is reported not-found exactly as
        it effectively is for that caller."""
        attempt = self._get_owned_attempt(attempt_id, user_id)
        if self.module_execution is None or self.section_repo is None:
            raise ModuleNotFoundForAttemptException("Bu modul ushbu urinishga tegishli emas")

        self.module_execution.get_owned_module_progress(attempt, module_id)

        module = self.module_repo.get_by_id(module_id) if self.module_repo is not None else None
        if module is None:
            raise ModuleNotFoundForAttemptException("Bu modul ushbu urinishga tegishli emas")
        section = self.section_repo.get_by_id(module.section_id)
        if section is None:
            raise ModuleNotFoundForAttemptException("Bu modul ushbu urinishga tegishli emas")

        return ModuleForAttemptOut(
            id=module.id, name=module.name, order_number=module.order_number, duration=module.duration,
            section_id=section.id, section_name=section.name, section_order_number=section.order_number,
        )

    def get_media_view_url(self, attempt_id: uuid.UUID, media_id: uuid.UUID, user_id: uuid.UUID) -> AttemptMediaViewUrlOut:
        """Task 1 — a short-lived URL for one question/option media item
        of an attempt this student is actively taking.

        Authorization, in order:
        1. The attempt must be the caller's own (404 otherwise — the
           same not-found-or-not-yours shape as every attempt endpoint).
        2. Lazy expiry runs first (get_attempt), then the attempt must
           still be active (409 ATTEMPT_NOT_ACTIVE otherwise). Media is
           an exam-time resource; result review is out of scope.
        3. The media must be non-deleted and belong to a question in the
           attempt's CURRENT delivery scope (_resolve_delivery — the
           active module for a modular attempt), and an option-level
           media's option must not be deleted. Anything else is 404, so
           another test's, a future module's, or a deleted item's media
           cannot be fetched by guessing ids.
        4. Upload-backed media: the upload must exist and be finalized,
           then the configured StorageBackend issues the same short-lived
           presigned GET URL used for lesson media (uploads/constants.py
           PRESIGNED_DOWNLOAD_TTL_SECONDS). The storage object key itself
           is never returned. Legacy rows (no upload_id) return their
           stored http(s) URL, already validated at creation time."""
        attempt = self.get_attempt(attempt_id, user_id)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Urinish faol emas — media faqat test davomida mavjud")

        if self.media_repo is None:
            raise AttemptMediaNotFoundException("Media topilmadi")
        media = self.media_repo.get_by_id(media_id)
        if media is None:
            raise AttemptMediaNotFoundException("Media topilmadi")

        delivered_ids, _, _ = self._resolve_delivery(attempt)
        if media.question_id not in set(delivered_ids):
            raise AttemptMediaNotFoundException("Media topilmadi")
        if media.option_id is not None:
            option = self.option_repo.get_by_id(media.option_id)
            if option is None or option.deleted_at is not None or option.question_id != media.question_id:
                raise AttemptMediaNotFoundException("Media topilmadi")

        if media.upload_id is None:
            return AttemptMediaViewUrlOut(view_url=media.file_url, media_type=media.media_type)

        return AttemptMediaViewUrlOut(view_url=self._sign_upload(media.upload_id), media_type=media.media_type)

    def get_group_media_view_url(self, attempt_id: uuid.UUID, media_id: uuid.UUID, user_id: uuid.UUID) -> AttemptMediaViewUrlOut:
        """Task 3 — short-lived URL for one QuestionGroup media item (e.g.
        IELTS Listening audio). Same rules as get_media_view_url():
        owner only (404), active attempt only (409), and the media must
        belong to an ACTIVE group that at least one question in the
        attempt's CURRENT delivery scope points at (_resolve_delivery —
        the active module for a modular attempt). Another test's group,
        a not-yet-routed module's group, a soft-deleted group or media
        all answer 404. Always upload-backed, signed by the configured
        StorageBackend; the object key is never returned."""
        attempt = self.get_attempt(attempt_id, user_id)
        if attempt.status not in ACTIVE_STATUSES:
            raise AttemptNotActiveException("Urinish faol emas — media faqat test davomida mavjud")
        if self.group_media_repo is None or self.group_repo is None:
            raise AttemptMediaNotFoundException("Media topilmadi")

        media = self.group_media_repo.get_active_by_id(media_id)
        if media is None:
            raise AttemptMediaNotFoundException("Media topilmadi")

        delivered_ids, _, _ = self._resolve_delivery(attempt)
        delivered_group_ids = {q.group_id for q in self.question_repo.list_by_ids(delivered_ids) if q.group_id is not None}
        if media.group_id not in delivered_group_ids or not self.group_repo.list_active_by_ids([media.group_id]):
            raise AttemptMediaNotFoundException("Media topilmadi")

        return AttemptMediaViewUrlOut(view_url=self._sign_upload(media.upload_id), media_type=media.media_type)

    def _sign_upload(self, upload_id: uuid.UUID) -> str:
        """Shared by question and group media: the upload must exist and be
        finalized, then the configured StorageBackend issues the same
        short-lived presigned GET URL lesson media uses."""
        if self.upload_repo is None or self.storage is None:
            raise AttemptMediaUnavailableException("Media hozircha mavjud emas")
        upload = self.upload_repo.get_by_id(upload_id)
        if upload is None:
            raise AttemptMediaNotFoundException("Media topilmadi")
        if upload.status != UPLOAD_STATUS_READY:
            raise AttemptMediaUnavailableException("Media fayli hali tayyor emas")
        try:
            return self.storage.create_presigned_download(upload.file_url, PRESIGNED_DOWNLOAD_TTL_SECONDS)
        except NotImplementedError:
            raise AttemptMediaUnavailableException(
                "Joriy fayl saqlash tizimi vaqtinchalik havolalarni qo'llab-quvvatlamaydi"
            )

    # --- Internal helpers --------------------------------------------------

    def _resolve_delivery(self, attempt: TestAttempt) -> tuple[list[uuid.UUID], uuid.UUID | None, datetime | None]:
        """The single place that decides which questions an attempt is
        delivering RIGHT NOW (Sprint 57's active-module boundary) —
        extracted unchanged from get_attempt_detail() so the Task 1
        media view-url check uses exactly the same scope as question
        delivery and the two can never drift apart.

        Returns (effective_question_order, active_module_id,
        active_module_expires_at)."""
        effective_question_order = attempt.question_order or []
        # Sprint A (post-75) — additive. Captured alongside the existing
        # active_progress lookup above (no new query) so AttemptDetailOut
        # can tell the student frontend which module is currently being
        # delivered, without it having to guess from question content.
        # Stays None for every case this didn't change: non-modular
        # attempts, or a modular attempt with no active progress row
        # right now (e.g. already finished).
        active_module_id: uuid.UUID | None = None
        # Sprint 76 — additive, same None-by-default reasoning as
        # active_module_id above. See AttemptDetailOut.module_expires_at.
        active_module_expires_at: datetime | None = None
        if self.module_execution is not None:
            active_progress = self.module_execution.get_active_module_progress(attempt.id)
            if active_progress is not None:
                effective_question_order = active_progress.question_order or []
                active_module_id = active_progress.module_id
                active_module_expires_at = active_progress.expires_at
        return effective_question_order, active_module_id, active_module_expires_at


    def _get_owned_attempt(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> TestAttempt:
        attempt = self.repo.get_by_id(attempt_id)
        if attempt is None or attempt.user_id != user_id:
            raise AttemptNotFoundException("Urinish topilmadi")
        return attempt

    def _check_option(self, question_id: uuid.UUID, selected_option: uuid.UUID | None) -> bool | None:
        if selected_option is None:
            return None
        option = self.option_repo.get_by_id(selected_option)
        if option is None or option.question_id != question_id:
            raise InvalidOptionReferenceException("Tanlangan variant bu savolga tegishli emas")
        return option.is_correct

    def _check_options(self, question_id: uuid.UUID, selected_options: list[uuid.UUID]) -> bool | None:
        """Sprint 30 — multiple_choice scoring. Correct iff the
        student's selected set is EXACTLY the set of correct options —
        every correct option chosen, and no incorrect one chosen
        (standard multi-select grading, not partial credit). Returns
        None (unanswered) only for a genuinely empty selection, mirroring
        _check_option's None-for-unanswered convention above."""
        if not selected_options:
            return None
        all_options = self.option_repo.list_for_question(question_id)
        valid_ids = {o.id for o in all_options}
        for option_id in selected_options:
            if option_id not in valid_ids:
                raise InvalidOptionReferenceException("Tanlangan variant bu savolga tegishli emas")
        correct_ids = {o.id for o in all_options if o.is_correct}
        return set(selected_options) == correct_ids

    def _auto_finish_if_expired(self, attempt: TestAttempt) -> None:
        """Lazy expiration — see docs/Sprint6_TestEngine_Architecture.md
        Section 6. Designed so a future Celery task could call _finalize()
        proactively without changing this method's public callers.

        Sprint 59 — expires_at is immutable once an attempt is created,
        so checking it here, before locking, is safe (mirrors
        ResultService.create_result()'s own pre-lock reads of
        immutable-once-set fields). status is NOT immutable, so it is
        re-checked under the lock immediately below before finalizing —
        this closes the race where this method could run concurrently
        with submit_attempt()/submit_module()'s own finalize path and
        both observe ACTIVE_STATUSES before either commits."""
        if attempt.status in ACTIVE_STATUSES and is_expired(attempt.expires_at):
            attempt = self._lock_attempt(attempt)
            if attempt.status in ACTIVE_STATUSES:
                self._finalize(attempt, AttemptStatus.AUTO_FINISHED)
                self.repo.commit()

    def _auto_finish_active_module_if_expired(self, attempt: TestAttempt) -> None:
        """Sprint 79 — lazy per-module expiry, the module-scope analogue
        of _auto_finish_if_expired() above. Without this, a module whose
        own expires_at has passed while the whole-attempt
        Test.duration/TestAttempt.expires_at has NOT (the normal
        configuration for any modular test where each module carries
        its own, shorter time limit — see Sprint 79 audit CRITICAL
        finding, reproduced by the existing
        test_expired_module_cannot_be_submitted) left the student
        permanently stuck: submit_module() raised ModuleNotActiveException
        on every retry, and submit_attempt() was separately blocked by
        is_exam_complete()==False — no code path ever finalized or
        advanced the expired module.

        A pure no-op for a non-modular AttemptService construction
        (self.module_execution is None), an attempt that is not
        currently ACTIVE_STATUSES (nothing to expire), or a modular
        attempt whose active module — if any — has not actually
        expired. Called from every module-scoped entry point
        (get_attempt(), save_answer(), submit_attempt(), submit_module()),
        mirroring exactly where _auto_finish_if_expired() is called.

        ModuleExecutionService.auto_finish_active_module_if_expired()
        does the actual work (reusing submit_module()'s own locked
        scoring/routing logic) and returns the same
        {"completed": bool, "next_module_id": ...} shape submit_module()
        does, or None if it was a no-op. When the expired module routed
        to a next module, the whole attempt stays ACTIVE_STATUSES (now
        with a fresh active module) and this only needs to commit. When
        the expired module was the last one (completed=True), the whole
        attempt is finalized exactly like _auto_finish_if_expired() does
        for whole-test expiry — AttemptStatus.AUTO_FINISHED, no
        "attempt.submitted" audit-log entry, since this was not an
        explicit user submit action."""
        if self.module_execution is None or attempt.status not in ACTIVE_STATUSES:
            return
        outcome = self.module_execution.auto_finish_active_module_if_expired(attempt)
        if outcome is None:
            return
        if outcome["completed"]:
            attempt = self._lock_attempt(attempt)
            if attempt.status in ACTIVE_STATUSES:
                self._finalize(attempt, AttemptStatus.AUTO_FINISHED)
        self.repo.commit()

    def _lock_attempt(self, attempt: TestAttempt) -> TestAttempt:
        """Sprint 59 — CRITICAL fix for the attempt-finalize race
        identified in the Sprint 59 audit (S59-A). Reuses
        AttemptRepository.get_by_id_locked() exactly as introduced for
        Sprint 54 (SELECT ... FOR UPDATE + populate_existing=True) —
        no new locking mechanism. Every finalize-triggering call site
        (submit_attempt(), _auto_finish_if_expired(), submit_module()'s
        final-module completion branch) must call this BEFORE checking
        whether the attempt is already finalized/submitted/auto-finished
        and BEFORE _finalize()'s score/percentage write, so a second
        concurrent caller blocks here until the first's transaction
        commits, then re-reads the now-current status under the same
        lock instead of racing past an earlier unlocked check.

        populate_existing=True refreshes the same identity-mapped
        TestAttempt object in place (same session, same primary key) —
        the returned object is the caller's own `attempt` reference with
        its attributes brought current, so callers can keep using their
        existing variable after reassigning it from this call's return
        value."""
        return self.repo.get_by_id_locked(attempt.id)

    def _effective_scoring_question_ids(self, attempt: TestAttempt) -> list[uuid.UUID]:
        """Sprint 61 — S61-C. The single source of truth for "which
        questions count toward this attempt's final score/total", used
        by both _finalize() and _build_result() so they can never
        disagree with each other.

        For a modular attempt (module_execution configured AND this
        attempt actually has module-progress rows), delegates to
        ModuleExecutionService.get_effective_question_ids() — the
        deduplicated union of every module's delivered question_order.
        Falls back to the original whole-test attempt.question_order in
        every other case: a non-modular attempt (module_execution is
        None, or the attempt genuinely has zero progress rows — the
        defensive edge case where get_effective_question_ids() returns
        None rather than an empty list). This fallback is byte-identical
        to this method's pre-Sprint-61 behavior in both of those cases,
        so non-modular scoring is completely unaffected."""
        if self.module_execution is not None:
            effective_ids = self.module_execution.get_effective_question_ids(attempt.id)
            if effective_ids is not None:
                return effective_ids
        return list(attempt.question_order or [])

    def _finalize(self, attempt: TestAttempt, new_status: AttemptStatus) -> None:
        answers = self.answer_repo.list_for_attempt(attempt.id)
        question_ids = self._effective_scoring_question_ids(attempt)
        # ATT-N2 (Sprint 72) — same batched-fetch fix as ATT-N1
        # (get_attempt_detail() above): one list_by_ids() call instead
        # of one get_by_id() round trip per question. Safe here too —
        # neither auto_scored_questions below nor DEFAULT_SCORING_
        # STRATEGY.calculate() ever reads question.media.
        questions_by_id = {q.id: q for q in self.question_repo.list_by_ids(question_ids)}
        questions = [questions_by_id[qid] for qid in question_ids if qid in questions_by_id]

        # Sprint 66 — short_answer/essay can never be automatically
        # correct (is_correct stays NULL forever for them — see
        # save_answer()'s free-text branch above), so including them
        # here would only ever inflate total_possible without ever being
        # able to inflate total_score, silently deflating the automatic
        # percentage of any exam that contains one. Filter to the
        # automatically gradable subset BEFORE scoring — applied after
        # the effective (modular-aware) question set above has already
        # been resolved, so this does not touch or duplicate Sprint
        # 61/63's effective-question-set algorithm, only narrows its
        # output by question_type.
        auto_scored_questions = [q for q in questions if is_auto_gradable(q)]

        # Sprint 45 — delegates to the Scoring Strategy foundation
        # (scoring.py). DEFAULT_SCORING_STRATEGY.calculate() is the
        # exact same arithmetic this method used to do inline —
        # extracted, not changed. Sprint 61 — S61-C changed only WHICH
        # questions are passed in (see _effective_scoring_question_ids
        # above); the scoring arithmetic itself is untouched. Sprint 66
        # narrows the input further to auto_scored_questions (see above)
        # — the strategy itself has no notion of question_type.
        result = DEFAULT_SCORING_STRATEGY.calculate(auto_scored_questions, answers)

        self.repo.update(attempt, {
            "status": new_status.value, "finish_time": datetime.now(timezone.utc),
            "score": result.score, "percentage": result.percentage,
        })

    def _build_result(self, attempt: TestAttempt) -> SubmitResultOut:
        test = self.test_repo.get_by_id(attempt.test_id)
        answers = self.answer_repo.list_for_attempt(attempt.id)
        # Sprint 66 — deliberately UNCHANGED, documented semantic
        # limitation: total_questions below still means "all effective
        # exam questions" (auto-graded + short_answer/essay), NOT "the
        # auto-scored denominator" that _finalize() now uses for
        # score/percentage. correct_count needs no change either: it is
        # already computed from is_correct is True, and short_answer/
        # essay answers always have is_correct=None, so they were never
        # counted here regardless. Distinguishing "total exam questions"
        # from "auto-scored questions" as separate response fields would
        # be a result-schema change, which is explicitly out of scope
        # for this sprint (see scoring.py's AUTO_GRADABLE_QUESTION_TYPES
        # for where that distinction now lives). A caller that wants the
        # auto-scored denominator specifically has no field for it yet.
        #
        # Sprint 61 — S61-C. total_questions/correct_count must reflect
        # the SAME effective question set _finalize() scored against,
        # not the whole-test attempt.question_order — otherwise a
        # modular attempt's reported total_questions would still (as
        # before this sprint) overcount modules the student never saw,
        # even though score/percentage were already fixed. Filtering
        # correct_count by effective_question_ids is a no-op for every
        # existing (non-modular) case: save_answer() already only ever
        # creates an Answer for a question in attempt.question_order,
        # so answers and the non-modular effective set were always the
        # same set already.
        effective_question_ids = self._effective_scoring_question_ids(attempt)
        effective_id_set = set(effective_question_ids)
        correct_count = sum(1 for a in answers if a.is_correct is True and a.question_id in effective_id_set)
        is_passed = None
        if test is not None and test.passing_score is not None and attempt.percentage is not None:
            is_passed = float(attempt.percentage) >= float(test.passing_score)

        return SubmitResultOut(
            attempt_id=attempt.id, score=float(attempt.score or 0), percentage=float(attempt.percentage or 0),
            is_passed=is_passed, total_questions=len(effective_question_ids),
            correct_count=correct_count, status=attempt.status,
        )

    def _delivered_media_by_question(self, questions: list) -> dict:
        """Task 1 — one batched media fetch for questions that are
        already scoped to the attempt's current delivery. Media attached
        to a soft-deleted option is dropped, because that option is never
        delivered either. Returns {} when no media repository is wired."""
        if self.media_repo is None or not questions:
            return {}
        delivered_option_ids = {o.id for q in questions for o in q.options if o.deleted_at is None}
        by_question: dict = {}
        for m in self.media_repo.list_active_for_questions([q.id for q in questions]):
            if m.option_id is not None and m.option_id not in delivered_option_ids:
                continue
            by_question.setdefault(m.question_id, []).append(
                AttemptMediaOut(id=m.id, media_type=m.media_type, option_id=m.option_id)
            )
        return by_question

    def _to_question_view(self, question, groups_by_id: dict | None = None, media_by_question: dict | None = None,
                          capabilities: dict | None = None) -> QuestionForAttemptOut:
        calculator_enabled, accepts_audio = (capabilities or {}).get(question.id, (False, False))
        options = [OptionForAttemptOut.model_validate(o) for o in question.options if o.deleted_at is None]
        # Sprint 77 — group_by_id intentionally looked up here rather
        # than passed pre-resolved per question: a missing key (group
        # soft-deleted, group_repo not wired, or question.group_id is
        # None) all collapse to the same "ungrouped" view below, which
        # is exactly the safe default this question had before Sprint 77.
        group = (groups_by_id or {}).get(question.group_id) if question.group_id is not None else None
        return QuestionForAttemptOut(
            id=question.id, question_text=question.question_text,
            question_type=question.question_type, score=float(question.score), options=options,
            group_id=group.id if group is not None else None,
            group_title=group.title if group is not None else None,
            stimulus_text=group.stimulus_text if group is not None else None,
            media=(media_by_question or {}).get(question.id, []),
            # Task 3 — group.media is the relationship's active-only,
            # attach-ordered view; the group itself is already known to be
            # active and in this attempt's delivery scope (groups_by_id).
            group_media=[AttemptGroupMediaOut(id=m.id, media_type=m.media_type) for m in group.media] if group is not None else [],
            calculator_enabled=calculator_enabled, accepts_audio=accepts_audio,
        )
