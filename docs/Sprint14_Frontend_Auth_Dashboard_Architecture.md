# Sprint 14 — Frontend Authentication & Dashboard: Architecture Impact Analysis

**Status: DESIGN ONLY — no code written, no repository files modified, no ZIP.**

## Critical finding, established before any design choice below

**Investigated the current frontend state before writing this analysis.** Most of the requested scope (points 1–8, 11) was already built in Sprint 13 ("Frontend Foundation") and its continuation. Presenting this honestly, mapped point-by-point, rather than silently re-planning work that already exists — the same discipline used for Sprint 12's "one remaining module" finding.

| # | Requested topic | Actual status |
|---|---|---|
| 1 | Auth integration with backend | ✅ **Done** — `api/auth.ts`, `api/client.ts`, verified field-for-field against real backend schemas |
| 2 | Login flow | ✅ **Done** — `pages/public/LoginPage.tsx`, `useLogin()` |
| 3 | Refresh token flow | ✅ **Done** — `api/client.ts`'s race-safe interceptor (`refreshPromise`) |
| 4 | Logout flow | ✅ **Done** — `useLogout()`, calls `POST /auth/logout`, clears store |
| 5 | Auth Guard | ✅ **Done** — `routes/ProtectedRoute.tsx` |
| 6 | Dashboard architecture | 🟡 **Shell done, real data NOT done** — `DashboardCard` exists, but Sprint 13 explicitly scoped it as "empty/loading state only," deferred |
| 7 | Role-based routing | ✅ **Done** — `utils/roleConfig.ts`, all 8 real seeded roles |
| 8 | Sidebar generation | ✅ **Done** — `utils/sidebarConfig.ts`, copied from `panel_modules.md` |
| 9 | Header and user menu | 🟡 **Partially done** — `Header.tsx` exists but has no actual *menu* (just a name/role badge + one flat logout button, no dropdown, no Profile/Settings links) |
| 10 | Loading/Error handling | 🟡 **Partially done** — per-form error banners exist (Login/Register/Verify); no `ErrorBoundary` anywhere (a component crash = blank white screen), no mechanism for non-form errors (e.g. a failed dashboard query) to surface at all |
| 11 | Testing strategy | ✅ **Done** — 17 tests already cover auth flow, routing, role/sidebar mapping |
| 12 | Risks | New analysis, below |

**Conclusion: Sprint 14's real, non-duplicate scope is exactly three things** — (a) completing the Header into an actual user menu, (b) systematizing error handling (`ErrorBoundary` + a non-form error surface), (c) wiring the dashboard shells to real backend data per role. Everything else in the original 12-point list is already shipped and shouldn't be rebuilt.

---

## 6 (continued). Dashboard Architecture — real data wiring

Backend endpoints already exist and are suitable, checked directly rather than assumed:

| Role | Candidate widgets | Backend source |
|---|---|---|
| Admin | User count, active tests, today's attempts | `GET /users`, `GET /tests`, `GET /attempts` (Admin-tier list endpoints, already built) |
| Teacher | Own tests, recent results | `GET /tests` (own), `GET /results` (filtered) |
| Student/Applicant | My results, my active tests, recommendations | `GET /results/me`, `GET /attempts` (own), `GET /ai/recommendations/me` (real endpoint — but recall: `ai`'s own README confirms nothing generates a recommendation yet, no real provider exists, so this widget legitimately shows an empty state regardless of wiring — not a frontend gap) |

**No `response_model=` on backend endpoints (known, pre-existing gap)** means each widget's exact response shape must be verified against the real `*Out` schema by reading the backend source directly (same practice as Sprint 13's `UserPublic`/`TokenPair` verification), not assumed from endpoint names.

## 9 (continued). Header & User Menu

A real dropdown (not a single button): avatar/initials, name, role badge (already present), then menu items — **Profil** (links to a future profile page — `profiles` module exists on the backend but has no frontend page yet, out of this sprint), **Chiqish**. Click-outside-to-close and `Escape`-to-close behavior needed (accessibility, not present in the current flat button).

## 10 (continued). Loading/Error Handling — systematized

Two genuinely separate concerns, previously conflated as "not built yet":
- **`ErrorBoundary`** (React class component or a library like `react-error-boundary`) wrapping the app (or at least each layout) — catches render-time crashes, shows a real fallback UI instead of a blank screen. This is a **new architectural piece**, not present anywhere in Sprint 13.
- **Query error surface**: TanStack Query's `isError`/`error` states exist per-hook already (used implicitly), but nothing currently *displays* them outside the three auth forms. A shared `<ErrorState>` component (parallel to the existing `DashboardCard`) for "this widget failed to load" is needed for the new dashboard widgets in point 6.

---

## Testing Strategy (for the genuinely new work)

- Header menu: open/close behavior, click-outside, keyboard (`Escape`), Profile link renders correctly per role.
- `ErrorBoundary`: a deliberately-throwing test component confirms the fallback renders instead of crashing the test itself.
- Dashboard widgets: TanStack Query hooks tested with a mocked `httpClient` (success, loading, and error states each), matching the existing `client.test.ts` mocking style.

## Risks

| Risk | Severity |
|---|---|
| **No `response_model=` on backend** (pre-existing, already flagged in the original backend audit) means every new dashboard widget's type must be hand-verified against source, same manual-interface discipline as Sprint 13 — a real, recurring cost, not a one-time one. | Medium |
| **AI recommendation widget will show empty state** — not a bug, but worth stating plainly so it isn't "discovered" as broken later (same honesty pattern as Sprint 13's Verify-page `debug_code` notice). | Low |
| **`ErrorBoundary` scope ambiguity** — one boundary for the whole app (simpler, but one bad page can still blank the whole session until reload) vs. one per layout (more resilient, more code) — a real design choice, not silently picked. | Low |

---

## Outstanding Decisions — must be resolved before implementation

1. **Confirm the reduced Sprint 14 scope**: only Header user menu + systematic error handling + real dashboard data wiring — not points 1–5, 7, 8, 11 (already done). Proceed on this basis, or is there a reason to revisit an already-completed piece?
2. **Dashboard widgets per role** — confirm the candidate list above (Admin: users/tests/attempts counts; Teacher: own tests/results; Student/Applicant: results/attempts/recommendations) matches what you actually want shown, versus a different set.
3. **`ErrorBoundary` granularity** — one app-wide boundary, or one per layout (Admin/Teacher/Student independently resilient)?
4. **Header menu scope** — Profile link only (pointing at a not-yet-built page, so it would 404/placeholder for now), or hold off on the Profile link until the `profiles` frontend page itself is built in a future sprint?
5. **Non-form error display component** — a small inline `<ErrorState>` per widget (matches `DashboardCard`'s existing shape), or a global toast system (a genuinely new dependency/pattern not used anywhere in Sprint 13, since the documented UX explicitly said form errors are banners, not toasts — would a toast for *non-form* errors be a new, separate UX decision or an inconsistency worth avoiding)?
