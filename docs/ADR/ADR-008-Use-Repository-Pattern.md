# ADR-008

## Title
Use the Repository Pattern to isolate all database access

## Status
Accepted — implemented in every module built so far (`auth/repository.py`, `subjects/repository.py`)

## Context
`service.py` in every module needs to run queries (filter, search, sort, paginate, create, update, soft-delete) without becoming coupled to SQLAlchemy's query syntax directly. Without this separation, business-rule tests (e.g. "reject a duplicate subject name") would require a real database connection just to exercise logic that has nothing to do with SQL — exactly the situation the QA Engineer prompt's "Unit Testing" section is designed to avoid.

## Decision
Every module gets a `Repository` class (e.g. `SubjectRepository`) that owns 100% of the SQLAlchemy `select`/`insert`/`update` statements for its table(s). `Service` classes depend on a `Repository` instance (constructor injection via FastAPI's `Depends()` chain) and never import `sqlalchemy` directly.

## Consequences

**Positive:**
- Every service-layer unit test (`test_subject_service.py`, `test_auth_service.py`) mocks the repository with `unittest.mock.MagicMock()` and runs with **zero database connection** — this is precisely why 20+ unit tests could be written and syntax-verified in this environment despite having no running PostgreSQL instance at all.
- Query construction bugs are isolated to one file per module — when BUG-001 was found during QA review (self-collision in `get_by_name` during rename), the fix was a two-line change in `repository.py` with zero risk to `service.py`'s business logic.
- If the ORM itself is ever replaced (e.g. SQLAlchemy → a different query builder, or raw SQL for a performance-critical path), only `repository.py` files change — `service.py`, `router.py`, and all business-logic tests are untouched. Documented explicitly in both module READMEs as the payoff of this pattern.

**Negative:**
- A thin extra layer for genuinely simple CRUD — `SubjectRepository.get_by_id()` is a one-line wrapper around a `select()`. Accepted because the discipline pays for itself the moment a repository method needs to change (as BUG-001 demonstrated within the first two modules built).
- Repositories currently return SQLAlchemy model instances, not plain dataclasses — a lighter "pure domain object" boundary would be even more decoupled, but was judged unnecessary complexity for the current stage (see ADR-005's DDD trade-off note).

## Alternatives

| Option | Rejected because |
|---|---|
| Active Record (query methods directly on the model, e.g. `Subject.objects.filter(...)`) | Couples the domain model to persistence concerns; makes service-layer unit testing require a real DB or heavy mocking of the model class itself |
| Query logic inline in `service.py` | Explicitly forbidden by both the Backend Engineer prompt ("Repositories communicate with Database... Never bypass layers") and the Architect prompt |
| Generic/base repository with reflection-based CRUD | Considered for DRY, but each module's list/filter/search needs (see `SubjectRepository.list()`) are different enough that a one-size-fits-all base class would need constant overriding, negating the DRY benefit |

## References
- `.cursor/prompts/01-architect.md`, `.cursor/prompts/03-backend.md`
- `backend/app/subjects/repository.py`, `backend/app/auth/repository.py`
- `backend/app/subjects/tests/TEST_PLAN.md` (BUG-001 regression, direct evidence of this pattern's value)
