# BilimUz

Sun'iy intellekt yordamida ishlovchi onlayn ta'lim va test platformasi — o'qituvchilar, abituriyentlar, o'quvchilar uchun.

## Arxitektura
- **Backend**: FastAPI, feature-based modullar (`backend/app/modules/`) + Layered Architecture (Router → Dependencies → Service → Repository → Database), Clean Architecture tamoyillari bilan
- **Frontend**: React + TypeScript (Pages → Components → Services → API → Backend) — hali qurilmagan
- **Database**: PostgreSQL, 54 jadval, 25 modul, Alembic migratsiyalari bilan boshqariladi

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
| Sprint 2 — Enterprise modul arxitekturasi | `auth`, `users`, `roles`, `permissions`, `subjects` — barchasi `backend/app/modules/` ostida, bir xil qatlamli naqsh bilan | ✅ Yakunlandi |
| Sprint 3 — Izolyatsiyalangan Argon2/JWT autentifikatsiya | `PasswordService` (Argon2), `JWTService`, Register/Login/Refresh/Me API'lari — mavjud tizimga parallel, alohida yo'llarda (`/auth/registration`, `/auth/login-v2` va h.k.) | ✅ Yakunlandi |

**Muhim, ochiq eslatma**: Sprint 3 mavjud (bcrypt asosidagi) autentifikatsiya tizimini **almashtirmadi** — ikkalasi hozircha parallel mavjud. Qaysi birini asosiy qilish (yoki ikkalasini saqlab qolish) — hali qabul qilinmagan mahsulot qarori (batafsil: har bir `backend/app/modules/auth/{security,jwt,registration,login,refresh,me}/README.md`). Shuningdek, test to'plami (100+ unit test) hali **haqiqiy Postgres muhitida ishga tushirilmagan** — faqat sintaksis va qo'lda tekshirilgan.

Reja: [`docs/Roadmap/roadmap_v1_to_v5.md`](docs/Roadmap/roadmap_v1_to_v5.md)
