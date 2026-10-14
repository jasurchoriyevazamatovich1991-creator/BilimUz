# Sprint 89 — Frontend Completion and UX Hardening

Release-prep document for the repository owner. Prepared as part of a
release-preparation pass; no commit or push was performed by that pass —
see "Release process" below.

## Summary

Sprint 89 audited the complete frontend (routes, shared layout
components, loading/error/empty states) and fixed four confirmed defects
found during that audit, plus added focused regression tests for each.
No AI provider changes, no backend contract changes, no database/auth
changes, and no broad redesign were made.

## User-visible changes

- **404 handling**: unmatched routes (any path, authenticated or not)
  now render a dedicated "Sahifa topilmadi" page with a role-aware link
  back to the user's own panel (or `/` when signed out), instead of a
  blank screen. Implemented as a single top-level catch-all route, kept
  last in `AppRoutes.tsx` so it cannot shadow any real route.
- **Teacher dashboard error handling**: each of the dashboard's four
  stat widgets (Topics/Lessons/Tests/Questions) now shows its own error
  state if its request fails, instead of silently rendering as if the
  count were genuinely zero. A failed widget and a widget that is
  correctly reporting zero are now visually and behaviorally distinct;
  the other three widgets keep showing real data independently when
  only one request fails. A toast is also fired on failure (reusing the
  existing `useToastOnQueryError` hook, now exported for reuse).
- **Responsive mobile navigation**: the sidebar (shared by every
  authenticated layout — Student/Admin/Teacher) is now a slide-in drawer
  below the existing `lg` breakpoint, opened via a new hamburger button
  in the header. It closes on backdrop click, on Escape, or automatically
  after following a nav link. At `lg` and above, the sidebar's appearance
  is unchanged from before this sprint (always-visible sticky column).
  State is held in a new, deliberately non-persisted `uiStore.ts` (drawer
  state has no meaning across reload/new tab).
- **ConfirmDialog accessibility**: the shared confirm dialog now closes
  on Escape and moves focus to its Cancel button on open, matching the
  Escape-handling convention already used by the header's own dropdown.

## Verified Sprint 89 files

Confirmed via individual `git diff` review against the repository's real
HEAD (commit `449d316`) — each listed file contains Sprint 89 changes
only, with no unrelated earlier-sprint hunks mixed in:

New files:
- `frontend/src/pages/public/NotFoundPage.tsx`
- `frontend/src/pages/public/NotFoundPage.test.tsx`
- `frontend/src/routes/AppRoutes.test.tsx`
- `frontend/src/components/layout/Sidebar.test.tsx`
- `frontend/src/store/uiStore.ts`

Modified files, confirmed clean (Sprint 89 only):
- `frontend/src/pages/teacher/DashboardPage.tsx`
- `frontend/src/pages/teacher/DashboardPage.test.tsx`
- `frontend/src/hooks/useDashboardStats.ts`
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/components/layout/Header.tsx`
- `frontend/src/components/layout/Header.test.tsx`
- `frontend/src/components/common/ConfirmDialog.tsx`
- `frontend/src/components/common/ConfirmDialog.test.tsx`

**Not included — mixed with unrelated earlier work**:
`frontend/src/routes/AppRoutes.tsx` also carries Sprint 74 (exam-config
route) and Sprint 88 (AI Center route) changes in the same diff against
HEAD. Only this file's Sprint 89 hunk (the `NotFoundPage` import and the
trailing catch-all `<Route path="*">`) belongs to this release — see the
release-prep report delivered alongside this document for the exact
recommended staging approach.

## Tests and validation

Run from `frontend/` on this date:

- `npm run test -- --run` → **69 test files, 473 tests, all passed**
- `npx tsc -b --noEmit` → **0 errors**
- `npm run lint` → **0 errors, 5 pre-existing warnings** (all in files
  untouched by Sprint 89: `LessonFormPage.tsx`, `QuestionFormPage.tsx`,
  `TestFormPage.tsx`, `TopicFormPage.tsx` — missing-dependency warnings —
  and one unused-eslint-disable-directive warning in `AttemptPage.tsx`)
- `npm run build` → **succeeded** (one pre-existing chunk-size advisory
  from Vite, unrelated to this sprint's changes)

New/updated tests added this sprint: `NotFoundPage.test.tsx` (3),
`AppRoutes.test.tsx` (3, exercising the real route tree), `Sidebar.test.tsx`
(6), `DashboardPage.test.tsx` for teacher (+2), `Header.test.tsx` (+1),
`ConfirmDialog.test.tsx` (+3) — 18 new/updated tests in total, all
included in the 473 passing above.

## Known limitations

- **Responsive behavior was tested automatically only.** The sidebar
  drawer's open/closed/backdrop/Escape/nav-close behavior is covered by
  jsdom-based assertions on the Tailwind classes that drive the
  breakpoint behavior (e.g. `-translate-x-full` vs `translate-x-0`), not
  by manual testing in a real browser at real viewport widths. No manual
  cross-browser or real-device check was performed.
- **`AttemptPage` (the test-taking page) still uses the regular
  `StudentLayout` and was not changed in this sprint.** The sidebar/
  header responsive changes apply to it only incidentally, through the
  shared layout; no attempt-specific UX work was done.
- The mobile-nav hamburger button toggles the drawer but does not carry
  `aria-expanded`/`aria-controls` attributes. Core keyboard/screen-reader
  dismissal (Escape, and focus landing on Cancel in `ConfirmDialog`) was
  addressed; this smaller refinement was left out as a new feature
  outside this sprint's narrow audit-and-fix scope.
- The AI Center UX hardening mentioned in earlier sprint planning is not
  part of this file's change set captured here — it was addressed, if at
  all, without any changes to its backend contract, per the standing
  restriction; no AI Center files appear in the verified file list above.

## Release process

This document was prepared during a release-preparation pass that did
**not** stage, commit, or push any changes, and did not run any
destructive Git command. The repository owner reviews the accompanying
report and performs all Git/GitHub operations manually.
