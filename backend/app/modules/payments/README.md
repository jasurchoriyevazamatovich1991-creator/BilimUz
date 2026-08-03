# Payments Module — BilimUz

Full design rationale: `docs/Sprint9_AI_Payments_Architecture.md` (approved).

## Architecture

Same 8-layer pattern. `providers.py` (inside this module) defines `PaymentProvider` + `PaymentProviderRegistry` — same relationship `AIProvider`/`EmailProvider`/`StorageBackend` have to their services. **No vendor SDK import anywhere** (no `payme`, `click`, `stripe`, etc.) — verified as part of Sprint 9 validation.

## ⚠️ Approved scope boundary: no real payment vendor this sprint

`UnconfiguredPaymentProvider.initiate()`/`.verify_webhook()`/`.refund()` all raise `PaymentProviderNotConfiguredException` (501) — an honest refusal, not a fake success. Refusing to verify webhooks by default is also the **safe** default: an unconfigured provider must never accept unverified external input. A future sprint adds a real implementation (e.g. `ClickProvider`, `PaymeProvider`) and registers it in `PaymentProviderRegistry` via `get_payment_provider_registry()` — zero change to `PaymentService`.

## Business rules

- **Idempotency — approved decision, implemented at BOTH layers**:
  1. **Service-layer**: `TransactionRepository.get_by_provider_txn_id()` checked before every webhook-driven transaction insert — handles the common case cheaply.
  2. **Database-layer**: migration `0003` adds a partial `UNIQUE` index on `transactions.provider_txn_id` (`WHERE provider_txn_id IS NOT NULL`). This closes the race-condition gap the service-layer check alone cannot: two concurrent webhook deliveries could both pass the check before either commits. When the DB constraint rejects the second insert (`IntegrityError`), `PaymentService.handle_webhook()` catches it, rolls back, and returns the winning transaction — acknowledging idempotently instead of crashing. **Tested explicitly** (`test_webhook_race_condition_handled_via_integrity_error`) by simulating the exact race.
- **Refunds — full-amount only** (approved decision): `PaymentService.refund()` rejects a payment that isn't `status='success'` or is already `'refunded'`. No partial-amount tracking this sprint.
- **A refund is recorded as a new `transactions` row** (`status='refund_recorded'`) — **no new table needed**, reusing the existing `transactions` table's flexible event-log shape.
- **Every state transition is audit-logged** via the existing `core.audit.log_action()`: `payment.initiated`, `payment.webhook_received`, `payment.refunded`.
- **Webhook routing**: `POST /payments/webhook/{provider}` (approved path shape) dispatches via `PaymentProviderRegistry.get(provider_name)` — one endpoint, provider-specific verification happens inside each provider's own `verify_webhook()`, never done generically (different providers sign payloads differently).

## Database

Tables: `plans`, `subscriptions`, `payments`, `transactions` (Module 18, `schema_v2.sql`) — reused entirely, no new tables. **One migration this sprint**: `0003_unique_provider_txn_id.py` — adds the partial `UNIQUE` index described above. This is the first schema-changing migration since `0002` (Sprint 6).

## API

```
GET  /api/v1/payments/plans                     — list active plans                      Public
POST /api/v1/payments/plans                        — create a plan                           Admin, Super Admin
POST /api/v1/payments/subscriptions                   — subscribe                                Authenticated
GET  /api/v1/payments/subscriptions/me                  — my subscriptions                          Authenticated
POST /api/v1/payments/initiate                            — start a payment (501 this sprint)          Authenticated
GET  /api/v1/payments/me                                    — my payment history                          Authenticated
GET  /api/v1/payments/{id}                                    — one payment + transactions                  Authenticated (owner)
POST /api/v1/payments/webhook/{provider}                        — provider callback                            PUBLIC, no auth
POST /api/v1/payments/{id}/refund                                  — refund (501 this sprint)                     Admin, Super Admin
```

**The webhook endpoint has no `Depends(get_current_user)`** — this is intentional, not an oversight. It's documented explicitly in the endpoint's Swagger `description` and in `router.py`'s module docstring so it's never mistaken for a missed auth check during a future review.

## Flow — webhook idempotency (this sprint's actual, testable behavior)

```
POST /payments/webhook/{provider}
  → PaymentService.handle_webhook(provider, raw_body, headers)
      → registry.get(provider) → UnconfiguredPaymentProvider
      → provider.verify_webhook(...) → raises PaymentProviderNotConfiguredException   [this sprint]

  (future, once a real provider exists:)
      → result = provider.verify_webhook(...)   [signature verified, payload parsed]
      → txn_repo.get_by_provider_txn_id(result.provider_txn_id)
          → if found: return existing   [idempotent, no reprocessing]
      → try: create Transaction, update Payment.status, log_action(), commit
      → except IntegrityError (DB constraint caught a race the check missed):
          → rollback, re-fetch by provider_txn_id, return the winner
```

## Tests

Four files, 30 tests: `test_payment_validators.py` (11 — amount/currency/provider/plan-name/duration boundaries), `test_payment_providers.py` (6 — all three `PaymentProvider` methods honestly raise, registry dispatch, unknown-provider rejection, 501 status), `test_plan_subscription_service.py` (4 — plan CRUD, subscription end-date computed from plan duration), `test_payment_service.py` (9 — **the module's most important tests**: payment row created before provider call, webhook honestly raises when unconfigured, webhook idempotency returns the existing transaction without reprocessing, **the simulated race-condition test proving the `IntegrityError` recovery path**, unknown payment_id in a webhook rejected, refund state-machine guards, refund provider-not-configured, ownership check).

## Future improvements
- Real `PaymentProvider` implementations (`ClickProvider`, `PaymeProvider`, etc.) — each a future plugin, `PaymentService` unchanged.
- Partial refunds (deferred, approved) — would need amount-tracking validation (refunded total ≤ original amount across possibly-multiple partial refunds).
- `subscriptions → tests/certificates` access-gating integration (explicitly out of scope this sprint, approved) — a subscription doesn't yet unlock any content.
