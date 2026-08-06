/**
 * Dashboard data hooks, one per role — each wraps a real backend
 * endpoint (see api/*.ts files, every shape verified against backend
 * source before writing). On error: triggers the existing global toast
 * (approved decision — NOT a new toast system) IN ADDITION to the
 * widget's own inline error state — both together, not either/or.
 *
 * Toast triggering happens in useEffect, NOT directly in the render
 * body — calling a state-mutating store action during render is an
 * anti-pattern (would re-fire on every re-render while isError stays
 * true, spamming duplicate toasts).
 */
import { useEffect } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { usersApi } from "@/api/users";
import { testsApi } from "@/api/tests";
import { subjectsApi } from "@/api/subjects";
import { resultsApi } from "@/api/results";
import { attemptsApi } from "@/api/attempts";
import { aiApi } from "@/api/ai";
import { schoolsApi } from "@/api/schools";
import { learningCentersApi } from "@/api/learningCenters";
import { lessonsApi } from "@/api/lessons";
import { certificatesApi } from "@/api/certificates";
import { paymentsApi } from "@/api/payments";
import { useToastStore } from "@/store/toastStore";
import { ApiError } from "@/api/client";

function useToastOnQueryError(query: UseQueryResult<unknown, unknown>) {
  const addToast = useToastStore((s) => s.addToast);

  useEffect(() => {
    if (query.isError) {
      const message = query.error instanceof ApiError ? query.error.message : "Ma'lumot yuklanmadi";
      addToast(message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.isError, query.error]);
}

/**
 * Super Admin: Users, Schools, Learning Centers, Subjects, Tests,
 * Payments, Results — per the approved widget list. "Payments" and
 * "Natijalar" have NO admin-wide backend endpoint (verified — only
 * /me-scoped or catalog-only endpoints exist); "Payments" is real data
 * from a different, honestly-labeled source (active plan count, not
 * transaction volume — see api/payments.ts), "Natijalar" has no
 * substitute and is flagged unavailable (see AdminDashboardPage.tsx).
 */
export function useAdminDashboardStats() {
  const usersCount = useQuery({ queryKey: ["dashboard", "admin", "users-count"], queryFn: usersApi.count });
  const schoolsCount = useQuery({ queryKey: ["dashboard", "admin", "schools-count"], queryFn: schoolsApi.count });
  const learningCentersCount = useQuery({
    queryKey: ["dashboard", "admin", "learning-centers-count"],
    queryFn: learningCentersApi.count,
  });
  const subjectsCount = useQuery({ queryKey: ["dashboard", "admin", "subjects-count"], queryFn: subjectsApi.count });
  const testsCount = useQuery({ queryKey: ["dashboard", "admin", "tests-count"], queryFn: testsApi.publishedCount });
  const activePlansCount = useQuery({
    queryKey: ["dashboard", "admin", "active-plans-count"],
    queryFn: paymentsApi.activePlansCount,
  });

  useToastOnQueryError(usersCount);
  useToastOnQueryError(schoolsCount);
  useToastOnQueryError(learningCentersCount);
  useToastOnQueryError(subjectsCount);
  useToastOnQueryError(testsCount);
  useToastOnQueryError(activePlansCount);

  return { usersCount, schoolsCount, learningCentersCount, subjectsCount, testsCount, activePlansCount };
}

/** Teacher: Subjects, Lessons, Tests, Natijalar (own — see
 * TeacherDashboardPage.tsx's note on what "own" means here, since
 * /results/me is scoped to the logged-in user regardless of role). */
export function useTeacherDashboardStats() {
  const subjectsCount = useQuery({ queryKey: ["dashboard", "teacher", "subjects-count"], queryFn: subjectsApi.count });
  const lessonsCount = useQuery({ queryKey: ["dashboard", "teacher", "lessons-count"], queryFn: lessonsApi.count });
  const testsCount = useQuery({ queryKey: ["dashboard", "teacher", "tests-count"], queryFn: testsApi.publishedCount });
  const resultsCount = useQuery({ queryKey: ["dashboard", "teacher", "results-count"], queryFn: resultsApi.myCount });

  useToastOnQueryError(subjectsCount);
  useToastOnQueryError(lessonsCount);
  useToastOnQueryError(testsCount);
  useToastOnQueryError(resultsCount);

  return { subjectsCount, lessonsCount, testsCount, resultsCount };
}

/**
 * Student/Applicant: "Assigned Tests", Results, Certificates. There is
 * no "assignment" concept anywhere in the backend schema (verified) —
 * the closest real data is the same published-tests catalog every
 * authenticated user sees, so the widget is labeled "Mavjud testlar"
 * (Available tests), not "Biriktirilgan" (Assigned), to avoid implying
 * a targeting feature that doesn't exist.
 */
export function useStudentDashboardStats() {
  const availableTestsCount = useQuery({
    queryKey: ["dashboard", "student", "available-tests-count"],
    queryFn: testsApi.publishedCount,
  });
  const resultsCount = useQuery({ queryKey: ["dashboard", "student", "results-count"], queryFn: resultsApi.myCount });
  const certificatesCount = useQuery({
    queryKey: ["dashboard", "student", "certificates-count"],
    queryFn: certificatesApi.myCount,
  });

  useToastOnQueryError(availableTestsCount);
  useToastOnQueryError(resultsCount);
  useToastOnQueryError(certificatesCount);

  return { availableTestsCount, resultsCount, certificatesCount };
}
