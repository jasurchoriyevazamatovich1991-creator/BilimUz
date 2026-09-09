# Sprint 27 — Student Learning Navigation

**Status: READY FOR REVIEW**

## Audit (performed before implementation)

Every fact below verified directly against backend code before writing anything.

1. **Student subjects endpoint**: `GET /subjects` — public (no auth dependency), verified in `subjects/router.py`.
2. **Student grades endpoint**: `GET /grades` — public, same pattern.
3. **Topic ↔ Subject/Grade relationship**: `TopicListParams` has `subject_id` and `grade_id` as independent optional filters — a Topic is the real junction; **Grade itself has no subject relationship** (`GradeOut` carries no `subject_id`). This means the "Sinf" step in the requested flow doesn't backend-filter by subject — the same full Grade list is shown regardless of which subject was picked; real filtering only happens once both `subject_id` and `grade_id` are supplied together at the Topics step. Documented in `SubjectGradesPage.tsx`'s own comment, not silently assumed.
4. **Lesson ↔ Topic relationship**: `Lesson.topic_id` (required) — `GET /lessons?topic_id=X` is public and filterable.
5. **Test ↔ Topic/Lesson relationship**: `TestListParams` has `subject_id`, `grade_id`, `topic_id` — **no `lesson_id` anywhere** (re-verified this sprint, consistent with every prior sprint's finding since Sprint 19). Test relates to Topic, not Lesson.
6. **`Lesson.video`**: a plain `str | None` URL field — no provider detection, no dedicated video entity, verified in `lessons/schemas.py`.
7. **Uploads module**: fully self-scoped (`list_my_uploads`, `get_upload`, `download_upload` all keyed to the requesting user's own files) — **no relationship to Lessons whatsoever**, confirmed by grepping for `lesson` anywhere in `uploads/*.py` (zero matches).
8. **Student file/upload access**: none relevant here — Uploads has no lesson-scoped read path a student could use even if they wanted to.
9. **How a student finds a test**: via the lesson's own `topic_id`, querying `GET /tests?topic_id=X&status=published` — the only real, backend-supported bridge between a Lesson and a Test.
10. **Existing Attempt/Result flow**: Sprint 20's `/student/tests/:testId` (`StudentTestDetailPage`) already handles the active-attempt-check / Start-vs-Continue logic — this sprint links into it unmodified, does not duplicate or bypass it.

**Frontend audit**: `hooks/useSubjects.ts`, `useGrades.ts`, `useTopics.ts`, `useLessons.ts` already had full read hooks (`useSubjectsList`, `useSubject`, `useGradesList`, `useGrade`, `useTopicsList`, `useTopic`, `useLessonsList`, `useLesson`) built in Sprints 16–18 for Admin/Teacher CRUD — all reused here completely unmodified, no new API file needed. `STUDENT_ITEMS` sidebar already had `/student/subjects` ("Mening fanlarim") and `/student/lessons` ("Darslar") pointing at these exact paths since Sprint 13/23 — both were still `PlaceholderPage`; no sidebar change was needed, only real pages behind the existing entries.

## Implemented

```
Fanlar (StudentSubjectsPage)
  → Sinf tanlash (StudentSubjectGradesPage)
    → Mavzular (StudentSubjectGradeTopicsPage — real subject_id+grade_id filter)
      → Darslar (TopicLessonsPage — real topic_id filter)
        → Dars tafsiloti (LessonDetailPage — content, video link, related tests)
          → Test (existing, unmodified Sprint 20 flow)
```

Plus a flat, direct "Darslar" entry (`StudentLessonsPage`) for browsing all active lessons without the drill-down, matching the sidebar's own separate "Darslar" item.

## Routes

```
/student/subjects
/student/subjects/:subjectId/grades
/student/subjects/:subjectId/grades/:gradeId/topics
/student/topics/:topicId/lessons
/student/lessons
/student/lessons/:lessonId
```

No collision with Admin/Teacher routes — all under the existing `ProtectedRoute allowedPanel="student"` tree, wired via the established `placeholderRoutesFor()`/`excludePaths` mechanism.

## API

| Frontend hook | Backend endpoint | Auth |
|---|---|---|
| `useSubjectsList` | `GET /subjects?status=active` | Public |
| `useSubject` | `GET /subjects/{id}` | Public |
| `useGradesList` | `GET /grades?status=active` | Public |
| `useGrade` | `GET /grades/{id}` | Public |
| `useTopicsList` | `GET /topics?subject_id=&grade_id=&status=active` | Public |
| `useTopic` | `GET /topics/{id}` | Public |
| `useLessonsList` | `GET /lessons?topic_id=&status=active` | Public |
| `useLesson` | `GET /lessons/{id}` | Public |
| `useTestsList` | `GET /tests?topic_id=&status=published` | Public |

## Backend Changes

**NONE.** `py_compile` re-verified PASS, byte-for-byte unchanged.

## Tests

```
Test Files: 45 passed (45)
Tests:      228 passed (228)
```

25 new tests across 6 files, all 203 pre-existing tests (Sprint 13–26) unmodified and still passing. Notably tested: the real `subject_id`+`grade_id` dual-filter at the Topics step, the real `topic_id` filter at the Lessons step, the video link rendering as a **plain `<a>` tag with no `<video>`/`<iframe>` anywhere** (explicit scope-boundary test), the topic-based test lookup (not an invented `lesson_id`), and navigation into the existing unmodified Sprint 20 test-taking flow.

## TypeScript

```
PASS
```

## Build

```
PASS (dist/ produced, 261 modules — up from 255 in Sprint 26)
```

## Security

Every new page reads only public, non-sensitive catalog data (subjects/grades/topics/lessons/published tests) — no student-owned or cross-student data is fetched or exposed anywhere in this sprint. `ProtectedRoute allowedPanel="student"` still gates the whole tree (unauthenticated visitors can't reach it, matching every other Student page). No `window.confirm`, no client-only authorization logic, no sensitive data in `localStorage`. Backend RBAC/ownership entirely unchanged.

## Known Limitations

- **Lesson has no `order_number`** (verified — genuinely absent from the backend schema, unlike Topic which has one). Lessons within a topic are shown in the backend's own default order (`-created_at`); no ordering UI was built since there's nothing reliable to order by. **Documented GAP, not worked around with an invented client-side sort.**
- **Grade is not subject-scoped** on the backend — the "Sinf" step shows the same full grade list for every subject; this is a real backend architecture characteristic, not a frontend bug.
- **No video player** — `Lesson.video` is rendered as a plain, safe external link only, exactly matching the field's real capability. YouTube/Vimeo embedding is explicitly Sprint 28.
- **No file/audio attachments** — the `uploads` module exists but has no relationship to Lessons; nothing was built here rather than inventing one. Real GAP for a future Media sprint (not fabricated as `LessonAudio`/`Audio` models or endpoints, per explicit instruction).
- **Test linkage is topic-based, not lesson-based** — since no `lesson_id` exists on Test, a Lesson's "related tests" are actually "the topic's published tests." If a topic has multiple tests, all are listed; this is an honest reflection of the real relationship, not a 1:1 lesson→test mapping.
- **No progress tracking** — explicitly out of scope (Sprint 29 per the Sprint 25 roadmap); no fake progress bar or completion percentage was added anywhere.

## Audio/Media

Explicitly not built this sprint, per instruction. The `uploads` module was audited and found to be entirely self-scoped (personal file cabinet, no lesson relationship) — not a viable path for lesson-attached audio/files without backend changes. Flagged as a real gap for a future dedicated Media sprint (previously identified as Sprint 28 in the Sprint 25 roadmap), not invented here as a fake `Audio`/`LessonAudio` model, endpoint, or storage URL.

## Files Changed

**Created**: `pages/student/{SubjectsPage,SubjectGradesPage,SubjectGradeTopicsPage,TopicLessonsPage,LessonsPage,LessonDetailPage}.tsx` (+ matching `.test.tsx` for each), `docs/Sprint27_Student_Learning_Navigation.md`

**Modified**: `routes/AppRoutes.tsx` (imports + route wiring only — no existing route touched or removed)

**Not touched**: `utils/sidebarConfig.ts` (the needed sidebar entries already existed since Sprint 13/23), every Admin/Teacher page, every API/hook file (all reused as-is), backend (zero files).

## Git Status

Not checked — per instruction, no git commands were run this sprint.

## Verdict

**READY FOR REVIEW**
