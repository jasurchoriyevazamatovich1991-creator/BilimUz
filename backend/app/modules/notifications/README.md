# Notifications Module — BilimUz

Full design rationale: `docs/Sprint8_Notifications_Settings_Uploads_Architecture.md` (approved).

## Architecture

Same 8-layer pattern. One addition, `providers.py`, living **inside this module** — `EmailProvider`/`SmsProvider` (abstract interfaces) + `UnconfiguredEmailProvider`/`UnconfiguredSmsProvider` (the only implementations this sprint). Same relationship `StorageBackend` has to the `uploads` module — infrastructure the service depends on, **not a new architectural layer**.

## ⚠️ Approved scope boundary: no real SMTP or SMS sending this sprint

**`UnconfiguredEmailProvider`/`UnconfiguredSmsProvider` do not send anything.** Calling `.send()` raises `ProviderNotConfiguredException` (501) — an **honest refusal**, not a fake success. This was a deliberate, explicit decision, not a shortcut:

- Enqueueing (`POST /queue/email`, `/queue/sms`) is fully real — a row is genuinely created with `status='pending'`.
- Processing (`POST /queue/process/email`, `/process/sms`) is fully real *as an engine* — it fetches pending rows, calls the configured provider, and would correctly track `sent`/`failed`/`attempts` **if** a real provider existed. It just doesn't, yet.
- The **fail-fast** behavior in `QueueService._process_batch()` is the key design decision: `ProviderNotConfiguredException` propagates immediately (the whole batch stops, the caller gets a clear 501), while any *other* exception (a future real provider's transient failure) is caught per-item and doesn't stop the rest of the batch. Tested explicitly — `test_process_email_queue_propagates_provider_not_configured` vs. `test_process_email_queue_marks_transient_failures_without_stopping_batch` prove these are different code paths, not the same catch-all.

A future sprint adds a real implementation (e.g. `SmtplibEmailProvider`, an Eskiz/Play Mobile `SmsProvider`) and wires it in via `get_email_provider()`/`get_sms_provider()` — **zero change to `QueueService`**.

## Business rules

- **In-app notifications never touch the queue tables** — `POST /notifications` writes directly to `notifications`, no delivery step.
- **Enqueueing is NOT idempotent** — unlike `results`/`certificates`'s idempotent-create pattern, calling `POST /queue/email` twice creates two rows. This is correct: queueing the same email twice is a valid use case (e.g. resending), tested explicitly (`test_enqueue_is_not_deduplicated`) to prove it's a deliberate difference, not an inconsistency.
- **A row past `MAX_SEND_ATTEMPTS` (5) stops retrying** — stays `failed` permanently rather than being retried forever.
- **`notification_templates.code` is unique** (schema-enforced, re-checked at the service layer for a clean 409 instead of a raw DB error).

## Database

Tables: `notification_templates`, `notifications`, `email_queue`, `sms_queue` (Module 19, `schema_v2.sql`). No schema change, no migration. **One model-layer correction made during development**: `EmailQueueItem`/`SmsQueueItem` do NOT use `StatusMixin` (unlike every other model in this sprint) — both tables have their own domain-specific `status` (the `queue_status` enum: pending/sent/failed), and `StatusMixin`'s own docstring explicitly says tables with their own status column should not use it. Caught and fixed before this module was considered complete.

## API

```
GET   /api/v1/notifications/me                    — list mine, ?is_read=          Authenticated
PATCH /api/v1/notifications/{id}/read                — mark one read                   Authenticated (owner)
PATCH /api/v1/notifications/me/read-all                — mark all mine read                Authenticated
POST  /api/v1/notifications                              — create for a user                  Admin, Super Admin
GET   /api/v1/notifications/templates                      — list templates                      Admin, Super Admin
POST  /api/v1/notifications/templates                        — create a template                    Admin, Super Admin
POST  /api/v1/notifications/queue/email                        — enqueue an email                      Admin, Super Admin
POST  /api/v1/notifications/queue/sms                             — enqueue an SMS                         Admin, Super Admin
POST  /api/v1/notifications/queue/process/email                     — delivery engine trigger (501 this sprint) Admin, Super Admin
POST  /api/v1/notifications/queue/process/sms                         — delivery engine trigger (501 this sprint) Admin, Super Admin
```

## Flow — process the email queue (this sprint's actual behavior)

```
POST /notifications/queue/process/email {batch_size}
  → QueueService.process_email_queue(batch_size)
      → email_repo.list_pending(batch_size)
      → for each item: UnconfiguredEmailProvider.send(...)
          → raises ProviderNotConfiguredException immediately
      → exception propagates → router → 501 response
      → (rows stay 'pending' — nothing was faked as 'sent')
```

## Tests

Four files, 24 tests: `test_notification_validators.py` (8 — channel, email, phone [reusing `auth.validators`], title, template code), `test_providers.py` (3 — both Unconfigured providers genuinely raise rather than silently succeed, exception is a 501), `test_notification_service.py` (6 — mark-read ownership, mark-all-read count, create, template duplicate-code rejection and success), `test_queue_service.py` (7 — enqueue always succeeds and is NOT deduplicated, fail-fast on unconfigured provider, transient-failure batch resilience, SMS uses the SMS provider not email).

## Future improvements
- Real `EmailProvider` implementation (`smtplib`, reading decrypted config from the `settings` module's `SmtpSettingsRepository`) — the architecture's `notifications → settings` read dependency is a documented **future** integration point, not code that exists yet (there's nothing to configure a non-existent real provider with).
- Real `SmsProvider` implementation — needs a business decision on which Uzbek SMS gateway to use (Eskiz, Play Mobile, etc.), out of this module's scope.
- `auth → notifications` wiring — replacing the Sprint 1 `# TODO(notifications module)` in `auth/router.py` with a real call, once a real SMS provider exists (sending a real SMS requires both this module AND a real provider — neither alone is sufficient).
