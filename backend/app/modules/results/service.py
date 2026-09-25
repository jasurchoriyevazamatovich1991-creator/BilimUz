"""
Business logic for results, statistics, and the ranking CALCULATION
ENGINE ONLY — per the approved Sprint 7 scope, there is no public
leaderboard read endpoint here, just the recompute operation that
populates the `ranking` table for future use.

Reads AttemptRepository, AnswerRepository (attempts module) and
TestRepository (tests module) — all read-only, unmodified.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.core.audit import log_action
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.attempts.scoring import DEFAULT_SCORING_STRATEGY
from app.modules.results.exceptions import AttemptNotFinishedException, ResultNotFoundException
from app.modules.results.models import Result, ResultSection, Statistics
from app.modules.results.repository import RankingRepository, ResultRepository, ResultSectionRepository, StatisticsRepository
from app.modules.results.schemas import OptionReviewOut, QuestionReviewOut, ResultDetailOut, ResultListParams, ResultSectionOut
from app.modules.tests.repository import ExamSectionRepository, TestRepository

_FINISHED_ATTEMPT_STATUSES = ("submitted", "auto_finished")


class ResultService:
    def __init__(
        self,
        repository: ResultRepository,
        statistics_repository: StatisticsRepository,
        attempt_repository: AttemptRepository,
        answer_repository: AnswerRepository,
        test_repository: TestRepository,
        question_repository: "QuestionRepository",
        # Sprint 54 — both optional, default None, same backward-compat
        # reasoning already established for AttemptService's
        # module_execution_service/module_repository (Sprint 50): every
        # existing caller (this module's own unit tests, and any future
        # caller with no need for section scoring) that constructs
        # ResultService with only the original 6 arguments is completely
        # unaffected — create_result() below degrades to the exact
        # legacy (no-ResultSection) behavior when these are None.
        exam_section_repository: ExamSectionRepository | None = None,
        result_section_repository: ResultSectionRepository | None = None,
        # Sprint 63 — optional, default None, same backward-compat
        # reasoning already established above for
        # exam_section_repository/result_section_repository (Sprint 54):
        # every existing caller (this module's own unit tests) that
        # constructs ResultService with only the original 6 arguments is
        # completely unaffected — get_result_detail() below degrades to
        # the exact legacy (attempt.question_order) behavior when this
        # is None, identical to how it always behaved before this sprint.
        module_execution_service: ModuleExecutionService | None = None,
    ):
        self.repo = repository
        self.stats_repo = statistics_repository
        self.attempt_repo = attempt_repository
        self.answer_repo = answer_repository
        self.test_repo = test_repository
        self.question_repo = question_repository
        self.section_repo = exam_section_repository
        self.result_section_repo = result_section_repository
        self.module_execution = module_execution_service

    def create_result(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> Result:
        attempt = self.attempt_repo.get_by_id(attempt_id)
        if attempt is None or attempt.user_id != user_id:
            raise ResultNotFoundException("Urinish topilmadi")
        if attempt.status not in _FINISHED_ATTEMPT_STATUSES:
            raise AttemptNotFinishedException("Urinish hali yakunlanmagan")

        # Sprint 54 — acquired here, BEFORE the existing-Result check
        # and BEFORE creating Result/ResultSection below (ownership/
        # status validation above is unaffected — it only ever reads
        # immutable-once-set attempt fields, so it doesn't need the
        # lock). Real PostgreSQL row-lock (SELECT ... FOR UPDATE +
        # populate_existing=True) — the identical pattern Sprint 50's
        # CRITICAL-1 fix established for AttemptModuleProgress. A
        # second, concurrent create_result() call for the SAME
        # attempt_id blocks here until the first call's transaction
        # commits and releases the lock; it then re-checks for an
        # already-created Result under that same lock immediately
        # below, so it reliably observes the first call's now-committed
        # Result instead of racing past an unlocked existence check and
        # hitting Result.attempt_id's UNIQUE constraint as an unhandled
        # IntegrityError. Every existing caller (this module's own unit
        # tests, which mock attempt_repo and only ever stub get_by_id())
        # is unaffected: get_by_id_locked() is called here for its
        # locking side-effect only — attempt's already-read fields
        # (user_id/status/test_id/score/percentage) don't change
        # between the two calls within this same transaction.
        self.attempt_repo.get_by_id_locked(attempt_id)

        existing = self.repo.get_by_attempt_id(attempt_id)
        if existing:
            return existing

        test = self.test_repo.get_by_id(attempt.test_id)
        is_passed = None
        if test is not None and test.passing_score is not None and attempt.percentage is not None:
            is_passed = float(attempt.percentage) >= float(test.passing_score)

        result = Result(
            attempt_id=attempt_id, user_id=user_id, test_id=attempt.test_id,
            score=float(attempt.score or 0), percentage=float(attempt.percentage or 0), is_passed=is_passed,
        )
        self.repo.create(result)
        self._create_result_sections(result, attempt)
        self._update_statistics(user_id, test.subject_id if test else None, attempt_id, float(attempt.percentage or 0))
        log_action(self.repo.db, action="result.created", user_id=user_id, entity_type="result", entity_id=result.id)
        self.repo.commit()
        return result

    def _create_result_sections(self, result: Result, attempt) -> None:
        """Sprint 54 — generic section-level raw scoring foundation.
        A complete no-op for a non-modular test (self.section_repo is
        None — legacy ResultService construction — or the Test simply
        has zero ExamSection rows, every existing Physics/National
        Certificate test): zero ResultSection rows are created, and
        Result creation behaves byte-for-byte as before this sprint.

        Only ever called from create_result(), after that method has
        already acquired the locked TestAttempt row and confirmed no
        Result exists yet for this attempt — so this always runs
        exactly once per attempt, inside the same transaction as the
        Result insert above (both flushed here, committed together by
        create_result()'s own self.repo.commit()).

        Sections come ONLY from ExamSectionRepository.list_for_test(
        attempt.test_id) — never from any client-supplied section_id —
        so every section this loop ever sees already belongs to the
        correct test by construction. The explicit section.test_id
        check below is a defensive, not load-bearing, assertion of
        that invariant (never trust an ID without re-verifying its
        ownership, even one this method itself just fetched)."""
        if self.section_repo is None or self.result_section_repo is None:
            return

        sections = self.section_repo.list_for_test(attempt.test_id)
        if not sections:
            return

        answers = self.answer_repo.list_for_attempt(attempt.id)
        answers_by_question = {a.question_id: a for a in answers}

        for section in sections:
            if section.test_id != result.test_id:
                # Defensive only — see docstring above. Can't actually
                # happen since list_for_test() already scoped by
                # attempt.test_id == result.test_id, but a ResultSection
                # is never created for a section outside this Result's
                # own test, no matter what.
                continue

            questions = self.question_repo.list_by_section(section.id)
            section_answers = [answers_by_question[q.id] for q in questions if q.id in answers_by_question]

            # Same generic ScoringStrategy already used for the
            # whole-attempt score (AttemptService._finalize()) and for
            # module-scoped routing performance
            # (ModuleExecutionService.submit_module()) — no new
            # weighting formula, no exam-specific scoring.
            scoring_result = DEFAULT_SCORING_STRATEGY.calculate(questions, section_answers)

            self.result_section_repo.create(ResultSection(
                result_id=result.id, section_id=section.id,
                raw_score=scoring_result.score, scaled_score=None,
            ))

    def get_result(self, result_id: uuid.UUID, user_id: uuid.UUID) -> Result:
        result = self.repo.get_by_id(result_id)
        if result is None or result.user_id != user_id:
            raise ResultNotFoundException("Natija topilmadi")
        return result

    def _effective_result_question_ids(self, attempt) -> list[uuid.UUID]:
        """Sprint 63 — S63-A. Mirrors
        AttemptService._effective_scoring_question_ids() exactly (same
        module, same algorithm, no second implementation): delegates to
        ModuleExecutionService.get_effective_question_ids(), the single
        Sprint 61 helper that returns the deduplicated, order-preserving
        union of every AttemptModuleProgress.question_order row for this
        attempt, or None when there are no progress rows at all (a
        non-modular attempt, or a legacy ResultService construction with
        no module_execution_service wired) — in which case this falls
        back to the pre-Sprint-61 attempt.question_order, byte-for-byte
        the same value get_result_detail() always used before this
        sprint, so non-modular results are completely unaffected.

        Fixes the exact gap Sprint 61 left open: AttemptService's own
        _finalize()/_build_result() already used this effective scope,
        but ResultService.get_result_detail() (a separate, student-
        reachable endpoint, GET /results/{id}) kept using the raw,
        un-scoped attempt.question_order — so a modular attempt where a
        student was routed through only some modules could show a
        different total_questions/unanswered count here than on
        GET /attempts/{id}/result. This method is the only change
        needed to close that gap; Result.score/percentage themselves
        were already correct (copied verbatim from the already-fixed
        attempt.score/attempt.percentage at create_result() time,
        untouched by this sprint)."""
        if self.module_execution is not None:
            effective_ids = self.module_execution.get_effective_question_ids(attempt.id)
            if effective_ids is not None:
                return effective_ids
        return list(attempt.question_order or [])

    def get_result_detail(self, result_id: uuid.UUID, user_id: uuid.UUID) -> ResultDetailOut:
        """Sprint 37 — Result Analysis. Reuses get_result()'s own
        ownership check (a student can only ever reach their own
        attempt/answers from here, since attempt_id/question_ids below
        are all derived from THIS already-ownership-verified result,
        never from a client-supplied id).

        Sprint 63 — S63-A: question_ids now comes from
        _effective_result_question_ids() (the same Sprint 61 effective
        scope AttemptService already uses for finalization/scoring)
        instead of the raw attempt.question_order, so this endpoint's
        total_questions/unanswered/review-list agree with
        GET /attempts/{id}/result for the same modular attempt. Order
        is still the real, persisted delivery order (question_order
        itself for non-modular attempts; the module-traversal order
        AttemptModuleProgress rows were created in for modular ones) —
        never an arbitrary re-sort."""
        result = self.get_result(result_id, user_id)
        section_outs = self._get_result_sections(result)
        attempt = self.attempt_repo.get_by_id(result.attempt_id)
        answers = self.answer_repo.list_for_attempt(result.attempt_id)
        answers_by_question = {a.question_id: a for a in answers}

        question_ids = self._effective_result_question_ids(attempt) if attempt else list(answers_by_question.keys())
        questions = self.question_repo.list_by_ids(question_ids)
        questions_by_id = {q.id: q for q in questions}

        correct_count = 0
        incorrect_count = 0
        unanswered_count = 0
        question_reviews: list[QuestionReviewOut] = []

        for qid in question_ids:
            question = questions_by_id.get(qid)
            if question is None:
                continue  # question was hard-deleted after the attempt — skip rather than fabricate
            answer = answers_by_question.get(qid)

            if answer is None or answer.is_correct is None:
                unanswered_count += 1
            elif answer.is_correct:
                correct_count += 1
            else:
                incorrect_count += 1

            question_reviews.append(QuestionReviewOut(
                question_id=question.id, question_text=question.question_text,
                question_type=question.question_type, explanation=question.explanation,
                options=[OptionReviewOut(id=o.id, option_text=o.option_text, is_correct=o.is_correct) for o in question.options],
                selected_option=answer.selected_option if answer else None,
                selected_options=answer.selected_options if answer else None,
                is_correct=answer.is_correct if answer else None,
            ))

        time_spent_seconds = None
        if attempt is not None and attempt.finish_time is not None:
            time_spent_seconds = int((attempt.finish_time - attempt.start_time).total_seconds())

        return ResultDetailOut(
            id=result.id, attempt_id=result.attempt_id, user_id=result.user_id, test_id=result.test_id,
            score=result.score, percentage=result.percentage, is_passed=result.is_passed,
            status=result.status, created_at=result.created_at,
            total_questions=len(question_ids), correct_answers=correct_count,
            incorrect_answers=incorrect_count, unanswered=unanswered_count,
            time_spent_seconds=time_spent_seconds, questions=question_reviews,
            sections=section_outs,
        )

    def _get_result_sections(self, result: Result) -> list[ResultSectionOut]:
        """Sprint 55 — read-only exposure of Sprint 54's ResultSection
        rows. Called from get_result_detail() ONLY after
        get_result()'s own ownership check has already passed — every
        row this method returns is scoped strictly to `result.id`
        (ResultSectionRepository.list_for_result()), never to a
        client-supplied section_id, so there is no way for a caller to
        pull another Result's sections through this method.

        A no-op ([]) for a legacy ResultService construction
        (self.result_section_repo is None) and for any Result with zero
        ResultSection rows (every non-modular result, exactly as
        before this sprint) — GET /results/{id}'s existing fields and
        behavior are completely unchanged either way.

        Ordering: by the owning Test's ExamSection.order_number when
        available (ExamSectionRepository.list_for_test() already
        returns sections in that deterministic order — reused here
        rather than inventing a new ordering column, per this sprint's
        own constraint), falling back to ResultSection.id ordering if
        section_repo isn't wired (defensive; in practice both repos
        are always wired together by get_result_service())."""
        if self.result_section_repo is None:
            return []

        rows = self.result_section_repo.list_for_result(result.id)
        if not rows:
            return []

        if self.section_repo is not None:
            order_by_section_id = {s.id: s.order_number for s in self.section_repo.list_for_test(result.test_id)}
            rows = sorted(rows, key=lambda r: order_by_section_id.get(r.section_id, 0))
        else:
            rows = sorted(rows, key=lambda r: r.id)

        return [ResultSectionOut.model_validate(r) for r in rows]

    def list_my_results(self, user_id: uuid.UUID, params: ResultListParams) -> tuple[list[Result], int]:
        return self.repo.list_for_user(user_id, params.page, params.per_page, params.test_id, params.sort)

    def _update_statistics(self, user_id: uuid.UUID, subject_id: uuid.UUID | None, attempt_id: uuid.UUID, percentage: float) -> None:
        answers = self.answer_repo.list_for_attempt(attempt_id)
        correct = sum(1 for a in answers if a.is_correct is True)
        wrong = sum(1 for a in answers if a.is_correct is False)

        stats = self.stats_repo.get_by_user_and_subject(user_id, subject_id)
        if stats is None:
            self.stats_repo.create(Statistics(
                user_id=user_id, subject_id=subject_id, tests_taken=1,
                correct_answers=correct, wrong_answers=wrong, avg_score=percentage,
            ))
            return

        new_count = stats.tests_taken + 1
        new_avg = ((float(stats.avg_score or 0) * stats.tests_taken) + percentage) / new_count
        self.stats_repo.update(stats, {
            "tests_taken": new_count,
            "correct_answers": stats.correct_answers + correct,
            "wrong_answers": stats.wrong_answers + wrong,
            "avg_score": round(new_avg, 2),
        })


class RankingService:
    """The ranking CALCULATION ENGINE — computes and persists `ranking`
    rows. Deliberately has no 'get ranking' method: reading the computed
    leaderboard is out of Sprint 7 scope per the approved architecture
    (docs/Sprint7_..._Architecture.md, 'Outstanding' section)."""

    def __init__(self, repository: RankingRepository, result_repository: ResultRepository, attempt_repository: AttemptRepository):
        self.repo = repository
        self.result_repo = result_repository
        self.attempt_repo = attempt_repository

    def recompute(self, subject_id: uuid.UUID | None, period: str) -> int:
        results = self._results_in_period(subject_id, period)
        best_per_user = self._pick_best_result_per_user(results)
        ranked = self._sort_with_tiebreak(best_per_user)

        for position, (user_id, percentage, _duration, _completed_at) in enumerate(ranked, start=1):
            self.repo.upsert(user_id, subject_id, period, percentage, position)
        self.repo.commit()
        return len(ranked)

    def _results_in_period(self, subject_id: uuid.UUID | None, period: str) -> list[Result]:
        all_results = self.result_repo.list_for_subject(subject_id)
        if period == "all_time":
            return all_results
        cutoff = self._period_cutoff(period)
        return [r for r in all_results if r.created_at >= cutoff]

    def _period_cutoff(self, period: str) -> datetime:
        now = datetime.now(timezone.utc)
        if period == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "weekly":
            start_of_week = now - timedelta(days=now.weekday())
            return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "monthly":
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return datetime.min.replace(tzinfo=timezone.utc)

    def _pick_best_result_per_user(self, results: list[Result]) -> dict:
        best: dict = {}
        for r in results:
            current = best.get(r.user_id)
            if current is None or float(r.percentage) > float(current.percentage):
                best[r.user_id] = r
        return best

    def _sort_with_tiebreak(self, best_per_user: dict) -> list[tuple]:
        """Tie-break order (approved): higher score -> shorter completion
        time -> earlier completed_at."""
        candidates = []
        for user_id, result in best_per_user.items():
            attempt = self.attempt_repo.get_by_id(result.attempt_id)
            duration = (attempt.finish_time - attempt.start_time) if (attempt and attempt.finish_time) else timedelta.max
            completed_at = attempt.finish_time if (attempt and attempt.finish_time) else datetime.max.replace(tzinfo=timezone.utc)
            candidates.append((user_id, float(result.percentage), duration, completed_at))

        return sorted(candidates, key=lambda c: (-c[1], c[2], c[3]))
