import { DashboardCard } from "@/components/layout/DashboardCard";

/**
 * Shared by Student and Applicant (same layout, per ui_ux_blueprint.md
 * §4.1's card-row pattern: "Faol testlar / So'nggi natijalar / Tavsiya
 * etilgan mavzular"). The AI-recommendation card legitimately shows an
 * empty state this sprint — the `ai` module's own README confirms
 * nothing generates a recommendation yet (no real provider exists) —
 * not faked here either.
 */
export function StudentDashboardPage() {
  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <DashboardCard title="Faol testlar" />
        <DashboardCard title="So'nggi natijalar" />
        <DashboardCard title="Tavsiya etilgan mavzular" isLoading={false} />
      </div>
    </div>
  );
}
