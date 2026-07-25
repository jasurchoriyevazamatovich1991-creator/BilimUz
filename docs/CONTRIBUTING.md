# Contributing to BilimUz

## Branch Strategy

- `main` — production, always deployable
- `develop` — integration branch, features merge here first
- `feature/*` — new features (e.g. `feature/tests-module`)
- `bugfix/*` — bug fixes
- `release/*` — release preparation
- `hotfix/*` — critical production fixes, branched from `main`

---

## Commit Style

Conventional Commits, scoped to the module when relevant:

```
feat:      new feature
fix:       bug fix
docs:      documentation only
style:     formatting, no logic change
refactor:  code change that neither fixes a bug nor adds a feature
test:      adding or correcting tests
perf:      performance improvement
ci:        CI/CD configuration
build:     build system or dependency changes
chore:     maintenance
```

Examples:
```
feat(auth): add device management (logout-all, sessions)
fix(subjects): exclude current row from duplicate-name check
docs(adr): record RBAC decision
test(subjects): add regression test for BUG-001
```

---

## Pull Request Requirements

Every PR must:

- [ ] Pass all automated tests (`pytest`, coverage ≥ 80% for the touched module, ≥ 90% for critical modules — `rules/09-testing-rules.md`)
- [ ] Pass review against `.cursor/prompts/07-reviewer.md` (Architecture, Backend, Security, Testing, Documentation at minimum)
- [ ] Include documentation — a new/changed module updates its own `README.md` (Architecture, Business Logic, Database, API, Flow, Security, Future Improvements)
- [ ] Include an Alembic migration if the schema changed — **never edit `database/schema/schema_v2.sql` in place after v1.0 ships**; schema changes after initial release go through `backend/alembic/versions/`
- [ ] Include a `docs/CHANGELOG.md` entry under `[Unreleased]`
- [ ] Include an ADR (`docs/ADR/ADR-0XX-*.md`) if the PR introduces a new technology, pattern, or reverses an existing ADR

A PR description should state: what changed, why, which module(s), and which `.cursor/rules/` or `.cursor/prompts/` it was reviewed against.

---

## Coding Rules

Every module follows `.cursor/prompts/01-architect.md` and `.cursor/rules/`:

- Clean Architecture / Layered Architecture (`router → dependencies → service → repository → database`)
- Repository Pattern — `service.py` never imports `sqlalchemy` directly (ADR-008)
- SOLID, DRY, KISS, YAGNI
- Maximum function length: **40 lines**
- Maximum file length: **300 lines**
- No duplicated code — if the same logic appears in two modules, it belongs in `core/`
- No magic numbers — belongs in the module's `constants.py`
- Type hints everywhere, no untyped `Any` without a documented reason
- Naming: `snake_case` for files/folders/functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants (`.cursor/rules/02-naming-conventions.md`)

## Before opening a PR — self-review checklist

Run through `.cursor/rules/05-security-checklist.md` and `.cursor/rules/10-review-checklist.md` yourself before requesting review. A PR that fails these on first review is sent back, not fixed in review comments — this keeps review cycles fast for everyone.

## Every module must contain

```
models.py, schemas.py, repository.py, service.py, router.py,
dependencies.py, validators.py, exceptions.py, constants.py,
tests/, README.md
```

See `backend/app/subjects/` as the reference implementation — copy its shape for new modules.
