# BilimUz — Cursor Role Prompts

Har bir qatlam ustida ishlaganda Cursor qanday "fikrlashi" kerakligini belgilaydi. Ish tartibi rollarning tabiiy ish oqimiga mos: Architect → Database → Backend → Frontend → Security → QA → Reviewer.

| Fayl | Rol | Qamrov |
|---|---|---|
| `01-architect.md` | Chief Software Architect | Umumiy arxitektura: Clean/Layered/DDD, texnologiya tanlovi |
| `02-database.md` | Chief Database Architect | PostgreSQL schema, normalizatsiya, audit ustunlari |
| `03-backend.md` | Chief Backend Engineer | FastAPI modul tuzilmasi, javob formati, testlash |
| `04-frontend.md` | Chief Frontend Engineer | React/TypeScript arxitekturasi, komponent qoidalari |
| `05-security.md` | Chief Security Engineer | Zero Trust, OWASP, rate-limit, audit, xavfsizlik headerlari |
| `06-qa.md` | Chief QA Engineer | Test strategiyasi, bug hisobotlari, regressiya |
| `07-reviewer.md` | Chief Reviewer / Principal Engineer | Yakuniy production-readiness review, ball berish, APPROVED/CHANGES REQUIRED qarori |

## Munosabat boshqa `.cursor/` papkalar bilan

- `../rules/` — bu rollarning **qat'iy, qisqa qoidalari** (masalan "300 qatordan oshmasin"). Promptlar *qanday fikrlash kerak*ligini, rules esa *aniq chegaralar*ni belgilaydi.
- `../context/` — loyihaning **joriy holati** (qaysi modul qurilgan, qaysi texnologiya haqiqatan ishlatilmoqda). Promptlar umumiy tamoyil, context — bugungi haqiqat.

## Muhim izoh

`04-frontend.md` dagi `src/` tuzilmasi hozirgi `frontend/src/` skeletidan biroz kengroq — frontend kod yozishni boshlaganimizda moslab qayta quriladi.

`05-security.md` talablari `auth` moduliga joriy qilindi. `06-qa.md` asosida `subjects` moduli tekshirildi va 3 ta bug topilib tuzatildi (`backend/app/subjects/tests/TEST_PLAN.md`). `07-reviewer.md` asosida birinchi to'liq platform review o'tkazildi — natija: **64/100, CHANGES REQUIRED** (asosiy sabab: Alembic yo'qligi va test suite hech qachon ishga tushirilmagani).
