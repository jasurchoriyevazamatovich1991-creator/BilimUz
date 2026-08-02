# BilimUz

Sun'iy intellekt yordamida ishlovchi onlayn ta'lim va test platformasi — o'qituvchilar, abituriyentlar, o'quvchilar uchun.

## Arxitektura
- **Backend**: FastAPI, feature-based modullar (`backend/app/modules/`) + Layered Architecture (Router → Service → Repository → Database), Clean Architecture tamoyillari bilan
- **Frontend**: React + TypeScript (Pages → Components → Services → API → Backend) — hali qurilmagan
- **Database**: PostgreSQL, 54 jadval, 25 modul, Alembic migratsiyalari bilan boshqariladi
- **Xavfsizlik**: Argon2 (parol xeshlash), JWT (`nbf` claim bilan) — `backend/app/core/security/`da markazlashgan yagona amalga oshirish (Sprint 4 Auth Cutover)

Batafsil: [`docs/00_Folder_Architecture.md`](docs/00_Folder_Architecture.md)

## Hujjatlar
| Bo'lim | Papka |
|---|---|
| Talablar (SRS) | `docs/SRS/` |
| Database | `docs/Database/` |
| API | `docs/API/` |
| UI/UX | `docs/UI-UX/` |
| Xavfsizlik | `docs/Security/` |
| Deploy | `docs/Deployment/` |
| Roadmap | `docs/Roadmap/` |
| Arxitektura qarorlari (ADR) | `docs/ADR/` |
| Jamoa qoidalari | [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) |
| O'zgarishlar tarixi | [`docs/CHANGELOG.md`](docs/CHANGELOG.md) |

`.cursor/` papkasi — AI yordamchilar (Cursor va h.k.) uchun rollar, qoidalar va joriy loyiha konteksti (`.cursor/prompts/`, `.cursor/rules/`, `.cursor/context/`).

## Holat

Kod yozish boshlangan va faol davom etmoqda.

| Bosqich | Qamrov | Holat |
|---|---|---|
| Sprint 1 — Foundation | FastAPI skeleti, `core/`, `db/`, Docker, Alembic, health/version endpointlar | ✅ Yakunlandi |
| Sprint 2 — Enterprise modul arxitekturasi | `auth`, `users`, `roles`, `permissions`, `subjects` — barchasi `backend/app/modules/` ostida | ✅ Yakunlandi |
| Sprint 3 — Argon2/JWT (izolyatsiyalangan sinov) | `PasswordService`, `JWTService`, Register/Login/Refresh/Me — alohida `-v2` yo'llarda qurildi va sinaldi | ✅ Yakunlandi, keyin birlashtirildi ↓ |
| Sprint 4 — Auth Cutover | Sprint 3'dagi Argon2/JWT `core/security/`ga ko'chirildi, `auth` moduli shu asosda qayta yozildi, `-v2` papkalar o'chirildi. **Endi faqat bitta auth tizimi bor.** | ✅ Yakunlandi |
| Sprint 5 — Education Core | `grades`, `topics`, `lessons` — to'liq CRUD, cross-module bog'lanish tekshiruvi (`topics→subjects/grades`, `lessons→topics`), 23 test | ✅ Yakunlandi |
| Sprint 6 — Test Engine | `tests`, `questions` (+options+media), `attempts` — to'liq test topshirish dvigateli: timer, randomizatsiya, scoring, lazy auto-finish, 47 test. Migratsiya `0002` | ✅ Yakunlandi |
| Sprint 7 — Results, Certificates, Analytics | `results` (reyting hisoblash dvigateli, leaderboard endpoint keyingi sprintga qoldirilgan), `certificates` (PDF'siz, idempotent), `analytics` (mustaqil, faqat `results`ni o'qiydi), 36 test | ✅ Yakunlandi |

To'liq qaror tarixi: [`docs/ADR/ADR-009-Auth-Cutover.md`](docs/ADR/ADR-009-Auth-Cutover.md).

**Ochiq eslatma**: test to'plami (100+ unit test) hali **haqiqiy Postgres muhitida ishga tushirilmagan** — faqat sintaksis va qo'lda tekshirilgan.

Reja: [`docs/Roadmap/roadmap_v1_to_v5.md`](docs/Roadmap/roadmap_v1_to_v5.md)
