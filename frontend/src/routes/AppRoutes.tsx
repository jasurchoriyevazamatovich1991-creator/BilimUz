import { Route, Routes } from "react-router-dom";
import { PublicLayout } from "@/layouts/PublicLayout";
import { AdminLayout } from "@/layouts/AdminLayout";
import { TeacherLayout } from "@/layouts/TeacherLayout";
import { StudentLayout } from "@/layouts/StudentLayout";
import { HomePage } from "@/pages/public/HomePage";
import { LoginPage } from "@/pages/public/LoginPage";
import { RegisterPage } from "@/pages/public/RegisterPage";
import { VerifyPage } from "@/pages/public/VerifyPage";
import { UnsupportedRolePage } from "@/pages/public/UnsupportedRolePage";
import { AdminDashboardPage } from "@/pages/admin/DashboardPage";
import { TeacherDashboardPage } from "@/pages/teacher/DashboardPage";
import { StudentDashboardPage } from "@/pages/student/DashboardPage";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";
import { ProtectedRoute } from "./ProtectedRoute";
import { ADMIN_ITEMS, TEACHER_ITEMS, APPLICANT_STUDENT_ITEMS } from "@/utils/sidebarConfig";
import type { SidebarItem } from "@/utils/sidebarConfig";

/** Renders every non-dashboard sidebar item as a <Route> pointing at
 * PlaceholderPage — the dashboard item (index route) is handled
 * separately by the caller, since it needs the real dashboard
 * component, not a placeholder. */
function placeholderRoutesFor(items: SidebarItem[], basePath: string) {
  return items
    .filter((item) => item.path !== basePath)
    .map((item) => {
      const relativePath = item.path.slice(basePath.length + 1); // strip "/admin/" etc.
      return <Route key={item.path} path={relativePath} element={<PlaceholderPage title={item.label} />} />;
    });
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route element={<PublicLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify" element={<VerifyPage />} />
        <Route path="/unsupported" element={<UnsupportedRolePage />} />
      </Route>

      {/* Admin (Super Admin, Admin, Moderator per roleConfig.ts) */}
      <Route element={<ProtectedRoute allowedPanel="admin" />}>
        <Route element={<AdminLayout />}>
          <Route path="/admin" element={<AdminDashboardPage />} />
          {placeholderRoutesFor(ADMIN_ITEMS, "/admin")}
        </Route>
      </Route>

      {/* Teacher */}
      <Route element={<ProtectedRoute allowedPanel="teacher" />}>
        <Route element={<TeacherLayout />}>
          <Route path="/teacher" element={<TeacherDashboardPage />} />
          {placeholderRoutesFor(TEACHER_ITEMS, "/teacher")}
        </Route>
      </Route>

      {/* Student (Student, Applicant per roleConfig.ts — same layout,
          different sidebar content, see sidebarConfig.ts) */}
      <Route element={<ProtectedRoute allowedPanel="student" />}>
        <Route element={<StudentLayout />}>
          <Route path="/student" element={<StudentDashboardPage />} />
          {placeholderRoutesFor(APPLICANT_STUDENT_ITEMS, "/student")}
        </Route>
      </Route>
    </Routes>
  );
}
