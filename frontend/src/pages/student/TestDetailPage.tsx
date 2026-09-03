/**
 * Approved decision 3: before showing "Boshlash", checks
 * GET /attempts/me?test_id=X&status=in_progress (useActiveAttemptForTest)
 * — if a real active attempt exists, shows "Davom ettirish" instead and
 * navigates straight to it, never calling start() again. start_attempt
 * itself does NOT do this check (verified in the Sprint 20 audit) — the
 * frontend is the one responsible for this, not an invented backend
 * behavior.
 */
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { useTest } from "@/hooks/useTests";
import { useActiveAttemptForTest, useStartAttempt } from "@/hooks/useAttempt";

export function StudentTestDetailPage() {
  const { testId } = useParams<{ testId: string }>();
  const navigate = useNavigate();

  const { data: test, isLoading, isError } = useTest(testId);
  const { data: activeAttempts, isLoading: isCheckingActive } = useActiveAttemptForTest(testId);
  const startAttempt = useStartAttempt();

  if (!testId) return null;
  if (isError) return <ErrorState title="Test" />;
  if (isLoading || !test) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  const activeAttempt = activeAttempts?.items[0];

  function handleStart() {
    if (!testId) return;
    startAttempt.mutate(testId, {
      onSuccess: (attempt) => navigate(`/student/tests/${testId}/attempt/${attempt.id}`),
    });
  }

  function handleContinue() {
    if (!activeAttempt) return;
    navigate(`/student/tests/${testId}/attempt/${activeAttempt.id}`);
  }

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/student/tests")} className="mb-4 text-sm text-primary hover:underline">
        ← Testlarga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{test.title}</CardTitle>
        </CardHeader>
        <CardContent>
          {test.description ? <p className="mb-4 text-sm text-foreground/70">{test.description}</p> : null}
          <dl className="mb-6 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-foreground/50">Savollar soni</dt>
              <dd className="font-medium text-foreground">{test.question_count}</dd>
            </div>
            <div>
              <dt className="text-foreground/50">Davomiyligi</dt>
              <dd className="font-medium text-foreground">{test.duration} daqiqa</dd>
            </div>
            {test.passing_score != null ? (
              <div>
                <dt className="text-foreground/50">O'tish bali</dt>
                <dd className="font-medium text-foreground">{test.passing_score}%</dd>
              </div>
            ) : null}
          </dl>

          {isCheckingActive ? (
            <p className="text-sm text-foreground/50">Tekshirilmoqda...</p>
          ) : activeAttempt ? (
            <Button onClick={handleContinue}>Davom ettirish</Button>
          ) : (
            <Button onClick={handleStart} disabled={startAttempt.isPending}>
              {startAttempt.isPending ? "Boshlanmoqda..." : "Boshlash"}
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
