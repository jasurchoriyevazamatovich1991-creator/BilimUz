# Settings Module — BilimUz

Full design rationale: `docs/Sprint8_Notifications_Settings_Uploads_Architecture.md` (approved). The most security-sensitive module in the codebase.

## Architecture

Same 8-layer pattern as every module — **no new architectural layer**. Encryption is a service-level capability (`core/security/encryption.py`, same precedent as `jwt_service.py`/`password_service.py`), used *by* the repository layer, not a new layer between existing ones.

## ⚠️ The one rule this module must never break

**No GET endpoint, no schema, no log line ever contains a decrypted secret.** `SmtpSettingsOut`, `PaymentSettingsOut`, `AiSettingsOut` structurally have no `password`/`secret_key`/`api_key` field — proven by `tests/test_settings_schemas.py`, which asserts the field is absent from `model_fields`, not just checking a runtime value. Decrypted secrets exist only inside `get_decrypted_*()` repository methods, named deliberately differently from every other `get()` method so a call site is impossible to write by accident.

## Business rules

- **Encryption**: Fernet (`cryptography` library), key from `FILE_ENCRYPTION_KEY` (new `.env` variable, per approved decision). If this key is ever lost, every encrypted row becomes **permanently unreadable** — no recovery path, stated in three places (this README, `core/security/encryption.py`'s docstring, `.env.example`) because it's the single most consequential operational fact in this sprint.
- **`smtp_settings`/`ai_settings` are single-row configs** — `get()` returns the most recently updated row, `upsert()` updates in place if one exists. **`payment_settings` is one row per provider** (schema's `uq_payment_settings_provider` constraint), since a platform might configure both Click and Payme simultaneously.
- **Super Admin only, for both read and write**, on every provider-credential endpoint — even reading non-secret fields (`host`, `port`, provider name) is gated, since infrastructure topology is itself sensitive. This is stricter than every content-management module's Admin+SuperAdmin pattern.
- **`general_settings`** is the exception: Admin can read (not just Super Admin), since it's non-secret platform configuration (e.g. site name, feature flags) — only writes are Super Admin.

## Database

Tables: `general_settings`, `smtp_settings`, `payment_settings`, `ai_settings` (Module 22, `schema_v2.sql`). No schema change, no migration — encryption needed a new **environment variable**, not a new column (the `password`/`secret_key`/`api_key` columns already exist; they simply now store ciphertext instead of nothing).

## API

```
GET /PUT  /api/v1/settings/general[/{key}]      — Admin read, Super Admin write
GET /PUT  /api/v1/settings/smtp                   — Super Admin only, both directions
GET /PUT  /api/v1/settings/payment[/{provider}]     — Super Admin only, both directions
GET /PUT  /api/v1/settings/ai                         — Super Admin only, both directions
```

Full Swagger descriptions — every secret-adjacent endpoint's `description` explicitly states the secret field is absent from the response, not just relying on the schema itself.

## Flow — set SMTP configuration

```
PUT /settings/smtp {host, port, username, password, from_email}
  → SmtpSettingsService.upsert(...)
      → repo.upsert(...)
          → EncryptionService.encrypt(plaintext_password)   [core/security/]
          → store ciphertext
      → log_action('settings.smtp_updated')   [action only — never the password, not even encrypted]
      → commit
      → return SmtpSettingsOut   [no password field, structurally]
```

## Tests

Four files, 19 tests: `test_settings_schemas.py` (4 — the critical secret-omission proofs), `test_encryption_service.py` (5 — round-trip correctness, non-determinism of ciphertext, wrong-key failure, garbage-input failure), `test_settings_service.py` (5 — not-found cases, commit calls, plaintext-passthrough-to-repository confirmation), `test_settings_validators.py` (5 — key/port/secret validation boundaries).

## Future improvements
- `notifications` module (this same sprint) reads `SmtpSettingsRepository.get_decrypted_password()` read-only — the first real consumer of this module's decrypted-value pattern.
- A future `payments` module would read `PaymentSettingsRepository.get_decrypted_secret(provider)` the same way.
- Key rotation (re-encrypting all rows with a new `FILE_ENCRYPTION_KEY`) is not implemented — would be a one-time Admin-triggered operation, not attempted this sprint.
