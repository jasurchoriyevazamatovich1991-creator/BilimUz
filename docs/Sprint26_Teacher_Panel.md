# Sprint 26 — Teacher Panel

**Status: READY FOR REVIEW**

## 1. Architecture Audit (performed before implementation)

Verified directly against backend `require_roles()` calls on every relevant router:

| Module | Write RBAC | Teacher can write? |
|---|---|---|
| Subjects | `Admin, Super Admin` | ❌ Read-only |
| Grades | `Admin, Super Admin` | ❌ Read-only |
| Topics | `Admin, Super Admin, Teacher` | ✅ |
| Lessons | `Admin, Super Admin, Teacher` | ✅ |
| Tests | `Admin, Super Admin, Teacher` | ✅ |
| Questions (+ Options/Media) | `Admin, Super Admin, Teacher` | ✅ |

No `teacher_id`/`created_by` ownership column exists on Topics, Lessons, or Tests models (verified directly) — Teacher manages the same platform-wide content pool Admin does, not a personal subset. This shaped every design decision below (no fabricated "my content" filtering was invented).

Sprint 25's finding was confirmed exactly: the backend RBAC for Topics/Lessons/Tests/Questions already granted Teacher write access — the gap was **100% a missing frontend UI**, not a backend limitation.

## 2. Backend APIs Used

No new endpoint. Every Teacher page calls the exact same endpoints Admin's pages already use:

| Frontend API | Backend Endpoint | Method | Permission |
|---|---|---|---|
| `subjectsApi.list` | `/subjects` | GET | Admin, Super Admin, Teacher (read) |
| `gradesApi.list` | `/grades` | GET | Admin, Super Admin, Teacher (read) |
| `topicsApi.*` | `/topics`, `/topics/{id}` | GET/POST/PATCH/DELETE | Admin, Super Admin, Teacher (write) |
| `lessonsApi.*` | `/lessons`, `/lessons/{id}` | GET/POST/PATCH/DELETE | Admin, Super Admin, Teacher (write) |
| `testsApi.*` | `/tests`, `/tests/{id}`, `/tests/{id}/publish` | GET/POST/PATCH/DELETE | Admin, Super Admin, Teacher (write) |
| `questionsApi.*` | `/questions`, options/media sub-resources | GET/POST/PATCH/DELETE | Admin, Super Admin, Teacher (write) |

## 3. Teacher Routes Created

```
/teacher                                          (real Dashboard, was PlaceholderPage)
/teacher/subjects                                 (new, read-only)
/teacher/grades                                   (new, read-only)
/teacher/topics                                   (reuses TopicsListPage, basePath="/teacher")
/teacher/topics/new                               (reuses TopicFormPage, basePath="/teacher")
/teacher/topics/:topicId                          (reuses TopicFormPage, basePath="/teacher")
/teacher/lessons                                  (reuses LessonsListPage, basePath="/teacher")
/teacher/lessons/new                              (reuses LessonFormPage, basePath="/teacher")
/teacher/lessons/:lessonId                        (reuses LessonFormPage, basePath="/teacher")
/teacher/tests                                    (reuses TestsListPage, basePath="/teacher")
/teacher/tests/new                                (reuses TestFormPage, basePath="/teacher")
/teacher/tests/:testId                            (reuses TestFormPage, basePath="/teacher")
/teacher/tests/:testId/questions                  (reuses TestQuestionsListPage, basePath="/teacher")
/teacher/tests/:testId/questions/new              (reuses QuestionFormPage, basePath="/teacher")
/teacher/tests/:testId/questions/:questionId      (reuses QuestionFormPage, basePath="/teacher")
```

## 4. Pages Created

**New files**: `pages/teacher/SubjectsPage.tsx`, `pages/teacher/GradesPage.tsx` (both read-only), plus `pages/teacher/DashboardPage.tsx` rewritten in place (was a bare `PlaceholderPage` since Sprint 13) to show real platform-wide counts (Topics/Lessons/Tests/Questions via `meta.total` — the same pattern used everywhere else in the project, no fabricated numbers).

**Modified, additive-only** (see §5 for the exact mechanism): `TopicsListPage.tsx`, `TopicFormPage.tsx`, `LessonsListPage.tsx`, `LessonFormPage.tsx`, `TestsListPage.tsx`, `TestFormPage.tsx`, `TestQuestionsListPage.tsx`, `QuestionFormPage.tsx`.

## 5. Components Reused

**The core architectural decision of this sprint**: rather than duplicating ~8 large, complex CRUD page files for Teacher, each of the 8 files above gained one optional prop:

```ts
interface XProps { basePath?: string }
export function X({ basePath = "/admin" }: XProps) { ... }
```

Every hardcoded `navigate("/admin/...")` call inside these files was changed to `navigate(\`${basePath}/...\`)`. The default value (`"/admin"`) means **every existing Admin call site, with zero props passed, behaves byte-for-byte identically to before this sprint** — verified by re-running the full pre-existing test suite (194 tests) with zero failures before writing a single new test. Teacher's routes then mount the exact same components with `basePath="/teacher"`.

This was chosen deliberately over full duplication ("avoid copy-paste duplication where reasonable") and over a larger shared-abstraction refactor ("do NOT create dangerous shared abstractions that could break Admin pages, prefer small safe reuse") — a single optional string prop is the smallest possible change that enables genuine reuse without altering any existing behavior.

`ConfirmDialog`, `StatusBadge`, `ErrorState`, `DashboardCard`, `Button`, `Input`, `Card` — all reused unchanged, no new shared component needed.

## 6. RBAC Verification

- `ProtectedRoute allowedPanel="teacher"` wraps every new route — same mechanism as Admin/Student, no new guard pattern.
- Frontend `canWrite` checks inside the reused components (`role === "Admin" || "Super Admin" || "Teacher"` for Topics/Lessons/Tests/Questions) already existed and are unchanged — Teacher correctly sees write controls there.
- `TeacherSubjectsPage`/`TeacherGradesPage` render **no write controls at all** (no Create button, no Delete link anywhere in the JSX) — matching the confirmed backend read-only restriction, not just hidden-but-present controls.
- Backend remains the actual authorization boundary throughout — unchanged, unmodified.
- Users/Schools/Learning Centers/Roles/Permissions were **not** added to the Teacher sidebar or routes.

## 7. Test Results

```
Test Files: 39 passed (39)
Tests:      203 passed (203)
```

9 new tests: `TeacherDashboardPage.test.tsx` (2 — real counts, loading state), `TeacherSubjectsPage.test.tsx` (3 — success/empty/error, no write controls), `TeacherGradesPage.test.tsx` (2 — success/empty, no write controls), plus 2 new cases appended to `TopicsListPage.test.tsx` confirming the `basePath` prop: defaults to `/admin` (Admin behavior unchanged) and correctly navigates to `/teacher/topics/new` when `basePath="/teacher"` is passed. All 194 pre-existing tests (Sprint 13–25) still pass unmodified.

## 8. TypeScript Result

```
PASS
```

(One real issue was caught and fixed during this sprint: two new test files' mock `GradeOut`/`SubjectOut` objects were initially missing the required `created_at`/`updated_at` fields — `tsc -b`'s real build step caught this even though `vitest` itself doesn't type-check test bodies; fixed by completing the mock objects, not by weakening any type.)

## 9. Build Result

```
PASS (dist/ produced, 255 modules — up from 252 in Sprint 24)
```

## 10. Responsive QA

New Teacher pages reuse the exact same table/card/form patterns already responsive across Admin (`overflow-x-auto` on all tables, `sm:/lg:grid-cols` on the dashboard grid) — no new responsive architecture needed, verified present in all 3 new page files.

## 11. Accessibility QA

Reused components already carry their established accessibility properties (visible focus rings from Sprint 24's Button migration, `ConfirmDialog`'s `role="dialog"`/`aria-modal`, status conveyed via visible text not color alone). No new interactive pattern was introduced that would need new accessibility work.

## 12. Backend Changes

**NONE.** `py_compile` re-verified PASS, byte-for-byte unchanged.

## 13. Database Changes

**NONE.** No migration created or needed.

## 14. Known Limitations

- Teacher Dashboard shows platform-wide counts, not "my content" — there is no ownership field in the backend to filter by (confirmed, not a frontend oversight).
- Teacher's "Attestatsiya", "Milliy Sertifikat", "Natijalar", "Statistika" sidebar entries remain `PlaceholderPage` — explicitly out of this sprint's scope (Teacher Analytics, Certificate management were explicitly excluded).
- No standalone "Savollar" list page/sidebar entry was created — Questions have no meaning outside their parent Test (Sprint 19's established architecture, respected here rather than re-litigated).
- Video URL management for Lessons is exactly what already existed (`LessonFormPage`'s `type="url"` input, reused as-is) — no video player, per explicit Sprint 26 scope boundary (Sprint 28).

## 15. Sprint 27 Recommendations

Per Sprint 25's audit and this sprint's findings, Sprint 27 should be **Student Learning Navigation** (Fan → Sinf → Mavzu → Dars viewing pages) — the content Teacher can now actually create has no student-facing way to be browsed/read yet, which is the next most valuable, clearly-scoped gap.

---

**SPRINT 26 STATUS: READY FOR REVIEW**

**CODE CHANGES:**
Created: `pages/teacher/SubjectsPage.tsx` (+test), `pages/teacher/GradesPage.tsx` (+test), `pages/teacher/DashboardPage.test.tsx`, `docs/Sprint26_Teacher_Panel.md`
Modified: `pages/teacher/DashboardPage.tsx` (rewritten in place), `pages/admin/{TopicsListPage,TopicFormPage,LessonsListPage,LessonFormPage,TestsListPage,TestFormPage,TestQuestionsListPage,QuestionFormPage}.tsx` (basePath prop added), `pages/admin/TopicsListPage.test.tsx` (2 tests added), `routes/AppRoutes.tsx`, `utils/sidebarConfig.ts`

**BACKEND CHANGES: NONE**

**DATABASE MIGRATIONS: NONE**

**TESTS: 203 passed / 0 failed**

**BUILD: PASS**

**COMMIT: NONE**

**PUSH: NONE**
