import { DashboardCard } from "@/components/layout/DashboardCard";

export function TeacherDashboardPage() {
  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <DashboardCard title="Mening testlarim" />
        <DashboardCard title="So'nggi natijalar" />
        <DashboardCard title="Statistika" />
      </div>
    </div>
  );
}
