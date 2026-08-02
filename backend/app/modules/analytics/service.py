"""
Business logic for analytics — fully independent module. Reads
ResultRepository (results module) and, transitively, AnswerRepository
(attempts module, via each result's attempt_id) — both read-only, both
unmodified. NEVER written to by results (per the approved architecture
decision). Both recompute operations are explicit/Admin-triggered — no
background worker exists yet.

Why AnswerRepository too, not just Results: `results` rows carry
score/percentage but not per-question correct/wrong counts (those live
on `answers`, owned by `attempts`). "Calculate statistics from Results"
is implemented here as "from the Results dataset and the attempt data
each Result directly references" — the only way to populate
daily_statistics.correct_answers/wrong_answers with real numbers instead
of a fake placeholder.
"""
import uuid
from calendar import monthrange
from collections import defaultdict
from datetime import date

from app.modules.analytics.models import DailyStatistics
from app.modules.analytics.repository import DailyStatisticsRepository, MonthlyStatisticsRepository
from app.modules.attempts.repository import AnswerRepository
from app.modules.results.repository import ResultRepository
from app.modules.tests.repository import TestRepository


class AnalyticsService:
    def __init__(
        self,
        daily_repository: DailyStatisticsRepository,
        monthly_repository: MonthlyStatisticsRepository,
        result_repository: ResultRepository,
        answer_repository: AnswerRepository,
        test_repository: TestRepository,
    ):
        self.daily_repo = daily_repository
        self.monthly_repo = monthly_repository
        self.result_repo = result_repository
        self.answer_repo = answer_repository
        self.test_repo = test_repository

    def get_my_daily(self, user_id: uuid.UUID, start: date, end: date, subject_id: uuid.UUID | None) -> list[DailyStatistics]:
        return self.daily_repo.list_for_user(user_id, start, end, subject_id)

    def get_my_monthly(self, user_id: uuid.UUID):
        return self.monthly_repo.list_for_user(user_id)

    def recompute_daily(self, start: date, end: date) -> int:
        """Delete-and-rebuild for the window — always correct on re-run,
        no double-counting regardless of how many times it's called."""
        results = self.result_repo.list_in_date_range(start, end)
        subject_by_test = self._build_subject_cache(results)
        buckets = self._group_by_day(results, subject_by_test)

        self.daily_repo.delete_for_range(start, end)
        for (user_id, subject_id, stat_date), counts in buckets.items():
            self.daily_repo.create(DailyStatistics(
                user_id=user_id, subject_id=subject_id, stat_date=stat_date,
                tests_taken=counts["tests_taken"], correct_answers=counts["correct"], wrong_answers=counts["wrong"],
            ))
        self.daily_repo.commit()
        return len(buckets)

    def recompute_monthly(self, month: int, year: int) -> int:
        monthrange(year, month)  # validates the (year, month) combination is real
        daily_rows = self.daily_repo.list_for_month(year, month)
        grouped = self._sum_daily_by_user_subject(daily_rows)

        for (user_id, subject_id), tests_taken in grouped.items():
            self.monthly_repo.upsert(user_id, subject_id, month, year, tests_taken, avg_score=0)
        self.monthly_repo.commit()
        return len(grouped)

    def _build_subject_cache(self, results) -> dict:
        """One lookup per distinct test_id, not per result — avoids N+1
        when many results share the same test."""
        cache: dict = {}
        for r in results:
            if r.test_id not in cache:
                test = self.test_repo.get_by_id(r.test_id)
                cache[r.test_id] = test.subject_id if test else None
        return cache

    def _group_by_day(self, results, subject_by_test: dict) -> dict:
        buckets: dict = defaultdict(lambda: {"tests_taken": 0, "correct": 0, "wrong": 0})
        for r in results:
            subject_id = subject_by_test.get(r.test_id)
            key = (r.user_id, subject_id, r.created_at.date())
            answers = self.answer_repo.list_for_attempt(r.attempt_id)
            buckets[key]["tests_taken"] += 1
            buckets[key]["correct"] += sum(1 for a in answers if a.is_correct is True)
            buckets[key]["wrong"] += sum(1 for a in answers if a.is_correct is False)
        return buckets

    def _sum_daily_by_user_subject(self, daily_rows) -> dict:
        grouped: dict = defaultdict(int)
        for row in daily_rows:
            grouped[(row.user_id, row.subject_id)] += row.tests_taken
        return grouped
