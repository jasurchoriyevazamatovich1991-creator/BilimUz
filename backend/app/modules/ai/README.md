# AI Module — BilimUz

Full design rationale: `docs/Sprint9_AI_Payments_Architecture.md` (approved).

## Architecture

Same 8-layer pattern. `providers.py` (inside this module) defines `AIProvider` — same relationship `EmailProvider`/`StorageBackend` have to their services (Sprint 8). **No vendor SDK import anywhere** (no `openai`, `anthropic`, `google-generativeai`, etc.) — verified as part of Sprint 9 validation.

## ⚠️ Approved scope boundary: no real AI vendor this sprint

`UnconfiguredAIProvider.generate()` raises `AIProviderNotConfiguredException` (501) — an honest refusal, not a fake response. A future sprint adds a real implementation and wires it in via `get_ai_provider()` — zero change to `AIChatService`.

## Business rules

- **Rate limiting**: `POST /chats/{id}/messages` is limited to **10 requests/minute per authenticated user** (approved decision) via a new `rate_limit_by_user()` dependency added to `app/modules/auth/dependencies.py` — reuses the exact same Redis INCR/EXPIRE mechanism as the existing IP-based `core/middleware/rate_limit.py`, just keyed by `user_id` instead of IP. **Not a new rate-limiting system** — the existing `rate_limit()` (IP-only) couldn't express "per user," so a second, narrowly-scoped function was added alongside it, never modifying the original.
- **Message length**: capped at **4000 characters** (approved decision), validated at the schema layer.
- **Usage logging reuses the existing `audit_logs` table** via `core.audit.log_action()` — action `ai.message_sent`, with `metadata` carrying `{chat_id, status, provider, model, tokens_used}`. **No new table** — per the explicit approved decision to not introduce an AI-specific usage table this sprint.
- **Usage is logged on both success AND failure** (`AIProviderNotConfiguredException`) — a refused call is still a usage-relevant signal (tells you rate limits or configuration gaps are being hit), tested explicitly.
- **The user's message is always saved before the provider is called** — even when the provider call fails, the user never loses what they typed (tested explicitly, `test_send_message_persists_user_message_before_calling_provider`).
- **Conversation history is bounded** (`MAX_HISTORY_MESSAGES_FOR_CONTEXT = 20`) when assembled as context for the provider — an ever-growing conversation doesn't send unbounded context to a future real (and likely token-billed) provider.

## Database

Tables: `ai_chats`, `ai_history`, `ai_recommendations`, `study_plans` (Module 21, `schema_v2.sql`). No schema change, no migration.

## API

```
POST /api/v1/ai/chats                       — start a conversation                    Authenticated
GET  /api/v1/ai/chats/me                      — list mine                                 Authenticated
GET  /api/v1/ai/chats/{id}                      — get + full history                          Authenticated (owner)
POST /api/v1/ai/chats/{id}/messages               — send a message (501 this sprint), rate-limited  Authenticated (owner), 10/min
GET  /api/v1/ai/recommendations/me                  — my recommendations                                Authenticated
GET  /api/v1/ai/study-plans/me                        — my study plans                                      Authenticated
POST /api/v1/ai/study-plans                             — create a study plan                                  Authenticated
```

## Flow — send a message (this sprint's actual behavior)

```
POST /ai/chats/{id}/messages {content}
  → rate_limit_by_user('ai_message', 10, 60)   [auth module, reused mechanism]
  → AIChatService.send_message(chat_id, user_id, content)
      → ownership check
      → history = history_repo.list_recent_for_context(chat_id)   [bounded, oldest-first]
      → save the user's message FIRST
      → UnconfiguredAIProvider.generate(request) → raises AIProviderNotConfiguredException
      → log_action('ai.message_sent', metadata={status: 'provider_not_configured', ...})
      → commit → exception propagates → 501 response
```

## Tests

Four files, 16 tests: `test_ai_validators.py` (6 — message length boundaries, date-range validation), `test_ai_providers.py` (3 — honest refusal, 501 status, history carried in `AIRequest`), `test_ai_chat_service.py` (7 — ownership, provider-not-configured propagation, usage logged on failure, user message saved before provider call, successful two-message save, prior history correctly assembled as context), `test_study_plan_service.py` (3 — including a duplicate of the schema-level date validation, intentionally, to prove both layers agree).

## Future improvements
- Real `AIProvider` implementation(s) — e.g. `OpenAIProvider`, `AnthropicProvider` — each a separate future plugin, `AIChatService` unchanged.
- Token-cost budgeting (usage is *logged*, not *cost-limited*, this sprint — only request-rate is limited).
- `subjects`-scoped recommendation generation (currently `ai_recommendations.subject_id` exists in the schema and is exposed in `RecommendationOut`, but nothing generates a recommendation yet — that's tied to having a real provider).
