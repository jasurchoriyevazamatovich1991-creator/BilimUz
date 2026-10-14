# AI Module — BilimUz

Full design rationale: `docs/Sprint9_AI_Payments_Architecture.md` (approved).

## Architecture

Same 8-layer pattern. `providers.py` (inside this module) defines `AIProvider` — same relationship `EmailProvider`/`StorageBackend` have to their services (Sprint 8). **No vendor SDK import anywhere** (no `openai`, `anthropic`, `google-generativeai`, etc.) — verified as part of Sprint 9 validation.

## Real AI provider (Sprint 88)

`AnthropicProvider` (`providers.py`) is the first real `AIProvider` implementation — calls Anthropic's Messages API directly over plain `httpx` (no vendor SDK added as a dependency). Wired in via `get_ai_provider()`/`select_ai_provider()` (`dependencies.py`) — **zero change to `AIChatService`**, exactly as the Sprint 9 docstring said a future sprint would do.

**Opt-in only**: `AI_PROVIDER` defaults to `"none"` — `UnconfiguredAIProvider.generate()` still raises `AIProviderNotConfiguredException` (501, an honest refusal, never a fake response) unless `AI_PROVIDER=anthropic` is explicitly set AND `AI_API_KEY` is a real key (not left at its public placeholder default — `select_ai_provider()` checks this and falls back to `UnconfiguredAIProvider` otherwise, so a half-configured deployment fails with a clear 501, never a confusing provider-side 401). See root/backend README for the full environment-variable table and how to obtain a key.

Every provider failure mode (not configured, provider auth failure, provider rate-limited, timeout, unavailable) is now a subclass of `AIProviderException` (`exceptions.py`) — `AIChatService.send_message` catches that one base class and logs usage the same way for all of them (`exc.error_code.lower()`), never the prompt or response content.

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
POST /api/v1/ai/chats/{id}/messages               — send a message, rate-limited                     Authenticated (owner), 10/min
GET  /api/v1/ai/recommendations/me                  — my recommendations                                Authenticated
GET  /api/v1/ai/study-plans/me                        — my study plans                                      Authenticated
POST /api/v1/ai/study-plans                             — create a study plan                                  Authenticated
```

## Flow — send a message

```
POST /ai/chats/{id}/messages {content}
  → rate_limit_by_user('ai_message', 10, 60)   [auth module, reused mechanism]
  → AIChatService.send_message(chat_id, user_id, content)
      → ownership check
      → history = history_repo.list_recent_for_context(chat_id)   [bounded, oldest-first]
      → save the user's message FIRST (never lost even if the provider call fails)
      → provider.generate(request)
          → AI_PROVIDER=none (default) or AI_API_KEY still a placeholder:
              UnconfiguredAIProvider raises AIProviderNotConfiguredException → 501
          → AI_PROVIDER=anthropic + a real key: AnthropicProvider calls the
            real Messages API (bounded by AI_REQUEST_TIMEOUT_SECONDS) and
            either returns a real AIResponse, or raises one of
            AIProviderAuthenticationException (502) / AIProviderRateLimitedException (429) /
            AIProviderTimeoutException (504) / AIProviderUnavailableException (503) /
            AIProviderException (502, generic upstream failure)
      → on failure (any AIProviderException subclass): log_action('ai.message_sent',
        metadata={status: exc.error_code.lower(), ...}) → commit → exception propagates
      → on success: save the assistant's message, log_action(..., status: 'success',
        provider, model, tokens_used) → commit → 200 response (MessageResponseOut, unchanged contract)
```

## Tests

Four files, 16 tests: `test_ai_validators.py` (6 — message length boundaries, date-range validation), `test_ai_providers.py` (3 — honest refusal, 501 status, history carried in `AIRequest`), `test_ai_chat_service.py` (7 — ownership, provider-not-configured propagation, usage logged on failure, user message saved before provider call, successful two-message save, prior history correctly assembled as context), `test_study_plan_service.py` (3 — including a duplicate of the schema-level date validation, intentionally, to prove both layers agree).

## Future improvements
- Additional `AIProvider` implementation(s) — e.g. `OpenAIProvider` — each a separate future plugin, `AIChatService` unchanged (same pattern `AnthropicProvider` just proved).
- Token-cost budgeting beyond `AI_MAX_OUTPUT_TOKENS` (usage is *logged*, request-rate and output-length are *limited*, but there is no running cost/spend budget this sprint).
- `subjects`-scoped recommendation generation (currently `ai_recommendations.subject_id` exists in the schema and is exposed in `RecommendationOut`, but nothing generates a recommendation yet — that's tied to having a real provider).
