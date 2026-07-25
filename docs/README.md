# BilimUz Documentation

## Structure

| Folder/File | Contents |
|---|---|
| `ADR/` | Architecture Decision Records — why each major technical choice was made, alternatives considered |
| `API/` | API Blueprint — endpoint contract, response envelope, auth flow |
| `Database/` | Database Blueprint, ER Diagram |
| `Security/` | *(planned)* RBAC matrix, JWT policy, audit strategy |
| `UI-UX/` | Page inventory, panel modules per role, design tokens |
| `Deployment/` | *(planned)* Docker, CI/CD, hosting |
| `CONTRIBUTING.md` | Branch strategy, commit style, PR requirements, coding rules |
| `CHANGELOG.md` | What's been built, version by version, with honest status markers |
| `00_Folder_Architecture.md` | Full repo layout, backend/frontend folder conventions |

## Where to start

- **New to the project?** Read `.cursor/context/01-project-overview.md` first, then `00_Folder_Architecture.md`.
- **Contributing code?** Read `CONTRIBUTING.md`, then the relevant module's own `README.md` under `backend/app/{module}/`.
- **Wondering why a technology or pattern was chosen?** Check `ADR/` before asking — the reasoning and rejected alternatives are already written down.
- **Wondering what's actually built vs. planned?** `.cursor/context/05-system-modules.md` and `CHANGELOG.md` are the two sources of truth — both are kept honest (✅/🟡/❌ status markers), never aspirational.

## Relationship to `.cursor/`

`docs/` is the durable, versioned record of *what was decided and why* (ADRs) and *what exists* (blueprints, changelog). `.cursor/` is the operational layer that tells Cursor/AI assistants *how to work* on this codebase day to day (prompts, rules, live context). They reference each other constantly — an ADR will point to the prompt that motivated it; a `.cursor/context/` file will point to the `docs/` blueprint with full detail.
