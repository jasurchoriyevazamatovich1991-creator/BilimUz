# Test Plan — Subjects Module

## Test coverage summary

| Layer | File | Status |
|---|---|---|
| Validators (boundary, invalid, valid) | `test_subject_validators.py` | ✅ Runnable now (pure functions) |
| Schema validation (Pydantic) | `test_subject_schemas.py` | ✅ Runnable now |
| Service / business logic (mocked repo) | `test_subject_service.py` | ✅ Runnable now |
| API / integration (real DB, status codes, RBAC, pagination) | *(see below)* | ⏳ Requires a running Postgres — not executable in this environment |

**Honest note**: models use PostgreSQL-specific types (`UUID`, `INET`), so they cannot run against SQLite in-memory for a quick integration test — that would test a different database engine's behavior, which is worse than no integration test. The scenarios below are written and ready; they run in CI against a real Postgres service container (`docs/Deployment` — not yet written) or a local `docker-compose up postgres`.

## Bugs found in this review

| ID | Severity | Priority | Status |
|---|---|---|---|
| BUG-001 | Medium | High | ✅ Fixed — `get_by_name` now excludes the row being updated |
| BUG-002 | Medium | High | ✅ Fixed — `status` validated against `ALLOWED_STATUS_VALUES` |
| BUG-003 | Low (test quality) | Medium | ✅ Fixed — `MagicMock(name=...)` pitfall corrected |

## Risk-based scenario matrix (API level — ready for CI)

### Authentication & Authorization
| # | Scenario | Expected |
|---|---|---|
| A1 | `POST /subjects` with no Authorization header | `401` |
| A2 | `POST /subjects` with a Student's valid token | `403` |
| A3 | `POST /subjects` with an Admin token | `201` |
| A4 | `PATCH/DELETE /subjects/{id}` with Teacher token | `403` |
| A5 | `GET /subjects` with no token at all | `200` (public) |

### Validation
| # | Scenario | Expected |
|---|---|---|
| V1 | `name` = 1 char (below `MIN_NAME_LENGTH`) | `422` |
| V2 | `name` = 151 chars (above `MAX_NAME_LENGTH`) | `422` |
| V3 | `color` = `"red"` (not hex) | `422` |
| V4 | `status` = `"banana"` | `422` (BUG-002 regression) |
| V5 | `name` = `"   "` (whitespace only) | `422` |
| V6 | `name` contains emoji / non-Latin script (e.g. `"Матем@тика 数学"`) | `201` — Unicode subject names are valid (Uzbek/Russian/English all in use) |

### Business rules
| # | Scenario | Expected |
|---|---|---|
| B1 | Create subject with a name that already exists (any case) | `409` |
| B2 | Rename a subject to a different case of its own name | `200` (BUG-001 regression) |
| B3 | Delete a subject, then `GET /subjects/{id}` | `404` (soft-deleted, excluded) |
| B4 | Delete a subject, then create a new one with the same name | `201` — deleted names are not blocked |

### Pagination / Sorting / Filtering / Searching
| # | Scenario | Expected |
|---|---|---|
| P1 | `GET /subjects?page=0` | `422` (`page` has `ge=1`) |
| P2 | `GET /subjects?per_page=101` | `422` (`le=100`) |
| P3 | `GET /subjects?search=mat` | Only subjects with "mat" in the name (case-insensitive) |
| P4 | `GET /subjects?status=archived` | Only archived subjects |
| P5 | `GET /subjects?sort=malicious_field` | Falls back to `-created_at`, no `500` |
| P6 | `GET /subjects?sort=name` then `?sort=-name` | Ascending vs descending order confirmed |
| P7 | 25 subjects seeded, `per_page=10` | `meta.total_pages == 3` |

### Error response shape
| # | Scenario | Expected |
|---|---|---|
| E1 | Any `4xx`/`5xx` | Body matches `{success: false, message: str, data: null, errors: [...]}` |
| E2 | `500`-class failure (simulate DB down) | No stack trace, SQL, or file path in response body |

## Automation approach

- **Unit tests** (validators, schemas, service): pure Python + `pytest`, no external dependencies — run on every commit, <1s total.
- **API tests**: `httpx.AsyncClient` against a live app instance + Postgres test container in CI, one transaction per test rolled back after (fast, isolated).
- **Regression suite**: this module's tests are added to `docs/Roadmap` pre-release checklist (see QA prompt's "Regression Testing" module list) — re-run before every release once other modules exist.

## Coverage target

Current unit-test line coverage of `subjects/service.py` + `subjects/validators.py` + `subjects/schemas.py`: effectively 100% of branches (every `if`/`raise` has a dedicated test). API-level coverage (RBAC, pagination, DB constraints) is planned but not yet executed — tracked as a known gap, not silently assumed complete.

## Future test improvements

- Property-based testing (Hypothesis) for `validate_subject_name`/`validate_hex_color` instead of hand-picked boundary values.
- Load test: `GET /subjects` with 100k rows seeded, verify `p95` response time (Performance Testing requirement).
- Contract test between `docs/API/api_blueprint.md` and the actual OpenAPI schema (`/api/v1/openapi.json`) so documentation drift is caught automatically.
