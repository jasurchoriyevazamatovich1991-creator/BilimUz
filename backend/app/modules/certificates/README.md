# Certificates Module — BilimUz

Full design rationale: `docs/Sprint7_Results_Certificates_Analytics_Architecture.md` (Revision 2, approved).

## Architecture

Same 8-layer pattern. Three entities (`CertificateTemplate`, `Certificate`, `CertificateVerification`) in one module, matching the schema's own Module 17 grouping. Reads `ResultRepository` (`results` module) read-only for the pass/fail check and the idempotency lookup.

## ⚠️ Scope boundary: no PDF generation this sprint

**`pdf_url` is always `None` on creation.** This is a deliberate, approved scope decision — not a bug, not a stub pretending to work. Certificate issuance, uniqueness, public verification, and template management are all fully real and functional; only the rendered PDF file is deferred to a future sprint (see Future Improvements).

## Business rules

- **Only issuable from a passing Result** (`result.is_passed == True`) — `CannotCertifyFailedResultException` otherwise.
- **Idempotent per `(user_id, test_id)`** (approved decision — not per `result_id`): before creating, `CertificateRepository.get_by_user_and_test()` joins `certificates ⋈ results` to check whether this user already has *any* certificate for *this test*, regardless of which specific `result_id` it came from. Currently equivalent to a per-result check (since `attempts` enforces one attempt per user per test today), but stays correct automatically if that constraint is ever relaxed — tested explicitly (`test_issue_is_idempotent_per_user_and_test`).
- **`certificate_number` and `verification_code` are deliberately different values**, generated independently (`validators.py`): the certificate's internal reference number is never guessable from its public verification link, and vice versa. Tested explicitly (`test_verification_code_is_not_the_same_format_as_certificate_number`).
- **Public verification never leaks details for an invalid code** — `InvalidVerificationCodeException` is a generic 404, not "code not found" vs. "code expired" vs. any other distinguishing detail (anti-enumeration, same pattern used platform-wide).
- **Every verification check is recorded** (`verified_count`, `last_verified_at`, `last_verified_ip`) — gives the certificate holder and Admins a record of lookup activity without requiring the checker to authenticate.

## Database

Tables: `certificate_templates`, `certificates`, `certificate_verification` (Module 17, `database/schema/schema_v2.sql`). No schema change, no migration.

## API

Two routers, both registered in `api/router.py`:

```
POST /api/v1/certificates                      — issue (idempotent per user+test)   Authenticated
GET  /api/v1/certificates/me                      — list my own                          Authenticated
GET  /api/v1/certificates/{id}                      — get one (owner only)                  Authenticated
GET  /api/v1/certificates/verify/{code}               — PUBLIC verification                    Public, no auth
GET  /api/v1/certificate-templates                       — list active templates                  Public
POST /api/v1/certificate-templates                         — create a template                        Admin, Super Admin
```

Full Swagger descriptions on every endpoint.

## Flow — issue a certificate

```
POST /certificates {result_id, template_id?}
  → CertificateService.issue(result_id, user_id, template_id, actor_id)
      → result_repo.get_by_id(result_id)   [read-only, results module]
      → ownership check, is_passed check   [422 if failed]
      → repo.get_by_user_and_test(user_id, result.test_id)   [idempotency]
      → if existing: return existing
      → generate_certificate_number(), generate_verification_code()   [distinct, both random]
      → create Certificate(pdf_url=None)
      → create CertificateVerification(verified_count=0)
      → core.audit.log_action('certificate.issued')
      → commit
```

## Flow — public verification

```
GET /certificates/verify/{code}   [no auth]
  → VerificationService.verify(code, ip)
      → verification_repo.get_by_code(code)   [404 generic if not found]
      → cert_repo.get_by_id(verification.certificate_id)
      → record_check(): verified_count += 1, last_verified_at/ip updated
      → return {certificate_number, is_valid, verified_count}
```

## Tests

Two files, 12 tests: `test_certificate_service.py` (6 — rejects failed result, rejects wrong owner, idempotency keyed correctly on `(user_id, test_id)`, `pdf_url` is `None` on success, number/code are distinct, ownership check on read) and `test_verification_service.py` (6 — unknown code rejected, count increments, valid-certificate response shape, plus 3 pure-function tests for the generation logic: prefix/year format, code≠number, no collisions across 50 draws).

## Future improvements
- **PDF export** — pick a rendering approach (library or external service), populate `pdf_url` for real.
- **Email certificate delivery** — needs the `notifications` module (not yet built).
- **Public certificate verification page** — a frontend page consuming the already-working `GET /certificates/verify/{code}` API; no frontend work has started platform-wide yet.
- Template `design` (JSONB) is accepted and stored but has no rendering consumer yet — ties directly to the PDF export future work above.
