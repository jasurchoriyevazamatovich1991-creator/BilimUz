# Sprint 23 — Notifications UI

**Status: BUILD PASS, TESTS PASS, READY FOR REVIEW**

## 1. Sprint goal

Give the Student panel a working notifications experience: a list page for viewing/reading notifications, and a Header bell showing a real unread count — against real, already-implemented backend endpoints, with no backend changes and no admin notification management (explicitly out of scope).

## 2. Backend audit (performed before any code was written)

Every fact below verified directly against `app/modules/notifications/{router,schemas,service,models,exceptions}.py` — nothing assumed.

| # | Question | Answer |
|---|---|---|
| 1 | Student list endpoint | `GET /notifications/me` |
| 2 | Single read endpoint | `PATCH /notifications/{notification_id}/read` |
| 3 | Mark-all-read endpoint | `PATCH /notifications/me/read-all` |
| 4 | Response schema | `{items: NotificationOut[], meta: {page, per_page, total, total_pages}}` for the list; `NotificationOut` for single-read; `{marked_count: number}` for mark-all |
| 5 | Notification fields | `id, user_id, title, message, channel, is_read, created_at` — exactly these, nothing more |
| 6 | ID field | `id` (UUID) |
| 7 | read/unread field | `is_read: bool` |
| 8 | created_at field | `created_at: datetime` |
| 9 | title/message | `title: str`, `message: str` — both real, both used |
| 10 | Pagination | Yes — `page`, `per_page`, plus an `is_read` filter |
| 11 | Authentication | `get_current_user` — any authenticated user, not student-specific |
| 12 | RBAC/ownership | `mark_read` checks `notification.user_id != user_id` → 404 (same anti-enumeration pattern as Attempts/Certificates) |

**Unread count**: since the list endpoint is paginated, counting unread notifications by summing a fetched page would be wrong past page 1. Instead, `GET /notifications/me?is_read=false&per_page=1` is used and `meta.total` read from the response — the same reliable pattern already used platform-wide for every other "count" widget (Sprint 14's dashboard cards, etc.), not a client-side guess.

**Admin notification management** (templates, queueing, processing — all `Admin, Super Admin` only, verified in the same router) is confirmed real but **explicitly out of this sprint's scope**, per the approved brief.

## 3. Endpoints used

```
GET   /notifications/me?page=&per_page=&is_read=
PATCH /notifications/{notification_id}/read
PATCH /notifications/me/read-all
```

## 4. Frontend

**New files**:
- `src/api/notifications.ts`
- `src/hooks/useNotifications.ts`
- `src/pages/student/NotificationsPage.tsx`
- `src/pages/student/NotificationsPage.test.tsx`

**Modified, minimal and additive only**:
- `src/components/layout/Header.tsx` — a notification bell added to the previously-empty left side; **everything else in the file (dropdown, logout, click-outside/Escape handling) is untouched**.
- `src/routes/AppRoutes.tsx` — one new route.
- `src/utils/sidebarConfig.ts` — one new `STUDENT_ITEMS` entry, so the page is reachable from the sidebar too, not only via the bell.
- `src/components/layout/Header.test.tsx` — 6 new tests appended; all existing tests/assertions unchanged.

## 5. Routes

```
/student/notifications
```

Sits inside the existing `ProtectedRoute allowedPanel="student"` — no new auth mechanism, no new route guard pattern.

## 6. Features

- **List**: title, message, timestamp, read/unread visual state (a small dot + tinted background for unread), pagination — all real `NotificationOut` fields, nothing invented.
- **Mark one as read**: clicking an unread notification (or its "O'qildi" action) calls `PATCH /notifications/{id}/read`; on success, both the list and the unread-count query are invalidated so neither goes stale.
- **Mark all as read**: only rendered when the real unread count is `> 0`; calls `PATCH /notifications/me/read-all`; invalidates the same two query keys.
- **Header bell**: shown **only for the Student role** — a deliberate scope decision (Admin notification management is out of scope this sprint; the Teacher panel has no `/teacher/notifications` route at all, so showing a bell there would link nowhere). Badge shows the real unread count (capped visually at "99+"), sourced from the same reliable `meta.total` pattern. The query is `enabled` only when the current user is a Student, avoiding an unnecessary network call for every other role.

## 7. RBAC

Unchanged mechanism throughout — `ProtectedRoute allowedPanel="student"` for the page, the backend's own `get_current_user` + ownership check for the API calls. No new authorization pattern introduced. Admin notification management was not touched or built.

## 8. Security

- `ConfirmDialog` was not needed here — marking read/mark-all-read are non-destructive, reversible-in-spirit actions (unlike delete), matching how the rest of the project reserves `ConfirmDialog` for destructive operations specifically. No `window.confirm()` used anywhere.
- Ownership enforced entirely server-side; the frontend never assumes a notification ID belongs to the current user.
- JWT/API client/RBAC architecture completely unchanged.

## 9. Color / UI

No new colors, no theme changes — existing `Button`, `ErrorState`, Tailwind tokens (`bg-primary`, `text-foreground`, etc.) reused throughout, matching every prior sprint's visual shape. The bell itself is a plain emoji glyph (🔔) with the existing primary-color badge styling, not a new icon system.

## 10. Tests

16 new tests across 2 files; all pre-existing tests (Sprint 13–22) left completely unmodified in behavior.

**`NotificationsPage.test.tsx`** (10): renders title, list success (title/message shown), empty state, loading state, error state, unread/read visual distinction, mark-one-read (real endpoint call), mark-all-read (real endpoint call, only shown when unread > 0), mark-all-read button hidden at zero unread, query invalidation after mark-read (list refetches).

**`Header.test.tsx`** (6 new, appended): no bell for Teacher, no bell for Admin, bell renders and links correctly for Student, real unread count shown as a badge, no badge at zero unread, the unread-count query is never called for a non-Student role (`enabled` gating verified directly).

```
Test Files: 35 passed (35)
Tests:      186 passed (186)
```

## 11. Build

```
TypeScript: PASS
Build:      PASS (dist/ produced, 252 modules)
```

## 12. Backend validation

```
py_compile:                PASS (backend untouched)
Notification tests:         24 passed (all pre-existing, re-verified, none modified)
Full suite (known exclusions): 336 passed, 6 failed
```

**Pre-existing failures — confirmed identical to Sprint 21/22's documented baseline, NOT new, NOT caused by this sprint**: `profiles` module (4 failures), `roles` module (2 failures) — both re-run this sprint and produced the exact same failure set as previously documented. 3 modules (`auth`, `questions`, `attempts`) still fail to collect due to the same pre-existing missing-dependency and type-hint issues documented since Sprint 21. None of these were touched or "fixed" this sprint, per explicit instruction.

## 13. Known limitations

- No admin notification browsing/management UI (explicitly out of scope).
- The Header bell only appears for the Student role — Admin's existing "Bildirishnomalar" sidebar entry (pointing at `/admin/notifications`) remains an unbuilt `PlaceholderPage`, unchanged from before this sprint.
- No real-time/push updates — the unread count refreshes on a 30-second `staleTime` and on explicit mutation invalidation, not via websockets or polling.
- No per-notification "type" icon or category — the backend's `channel` field (`in_app`/`email`/`sms`) exists but isn't a user-facing categorization, so it isn't surfaced as one.

## 14. Future improvements

- Admin-side notification/template management, if ever prioritized as its own sprint.
- Real-time unread-count updates (websocket or short-polling), if product need arises.
- Extending the bell to Teacher/Admin once their respective notification pages and sidebar entries are built.

---

## Verification Summary

```
BUILD:        PASS
TESTS:        186 passed / 0 failed (16 new)
BACKEND:      py_compile PASS; notification tests 24/24 PASS; 6 pre-existing failures unchanged (profiles, roles)
SECURITY:     PASS (server-side ownership/RBAC unchanged, ConfirmDialog convention respected, no window.confirm)
GIT:          Ready for commit — no commit made, no push made
```
