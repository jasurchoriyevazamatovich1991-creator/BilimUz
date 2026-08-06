import { DashboardCard } from "@/components/layout/DashboardCard";

export function AdminDashboardPage() {
  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-foreground">Boshqaruv paneli</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardCard title="Foydalanuvchilar" />
        <DashboardCard title="Faol testlar" />
        <DashboardCard title="Bugungi urinishlar" />
        <DashboardCard title="To'lovlar (oy)" />
      </div>
    </div>
  );
}
