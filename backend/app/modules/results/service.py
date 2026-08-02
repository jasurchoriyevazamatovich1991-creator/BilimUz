"""
Business logic for results, statistics, and the ranking CALCULATION
ENGINE ONLY — per the approved Sprint 7 scope, there is no public
leaderboard read endpoint here, just the recompute operation that
populates the `ranking` table for future use.

Reads AttemptRepository, AnswerRepository (attempts module) and
TestRepository (tests module) — all read-only, unmodified.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from app.core.audit import log_action
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.results.exceptions import AttemptNotFinishedException, ResultNotFoundException
from app.modules.results.models import Result, Statistics
from app.modules.results.repository import RankingRepository, ResultRepository, StatisticsRepository
from app.modules.results.schemas import ResultListParams
from app.modules.tests.repository import TestRepository

_FINISHED_ATTEMPT_STATUSES = ("submitted", "auto_finished")


class ResultService:
    def __init__(
        self,
        repository: ResultRepository,
        statistics_repository: StatisticsRepository,
        attempt_repository: AttemptRepository,
        answer_repository: AnswerRepository,
        test_repository: TestRepository,
    ):
        self.repo = repository
        self.stats_repo = statistics_repository
        self.attempt_repo = attempt_repository
        self.answer_repo = answer_repository
        self.test_repo = test_repository

    def create_result(self, attempt_id: uuid.UUID, user_id: uuid.UUID) -> Result:
        attempt = self.attempt_repo.get_by_id(attempt_id)
        if attempt is None or attempt.user_id != user_id:
            raise ResultNotFoundException("Urinish topilmadi")
        if attempt.status not in _FINISHED_ATTEMPT_STATUSES:
            raise AttemptNotFinishedException("Urinish hali yakunlanmagan")

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
        self._update_statistics(user_id, test.subject_id if test else None, attempt_id, float(attempt.percentage or 0))
        log_action(self.repo.db, action="result.created", user_id=user_id, entity_type="result", entity_id=result.id)
        self.repo.commit()
        return result

    def get_result(self, result_id: uuid.UUID, user_id: uuid.UUID) -> Result:
        result = self.repo.get_by_id(result_id)
        if result is None or result.user_id != user_id:
            raise ResultNotFoundException("Natija topilmadi")
        return result

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
