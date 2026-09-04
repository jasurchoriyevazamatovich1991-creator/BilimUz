# Sprint 21 — Student Certificates UI

**Status: BUILD PASS, TESTS PASS, READY FOR REVIEW**

## 1. Sprint goal

Build the Student Certificates UI: a passing test result leads to an idempotently-issued certificate, viewable in a personal list/detail flow, with a working "verification code → public verify" continuation and a fully public certificate verification page — all against real backend endpoints.

## 2. Scope

- Student Certificates list (`GET /certificates/me`)
- Certificate detail (`GET /certificates/{id}`), including the verification code
- Certificate creation from a passing Result (`POST /certificates`)
- Public certificate verification (`GET /certificates/verify/{code}`), reachable both by manual code entry and by a direct link from the certificate detail page

**Explicitly out of scope**: Admin certificate template management, PDF generation UI, any template-selection workflow.

## 3. Backend fix (this sprint's precondition, not new frontend work)

**Real backend gap found and fixed before this frontend implementation continued**: `CertificateOut` did not include `verification_code` — the code the public verify endpoint (`GET /certificates/verify/{code}`) actually looks up. Confirmed directly: the code lives on a *separate* `CertificateVerification` record (`certificate_verification` table), matched via `VerificationRepository.get_by_code()`, and is architecturally distinct from `certificate_number`. Without this field, a student had no way to obtain the code needed to verify their own certificate.

**Fix applied** (backend, prior to this frontend work):
- `app/modules/certificates/schemas.py` — `CertificateOut` gained a `verification_code: str` field.
- `app/modules/certificates/service.py` — `issue()`, `get()`, and `list_mine()` now attach the linked `CertificateVerification`'s code as a **transient (non-persisted) attribute** on the `Certificate` ORM instance before it's serialized.
- `app/modules/certificates/router.py` — **untouched**; it already just calls `CertificateOut.model_validate(certificate)`, which now picks up the attached attribute automatically.

**No database migration was required** — no column was added to any table; the value is assembled at read time from the existing `certificate_verification` table, exactly as it already existed.

**6 new backend unit tests** were added (not replacing any existing ones) verifying: `issue()` attaches the code from the just-created verification (no extra query), the idempotent-reissue path also attaches it, `get()` and `list_mine()` attach it correctly, a defensive empty-string fallback if no verification record exists, and an explicit assertion that the public verify response still contains *only* the three approved fields (no PII, no `user_id` leak). All 18 certificate backend tests (12 original + 6 new) pass.

## 4. Frontend files

**Extended**:
- `src/api/certificates.ts` — `CertificateOut` now includes `verification_code: string` (docstring updated to reflect the fix, replacing the earlier "gap" note)

**Modified, additive only**:
- `src/pages/student/CertificateDetailPage.tsx` — now displays "Tekshirish kodi" and a "Kodni tekshirish" link to the public verify page with the code pre-filled
- `src/pages/public/VerifyCertificatePage.tsx` — now supports an optional `?code=` query param (pre-fills and auto-submits), powering the link above via the existing `react-router-dom` `useSearchParams` hook — no new routing mechanism
- `src/pages/student/ResultPage.tsx` — "Sertifikat olish" button (unchanged from the prior pass)
- `src/routes/AppRoutes.tsx`, `src/utils/sidebarConfig.ts` — routes/sidebar entry (unchanged from the prior pass)
- Three test files updated to include the now-required `verification_code` field in their mock `CertificateOut` objects (`CertificateDetailPage.test.tsx`, `CertificatesListPage.test.tsx`, `ResultPage.test.tsx`)

**New files** (unchanged from the prior pass):
- `src/hooks/useCertificates.ts`
- `src/pages/student/CertificatesListPage.tsx`
- 4 test files (2 gained new test cases this pass)

## 5. Certificate flow

```
ResultPage (is_passed === true)
  → "Sertifikat olish" → POST /certificates {result_id}
  → navigate to /student/certificates/:id
  → CertificateDetailPage (GET /certificates/{id})
    → shows certificate_number, date, status, AND verification_code
    → "Kodni tekshirish" → /certificates/verify?code=<verification_code>
      → VerifyCertificatePage auto-submits → GET /certificates/verify/{code}
      → shows "Sertifikat haqiqiy"
```

Idempotent creation is unchanged from the prior pass: `issue()`'s idempotent-reissue branch now also carries `verification_code` (verified by a dedicated backend test), so a second visit to an already-certified result correctly shows the same, real code — not a blank or stale one.

## 6. Public verification flow

`VerifyCertificatePage.tsx` remains fully public (`PublicLayout`, outside `ProtectedRoute`). Two ways to reach a result: (a) manual code entry (unchanged), (b) a `?code=` link (new) — both call the same `GET /certificates/verify/{code}` and render only `certificate_number`, `is_valid`, `verified_count`. Tested explicitly, including while logged out.

## 7. RBAC / security

Unchanged from the prior pass — `/student/certificates*` inside `ProtectedRoute allowedPanel="student"`, `/certificates/verify` fully public, ownership enforced entirely server-side (404 for non-owned). The newly-exposed `verification_code` is returned **only** through the already-authenticated, already-ownership-checked student endpoints — never through the public verify endpoint's own response (which still returns just the 3 approved fields, asserted explicitly in a new backend test).

## 8. PDF limitation

Unchanged — `pdf_url` is always `null`; `CertificateDetailPage.tsx` still shows no download button (re-tested this pass to confirm the new verification-code UI didn't accidentally reintroduce one).

## 9. Error handling

Unchanged from the prior pass — `ErrorState` for fetch failures, toast for mutation failures, inline banner for the public verify page's own errors.

## 10. React Query strategy

Unchanged — same key conventions, same single app-wide `QueryClient`. No new query keys were needed for the `verification_code` field since it's just an additional property on the already-cached `CertificateOut` object.

## 11. Tests

16 of the 16 requested scenarios covered; existing Sprint 13–20 tests were not touched or deleted.

| # | Scenario | File |
|---|---|---|
| 1 | Certificate list success | `CertificatesListPage.test.tsx` |
| 2 | Certificate list empty | `CertificatesListPage.test.tsx` |
| 3 | Certificate list error | `CertificatesListPage.test.tsx` |
| 4 | Certificate detail success | `CertificateDetailPage.test.tsx` |
| 5 | Certificate detail 404 | `CertificateDetailPage.test.tsx` |
| 6 | Passed result → button present | `ResultPage.test.tsx` |
| 7 | Failed result → button absent | `ResultPage.test.tsx` |
| 8 | Creation calls the real API with the correct payload | `ResultPage.test.tsx` |
| 9 | Successful creation → detail page | `ResultPage.test.tsx` |
| 10 | Idempotent creation handling | Backend: `test_issue_is_idempotent_per_user_and_test`, `test_issue_attaches_verification_code_on_idempotent_reissue` |
| 11 | Public verify requires no auth | `VerifyCertificatePage.test.tsx` |
| 12 | Valid verification | `VerifyCertificatePage.test.tsx` |
| 13 | Invalid verification | `VerifyCertificatePage.test.tsx` |
| 14 | `verification_code` shown on detail page | `CertificateDetailPage.test.tsx` (new) |
| 15 | No download button when `pdf_url` is null | `CertificateDetailPage.test.tsx` |
| 16 | Existing Sprint 13–20 tests remain passing | Full suite run |

**Frontend total: 133 tests, 133 passing** (17 new across this sprint's two passes). **Backend certificates: 18 tests, 18 passing** (6 new this pass).

## 12. Build

```
TypeScript: PASS
Build:      PASS (dist/ produced, 242 modules transformed)
```

## 13. Backend validation

```
py_compile:              PASS
Certificate tests:        18 passed (12 original + 6 new)
```

## 14. Known limitations

- No PDF certificates (`pdf_url` always `null`).
- No admin certificate template management UI.
- No test title shown on the certificate detail page (would need an extra Result fetch, out of scope).

## 15. Pre-existing failures — NOT caused by this sprint, NOT fixed by this sprint

Running the full backend suite surfaces 6 pre-existing failures, unrelated to certificates, discovered only because this was the first session real `pytest` execution was possible:

- `app/modules/profiles/tests/test_profile_service.py` — 4 failures
- `app/modules/roles/tests/test_role_service.py` — 2 failures (confirmed root cause: an unconfigured `MagicMock` return value compared with `>` against an `int`, a test-authoring gap, not application logic)

Additionally, 3 test modules fail to even **collect** (`auth`, `questions`, `attempts`) due to a missing optional dependency (`email-validator`) and an unrelated Python/type-hint evaluation issue in `questions/repository.py`. **None of these were touched, and per explicit instruction, none were "fixed" as part of this sprint** — they are recorded here for visibility only.

## 16. Future work

- Real PDF generation once the backend implements it.
- Admin-side certificate template CRUD.
- Showing the associated test's title on the certificate detail page.
- Addressing the 6 pre-existing test failures and 3 collection errors listed in §15, in a dedicated fix (not this sprint's scope).

---

## SPRINT 21 IMPLEMENTATION REPORT

**Backend changes:**
`app/modules/certificates/schemas.py` (1 field added), `app/modules/certificates/service.py` (3 methods extended, 1 private helper added), `app/modules/certificates/tests/test_certificate_service.py` (5 tests added), `app/modules/certificates/tests/test_verification_service.py` (1 test added). **No migration.** `router.py` and all other backend modules untouched.

**Frontend files created:**
`src/hooks/useCertificates.ts`, `src/pages/student/CertificatesListPage.tsx`, `src/pages/student/CertificateDetailPage.tsx`, `src/pages/public/VerifyCertificatePage.tsx`, 4 test files, `docs/Sprint21_Student_Certificates_UI.md`

**Frontend files modified:**
`src/api/certificates.ts`, `src/pages/student/ResultPage.tsx`, `src/routes/AppRoutes.tsx`, `src/utils/sidebarConfig.ts`, plus `verification_code` added to 3 existing test files' mock data

**Routes:**
`/student/certificates`, `/student/certificates/:certificateId`, `/certificates/verify` (public, now supports `?code=`)

**Endpoints:**
`POST /certificates`, `GET /certificates/me`, `GET /certificates/{id}`, `GET /certificates/verify/{code}`

**Tests:**
Frontend: 133 passed / 0 failed (17 new this feature). Backend certificates: 18 passed / 0 failed (6 new this pass).

**Build:**
PASS

**Backend validation:**
py_compile PASS; certificate tests PASS; 6 pre-existing failures in unrelated modules (profiles, roles) confirmed NOT caused by this work, NOT fixed (out of scope, see §15).

**Known limitations:**
See §14.

**Pre-existing failures:**
See §15 — 6 test failures (profiles, roles) + 3 collection errors (auth, questions, attempts), all confirmed pre-existing and unrelated.

**Security:**
Ownership enforced server-side throughout (unchanged). `verification_code` exposed only via already-authenticated, already-ownership-checked endpoints. Public verify endpoint's response shape unchanged and explicitly re-tested to contain no PII.

**Color/UI notes:**
No new colors introduced; existing `StatusBadge`, `Button`, `Card`, `Input` and Tailwind/shadcn tokens reused throughout. No global color system, dark mode, or theme work done (explicitly out of scope).

**Final verdict:**
READY FOR REVIEW
