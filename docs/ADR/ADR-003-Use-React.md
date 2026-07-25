# ADR-003

## Title
Use React + TypeScript for the frontend

## Status
Accepted (frontend implementation not yet started — see `.cursor/context/05-system-modules.md`)

## Context
BilimUz's frontend must serve four structurally different UIs (Public site, Admin panel, Teacher panel, Student/Applicant panel — see `docs/UI-UX/panel_modules.md`), with the most complex screen being the real-time Test Engine (timer, auto-save, question navigator). It needs strict typing (grades, scores, and payment amounts are not fields where `any`-typed bugs are acceptable), a large component ecosystem, and a realistic hiring pool in Uzbekistan's dev market.

## Decision
Use **React 19+** with **TypeScript** (strict mode, no `any`), **Vite** as the build tool, **Tailwind CSS** + **shadcn/ui** for the design system, **Redux Toolkit** for UI state, and **TanStack Query** for server state — full stack defined in `.cursor/prompts/04-frontend.md`.

## Consequences

**Positive:**
- Splitting UI state (Redux Toolkit — e.g. "is the sidebar open") from server state (TanStack Query — e.g. "the current test's questions") avoids the classic anti-pattern of caching server data in Redux and manually invalidating it.
- shadcn/ui ships as copy-in components (not an npm black box), matching the "no hardcoded values, reusable components" rule while staying fully customizable for BilimUz's own design tokens (Dark Mode Ready, per `rules/07-frontend-rules.md`).
- TypeScript strict mode catches an entire class of bugs (e.g. passing a `string` where a `TestAttemptId` UUID is expected) before they reach production — directly supports "millions of users" reliability target.

**Negative:**
- React Router + Redux Toolkit + TanStack Query is more moving parts than a meta-framework (e.g. Next.js) would provide out of the box; the team accepts this in exchange for not being tied to a specific hosting model (BilimUz's backend is a separate FastAPI service, not a Next.js API route).
- No SSR by default — acceptable because BilimUz is an authenticated application (dashboards, test-taking), not a content site where SEO-critical SSR matters; the *Public Website* pages (`docs/UI-UX`) may need a lighter separate treatment later if SEO becomes a priority.

## Alternatives

| Option | Rejected because |
|---|---|
| Next.js | SSR/server components add complexity not needed for an authenticated dashboard-heavy app; would also blur the clean frontend/backend separation the API Blueprint depends on |
| Vue.js | Smaller ecosystem for the specific component needs (TanStack Table, Recharts equivalents exist but React's are more mature) |
| Flutter Web | Would unify with a future Flutter mobile app, but the team's existing web expertise and shadcn/ui's design quality favored React for v1.0 |

## References
- `.cursor/prompts/04-frontend.md`, `rules/07-frontend-rules.md`
- `docs/UI-UX/ui_ux_blueprint.md`, `docs/UI-UX/panel_modules.md`
- `docs/00_Folder_Architecture.md` (frontend section)
