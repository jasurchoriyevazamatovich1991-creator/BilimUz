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
import { UsersListPage } from "@/pages/admin/UsersListPage";
import { UserDetailPage } from "@/pages/admin/UserDetailPage";
import { SchoolsListPage } from "@/pages/admin/SchoolsListPage";
import { SchoolFormPage } from "@/pages/admin/SchoolFormPage";
import { LearningCentersListPage } from "@/pages/admin/LearningCentersListPage";
import { LearningCenterFormPage } from "@/pages/admin/LearningCenterFormPage";
import { SubjectsListPage } from "@/pages/admin/SubjectsListPage";
import { SubjectFormPage } from "@/pages/admin/SubjectFormPage";
import { GradesListPage } from "@/pages/admin/GradesListPage";
import { GradeFormPage } from "@/pages/admin/GradeFormPage";
import { TopicsListPage } from "@/pages/admin/TopicsListPage";
import { TopicFormPage } from "@/pages/admin/TopicFormPage";
import { LessonsListPage } from "@/pages/admin/LessonsListPage";
import { LessonFormPage } from "@/pages/admin/LessonFormPage";
import { TestsListPage } from "@/pages/admin/TestsListPage";
import { TestFormPage } from "@/pages/admin/TestFormPage";
import { TestQuestionsListPage } from "@/pages/admin/TestQuestionsListPage";
import { QuestionFormPage } from "@/pages/admin/QuestionFormPage";
import { TeacherDashboardPage } from "@/pages/teacher/DashboardPage";
import { StudentDashboardPage } from "@/pages/student/DashboardPage";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";
import { ProtectedRoute } from "./ProtectedRoute";
import { ADMIN_ITEMS, TEACHER_ITEMS, APPLICANT_STUDENT_ITEMS } from "@/utils/sidebarConfig";
import type { SidebarItem } from "@/utils/sidebarConfig";

/** Renders every non-dashboard sidebar item as a <Route> pointing at
 * PlaceholderPage — the dashboard item (index route) is handled
 * separately by the caller, since it needs the real dashboard
 * component, not a placeholder. `excludePaths` lets a caller opt a
 * path out entirely once it has a real page (Sprint 15: "/admin/users"),
 * without needing to remove it from ADMIN_ITEMS (the sidebar label/path
 * itself is unchanged — only which component renders it changes). */
function placeholderRoutesFor(items: SidebarItem[], basePath: string, excludePaths: string[] = []) {
  return items
    .filter((item) => item.path !== basePath && !excludePaths.includes(item.path))
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
          <Route path="/admin/users" element={<UsersListPage />} />
          <Route path="/admin/users/:userId" element={<UserDetailPage />} />
          <Route path="/admin/schools" element={<SchoolsListPage />} />
          <Route path="/admin/schools/new" element={<SchoolFormPage />} />
          <Route path="/admin/schools/:schoolId" element={<SchoolFormPage />} />
          <Route path="/admin/learning-centers" element={<LearningCentersListPage />} />
          <Route path="/admin/learning-centers/new" element={<LearningCenterFormPage />} />
          <Route path="/admin/learning-centers/:centerId" element={<LearningCenterFormPage />} />
          <Route path="/admin/subjects" element={<SubjectsListPage />} />
          <Route path="/admin/subjects/new" element={<SubjectFormPage />} />
          <Route path="/admin/subjects/:subjectId" element={<SubjectFormPage />} />
          <Route path="/admin/grades" element={<GradesListPage />} />
          <Route path="/admin/grades/new" element={<GradeFormPage />} />
          <Route path="/admin/grades/:gradeId" element={<GradeFormPage />} />
          <Route path="/admin/topics" element={<TopicsListPage />} />
          <Route path="/admin/topics/new" element={<TopicFormPage />} />
          <Route path="/admin/topics/:topicId" element={<TopicFormPage />} />
          <Route path="/admin/lessons" element={<LessonsListPage />} />
          <Route path="/admin/lessons/new" element={<LessonFormPage />} />
          <Route path="/admin/lessons/:lessonId" element={<LessonFormPage />} />
          <Route path="/admin/tests" element={<TestsListPage />} />
          <Route path="/admin/tests/new" element={<TestFormPage />} />
          <Route path="/admin/tests/:testId" element={<TestFormPage />} />
          <Route path="/admin/tests/:testId/questions" element={<TestQuestionsListPage />} />
          <Route path="/admin/tests/:testId/questions/new" element={<QuestionFormPage />} />
          <Route path="/admin/tests/:testId/questions/:questionId" element={<QuestionFormPage />} />
          {placeholderRoutesFor(ADMIN_ITEMS, "/admin", [
            "/admin/users",
            "/admin/schools",
            "/admin/learning-centers",
            "/admin/subjects",
            "/admin/grades",
            "/admin/topics",
            "/admin/lessons",
            "/admin/tests",
          ])}
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
