# Sprint 24 — UI/UX + Design System (Indigo + Violet + Cyan)

**Status: BUILD PASS, TESTS PASS, READY FOR REVIEW**

## 1. Design direction

Indigo (primary) + Violet (secondary) + Cyan (accent), bright but not neon, cool-neutral light mode, deep-navy (never pure black) dark mode — matching the approved brief exactly. Font unchanged (Inter — already correct, already matched the "modern sans-serif" recommendation).

## 2. Audit findings (performed before any implementation)

- `tailwind.config.js` had exactly **one** color token (`primary`, hardcoded hex `#0C447C`) — no `secondary`, `accent`, `success`, `warning`, `destructive`, `info`, `muted`, `card`, `popover`, or `ring` existed at all.
- `border`/`background`/`foreground` were **static hardcoded HSL values**, not CSS variables — no single source of truth.
- `components.json` had `"cssVariables": false` — shadcn/ui was explicitly configured against the variable-based theming this sprint requires.
- `darkMode: ["class"]` was already configured in Tailwind but **completely unused** — nothing anywhere ever applied a `.dark` class. No dark-mode infrastructure existed.
- **High-leverage finding**: the large majority of existing components/pages already used *semantic* Tailwind classes (`bg-primary`, `text-foreground`, `border-border`, including opacity-modifier usage like `bg-primary/10`) rather than raw hex/named colors. This meant a correctly-built CSS-variable token system would **automatically** recolor most of the app to Indigo/Violet/Cyan without touching those files by hand — verified directly (e.g. `Sidebar.tsx`, `DashboardCard.tsx`, `ConfirmDialog.tsx`, `ContentBadges.tsx`, `MediaTypeBadges.tsx` needed **zero** code changes).
- A minority of files used raw Tailwind colors directly (`bg-red-50`, `text-green-700`, etc.) — mostly small, repeated "O'chirish" (delete) link text-colors across ~15 admin list pages, plus a few prominent pass/fail/valid/invalid banners.

## 3. Files created

- `src/store/themeStore.ts` — new Zustand store (light/dark, persisted, applies `.dark` to `<html>`)
- `src/store/themeStore.test.ts`
- `docs/Sprint24_UI_UX_Design_System.md`

## 4. Files modified

**Foundation** (the actual "source of truth"):
- `src/styles/index.css` — full `:root` (light) + `.dark` CSS variable blocks
- `tailwind.config.js` — full semantic token set (all `hsl(var(--x) / <alpha-value>)`-backed, preserving every existing opacity-modifier usage like `bg-primary/10` across the whole app), extended radius scale, new shadow scale
- `components.json` — `cssVariables: true`

**Core shared components** (cascade to the whole app):
- `src/components/ui/button.tsx` — added `secondary`/`success` variants, migrated `destructive` off hardcoded red, added a visible `focus-visible` ring (accessibility)
- `src/components/users/StatusBadge.tsx` — migrated to `success`/`muted`/`destructive`/`warning` tokens (same status→meaning mapping, same visible status text)
- `src/components/layout/ErrorState.tsx` — migrated to `destructive` tokens
- `src/components/layout/ToastContainer.tsx` — migrated to `destructive`/`success`/`info` tokens

**Targeted "hero moment" touches** (high-visibility, low-risk, self-contained):
- `src/pages/student/ResultPage.tsx` — pass/fail banner → `success`/`destructive` tokens
- `src/pages/public/VerifyCertificatePage.tsx` — valid/invalid + error banners → `success`/`destructive` tokens

**Careful, minimal, protected-file addition**:
- `src/components/layout/Header.tsx` — one new theme-toggle button added as a sibling to the existing user-menu `<div>`; the dropdown, logout, notification bell, and click-outside/Escape logic are **completely unchanged**.
- `src/components/layout/Header.test.tsx` — 3 pre-existing tests had their button selector disambiguated (`getByRole("button")` → `getByRole("button", { name: /Aziz Karimov/ })`) since the new toggle button legitimately introduced a second unlabeled button on the page — same fix philosophy already established in Sprint 20's build-blocker pass. **Test intent is completely unchanged**, only the selector precision. 3 new tests added for the toggle itself.

## 5. Color system

| Token | Light | Dark |
|---|---|---|
| `primary` (Indigo) | `243 75% 59%` | `243 90% 70%` |
| `secondary` (Violet) | `262 83% 58%` | `262 75% 68%` |
| `accent` (Cyan) | `189 94% 43%` | `189 85% 58%` |
| `success` | `142 71% 45%` | `142 60% 52%` |
| `warning` | `38 92% 50%` | `38 88% 58%` |
| `destructive` | `0 72% 51%` | `0 70% 62%` |
| `info` | `199 89% 48%` | `199 85% 58%` |
| `background` | `210 40% 98%` (cool, not stark white) | `222 47% 8%` (deep navy, not black) |
| `card`/`popover` | `0 0% 100%` | `222 40% 12%` |
| `muted` | `210 40% 96%` | `217 33% 17%` |
| `border`/`input` | `220 13% 91%` | `217 33% 20%` |
| `ring` | = `primary` | = `primary` |

Every color has a matching `-foreground` pair for guaranteed-readable text on that background.

## 6. Light mode

Cool, very light neutral background (not stark white — `210 40% 98%`), white card surfaces, dark navy text (`222 47% 11%`), soft slate borders. Matches the brief's "juda oq va bo'sh ko'rinib qolmasin" guidance via the cool-tinted background against pure-white cards, giving real depth without gradients.

## 7. Dark mode

Deep navy/slate background (`222 47% 8%`) — explicitly **not** pure black, per the brief. Card surfaces one step lighter (`222 40% 12%`) for visible elevation. Primary/secondary/accent are all brightened relative to their light-mode values (standard dark-mode contrast practice) without becoming neon. Toggle is in `Header.tsx`, persisted via `themeStore.ts`, applies instantly (`.dark` class on `<html>`).

## 8. Typography

Unchanged — `Inter` was already configured and already matches the brief's own suggestion. No new font added, no hierarchy scale changes needed (existing `text-xl`/`text-2xl`/`text-sm`/`text-xs` usage throughout the app already forms a reasonable, consistent scale).

## 9. Spacing

Unchanged — the existing Tailwind default spacing scale (4px-based: `p-2`, `p-3`, `p-4`, `p-5`, `p-6`, `gap-2`, `gap-3`, etc., already used consistently across every Sprint 15–23 page) already matches the brief's own 4/8px-multiple guidance. No new scale needed.

## 10. Radius

New named scale added to `tailwind.config.js`, backed by CSS variables: `sm` (6px), `md` (8px), `lg` (12px), `xl` (16px), `2xl` (20px) — matching the brief's exact suggested values.

## 11. Shadows

New `xs`/`sm`/`md`/`lg` scale added, all using very low-opacity `hsl(var(--foreground) / 0.0x)` (soft elevation, never a harsh black shadow) — automatically correct in both light and dark mode since it's foreground-color-relative, not a fixed black.

## 12. Buttons

`default` (Indigo), `secondary` (Violet, new), `success` (Green, new), `outline`, `ghost`, `destructive` (now token-backed, was hardcoded red) — 6 variants total, all with a proper `focus-visible` ring for keyboard accessibility (new, was missing before this sprint).

## 13. Forms

`Input.tsx` was already fully semantic (`border-border`, `bg-background`, `focus-visible:ring-primary/40`) — inherits the new Indigo focus ring automatically, no code change needed.

## 14. Cards

`Card`/`CardHeader`/`CardTitle`/`CardContent` were already fully semantic — inherit the new token system automatically, no code change needed.

## 15. Badges

`StatusBadge` migrated to semantic tokens (see §4). `ContentBadges`/`MediaTypeBadges` were already semantic (`bg-primary/10 text-primary`) — no change needed, automatically Indigo now instead of the old blue.

## 16. Sidebar

`Sidebar.tsx` was already fully semantic (active item: `bg-primary text-primary-foreground`) — automatically Indigo now, zero code change.

## 17. Header

Notification bell (Sprint 23) and dropdown (Sprint 14) completely unchanged in structure/logic. One new theme-toggle button added — see §4 for the exact, minimal diff shape.

## 18. Dashboard

`DashboardCard.tsx` was already fully semantic — automatically inherits the new palette, zero code change. No new dashboard-specific work was needed since the existing card/stat pattern already carries the Indigo identity through the token system.

## 19. Notifications

Sprint 23's `NotificationsPage.tsx` uses `bg-primary/5`/`border-primary/30`/`bg-primary` for its unread indicator dot and highlight — already exactly matching the brief's "subtle Indigo/Cyan indicator" request, automatically updated by the token change. No functional change to notification behavior.

## 20. Certificates

`CertificateDetailPage.tsx`/`CertificatesListPage.tsx` already used `Card`/`Button`/`StatusBadge` throughout — automatically inherit the new premium Indigo/Violet look. `VerifyCertificatePage.tsx`'s valid/invalid banner was explicitly migrated to `success`/`destructive` tokens (§4) as the most prominent "trust/achievement" moment on that page. No functional change to certificate creation/verification.

## 21. Roles & Permissions

`RolesListPage`/`RoleFormPage`/`PermissionsListPage`/`PermissionFormPage` all already build on `Table`/`Button`/`StatusBadge`/`ConfirmDialog` — automatically inherit the new system. No functional change.

## 22. Responsive

No new responsive architecture introduced — the existing Tailwind breakpoint usage (`sm:`/`md:`/`lg:` on grid layouts, `overflow-x-auto` on every data table since Sprint 15) is unchanged and was not touched, since responsiveness is orthogonal to color theming and none of it needed fixing.

## 23. Accessibility

- Every `Button` variant now has a visible `focus-visible` ring (new — was missing).
- `StatusBadge`/toast/banners still show the actual **text** of the status/message (never color-only), preserved exactly as before — colors were re-themed, the underlying "text conveys meaning" property was never touched.
- Theme toggle has a descriptive `aria-label` reflecting the *resulting* state ("Qorong'i rejimga o'tish" / "Yorug' rejimga o'tish"), not just an icon.

## 24. Tests

```
Test Files: 36 passed (36)
Tests:      194 passed (194)
```

8 new tests (5 `themeStore.test.ts` + 3 `Header.test.tsx` theme-toggle cases). 3 pre-existing `Header.test.tsx` tests had their button selector disambiguated (see §4) — **no test was weakened, deleted, or given a fake assertion**; the same behavior is verified, just via a more specific (and more correct) query now that a second real button exists on the page.

## 25. Build

```
TypeScript: PASS
Build:      PASS (dist/ produced, 252 modules — same module count as Sprint 23, no new page/route added)
```

## 26. Backend

**No changes.** `py_compile` re-verified PASS. No API endpoint, schema, or RBAC logic touched.

## 27. Known limitations

- ~15 admin list pages' small inline "O'chirish" delete-link text (`text-red-600 hover:underline`) were **not** individually migrated to the `destructive` token — left as documented follow-up rather than hand-touching every CRUD list page this sprint, since the visual difference between raw `red-600` and the new `destructive` token is minor and the touch-surface/regression-risk tradeoff favored a targeted approach (foundation + shared components + the highest-visibility "hero" pages) over an exhaustive one.
- `Timer.tsx`'s low-time-remaining red warning text was not migrated (same reasoning — small, self-contained, low marginal value).
- No dark-mode-specific manual QA was possible in this environment (no visual browser rendering available) — correctness was verified via the compiled CSS output (`--primary` etc. resolving to the intended HSL values) and automated tests, not a visual screenshot review.
- No code-splitting/bundle-size work was done — the existing single-chunk build (~515kB, unchanged from Sprint 23) still triggers Vite's advisory chunk-size warning; out of this sprint's scope (design system, not performance/bundling).

## 28. Future improvements

- Migrate the remaining ~15 files' small `red-600` delete-link instances to the `destructive` token for full consistency.
- A dedicated visual QA pass (real browser, both themes, all breakpoints) once a rendering environment is available.
- Consider code-splitting (`React.lazy`/dynamic `import()`) for the admin bundle, separate from this design-system sprint's scope.
