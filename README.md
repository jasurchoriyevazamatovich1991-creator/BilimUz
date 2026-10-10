# BilimUz

## 1. BilimUz haqida

BilimUz — sun'iy intellekt yordamida ishlovchi onlayn ta'lim va test platformasi: o'qituvchilar, abituriyentlar va o'quvchilar uchun mo'ljallangan. Loyiha dastlab fizika fani uchun yaratilgan test tizimi sifatida boshlangan va ko'p sprintlar davomida generic (universal) imtihon dvigateliga aylantirilgan. Loyihaning to'liq, sprint-by-sprint rivojlanish tarixi [`docs/SPRINT_HISTORY.md`](docs/SPRINT_HISTORY.md) faylida saqlangan (bu fayl ilgari repository ildizidagi `README.md` bo'lgan).

## 2. Loyihaning maqsadi va asosiy imkoniyatlari

Quyidagilar faqat haqiqiy backend kodi (`backend/app/modules/`, 27 modul) va frontend sahifalari asosida, tasdiqlangan holda sanab o'tilgan:

- **Autentifikatsiya va RBAC**: ro'yxatdan o'tish, login, token-refresh, Argon2 parol xeshlash, JWT (`backend/app/core/security/`), 8 real rol (Super Admin, Admin, Moderator, Teacher, Applicant, Student, Parent, Guest).
- **Ta'lim tuzilmasi**: Fanlar (Subjects), Sinflar (Grades), Mavzular (Topics), Darslar (Lessons) — to'liq CRUD, cross-module bog'lanish tekshiruvi bilan.
- **Test/imtihon dvigateli**: testlar va savollar (`single_choice`, `multiple_choice`, `true_false`, `short_answer`, `essay`), variantlar, media, timer, savol/variantlarni aralashtirish, scoring, modul-darajasidagi adaptiv yo'naltirish (routing), modul-timer bilan avtomatik yakunlash.
- **Natijalar va sertifikatlar**: natijalarni hisoblash, bo'lim bo'yicha natija tahlili, PDF sertifikat generatsiyasi (QR-kod bilan tasdiqlash), reyting (ranking) hisoblash.
- **Media saqlash**: Cloudflare R2 orqali private, presigned upload/download, 2GB'gacha multipart yuklash (dars videosi, savol media, sertifikat PDF uchun) — yoki mahalliy disk (`STORAGE_BACKEND=local`, standart rejim).
- **Qo'shimcha modullar**: bildirishnomalar (notifications), sozlamalar (Fernet shifrlash bilan maxfiy maydonlar), audit/system loglar, AI interfeysi (vendor-agnostik, haqiqiy AI ulanishi yo'q — faqat interfeys), to'lovlar (payments, vendor-agnostik, idempotent), maktablar/o'quv markazlari katalogi, foydalanuvchi profillari, student progress (dars tugatish holati).
- **Admin panel**: barcha modullar uchun to'liq CRUD UI, imtihon tuzilmasini (bo'lim/modul/guruh) va adaptiv yo'naltirish qoidalarini sozlash UI.
- **Teacher panel**: kontent yaratish (fayl boshqaruvi UI'siz).
- **Student panel**: darslarni ko'rish, testlarni topshirish (shu jumladan modulli/adaptiv testlar), natijalar tarixi, sertifikatlar, progress.

Hali to'liq amalga oshirilmagan imkoniyatlar (haqiqiy holatni yashirmaslik uchun aniq ko'rsatilgan): xalqaro standartlashtirilgan imtihonlar (IELTS/SAT/GRE) uchun maxsus javob turlari va band/scaled-score konversiyasi, frontend code splitting. To'liq, joriy holat tafsilotlari uchun [`docs/SPRINT_HISTORY.md`](docs/SPRINT_HISTORY.md)ga qarang.

## 3. Texnologiyalar

**Backend** (`backend/`, haqiqiy `requirements.txt`dan tasdiqlangan):
- Python 3.13 (production Docker image — `backend/Dockerfile`'da `python:3.13-slim`; local dasturchi muhitida boshqa 3.x versiyasi ham ishlaydi, agar barcha paketlar mos bo'lsa)
- FastAPI `0.115.0`, Uvicorn `0.32.0`
- SQLAlchemy `2.0.35`, Alembic `1.13.3`, psycopg2-binary `2.9.9` (PostgreSQL)
- Pydantic `2.9.2`, pydantic-settings `2.5.2`
- Argon2 (`argon2-cffi` `23.1.0`, `passlib` `1.7.4`), PyJWT `2.9.0`, `cryptography` `43.0.3`
- Redis `5.1.1` (cache / rate-limiting)
- `boto3` `1.35.36` (Cloudflare R2 — faqat `STORAGE_BACKEND=r2` bo'lsa lazy-import qilinadi)
- `bleach` `6.1.0` (rich-text/XSS sanitizatsiya), `email-validator` `2.2.0`
- `reportlab` `4.2.5` (sertifikat PDF), `qrcode[pil]` `7.4.2` (sertifikat QR kodi)
- Testlar: `pytest` `8.3.3`, `httpx` `0.27.2`

**Frontend** (`frontend/package.json`dan tasdiqlangan):
- React `19.x` + TypeScript, Vite `6.x`
- TanStack Query (server state), Zustand (client state), Axios (HTTP)
- React Router `7.x`
- Tailwind CSS + shadcn/ui primitivlari, KaTeX (formula render)
- Testlar: Vitest `2.x` + Testing Library, ESLint

**Infratuzilma**: PostgreSQL 16 (Docker: `postgres:16-alpine`), Redis 7 (Docker: `redis:7-alpine`), Docker Compose (`docker-compose.yml`).

## 4. Loyiha papkalari tuzilmasi

Haqiqiy repository tuzilmasi (tasdiqlangan):

```
BilimUz/
├── backend/                 — FastAPI backend
│   ├── app/
│   │   ├── core/             — config, security, logging, middleware, exceptions
│   │   ├── api/               — API router, versiyalash, v1 prefiks
│   │   ├── db/                  — SQLAlchemy Base, session
│   │   └── modules/              — 27 feature-based modul (har birida router/service/
│   │                                repository/schemas/models) — masalan: auth, users,
│   │                                roles, permissions, subjects, grades, topics,
│   │                                lessons, tests, questions, attempts, results,
│   │                                certificates, analytics, notifications, settings,
│   │                                uploads, ai, payments, schools, learning_centers,
│   │                                profiles, progress, audit_logs, system_logs
│   ├── alembic/                     — migratsiyalar (`versions/`, 19 fayl: 0001–0019)
│   ├── alembic.ini
│   ├── conftest.py                    — pytest fixture'lar (DB, test client)
│   ├── scripts/                        — `seed_admin.py` (birinchi Super Admin yaratish)
│   ├── storage/                          — mahalliy fayl saqlash (STORAGE_BACKEND=local)
│   ├── tests/integration/                 — real PostgreSQL talab qiluvchi testlar
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── README.md
├── frontend/                 — React + TypeScript frontend
│   ├── src/
│   │   ├── api/                — Axios client + har-modul API funksiyalari
│   │   ├── components/           — qayta ishlatiladigan UI komponentlari
│   │   ├── hooks/                  — TanStack Query hook'lari
│   │   ├── layouts/                  — Public/Admin/Teacher/Student layout'lari
│   │   ├── pages/                      — admin/teacher/student/public sahifalar
│   │   ├── routes/                      — marshrutlash, RBAC guard
│   │   ├── store/                        — Zustand (auth, toast)
│   │   └── types/                         — `npm run generate:types` orqali generatsiya
│   ├── package.json
│   ├── .env.example
│   └── README.md
├── database/                 — `schema/schema_v2.sql` (ma'lumotlar bazasi sxemasi
│                                hujjatlashtiruvi), `migrations/`/`backups/`/`seeds/`
│                                (bo'sh — haqiqiy migratsiyalar `backend/alembic/`da)
├── docs/                      — SRS, Database, API, UI-UX, Security, Deployment,
│                                Roadmap, ADR, CONTRIBUTING, CHANGELOG (alohida,
│                                eski narrativ changelog), sprint arxitektura
│                                hujjatlari, va `SPRINT_HISTORY.md` (sprint-by-sprint
│                                to'liq holat arxivi — ilgari root README bo'lgan)
├── .github/workflows/         — hozircha bo'sh (`.gitkeep` — real CI workflow yo'q)
├── docker-compose.yml          — Postgres + Redis + backend uchun local dev stack
├── nginx/, docker/, scripts/    — hozircha bo'sh (`.gitkeep`)
├── .gitignore
├── LICENSE                       — bo'sh (hech qanday litsenziya belgilanmagan, pastga qarang)
├── CHANGELOG.md                   — bo'sh
└── README.md                       — shu fayl
```

## 5. Talablar va o'rnatish

Minimal talablar:
- Python 3.11+ (production image 3.13 ishlatadi; mahalliy dasturchi muhitida yangi 3.x versiyalar ham ishlaydi)
- Node.js 20+ va npm (frontend uchun; `package.json`'dagi React 19/Vite 6 talabiga mos)
- PostgreSQL 16 (local o'rnatilgan yoki Docker orqali)
- Redis 7 (local o'rnatilgan yoki Docker orqali)
- (Ixtiyoriy) Docker va Docker Compose — `docker-compose.yml` orqali Postgres+Redis+backend'ni bitta buyruq bilan ko'tarish uchun

Repository'ni clone/ZIP orqali oldingizdan so'ng, backend va frontend bo'limlarini quyida tasvirlangan tartibda alohida sozlang.

## 6. Backendni ishga tushirish

**A. Docker Compose orqali (Postgres + Redis + backend birga):**

```bash
docker-compose up -d
```

Bu `postgres` (port 5432), `redis` (port 6379) va `backend` (port 8000, `--reload` bilan) konteynerlarini ishga tushiradi. `docker-compose.yml` backend konteyneri uchun `ENVIRONMENT=development`ni aniq belgilaydi va `backend/.env` faylini (agar mavjud bo'lsa) o'qiydi.

**B. Mahalliy (venv) orqali:**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # keyingi bo'limga qarang — ENVIRONMENT va boshqa qiymatlarni sozlang
alembic upgrade head                # migratsiyalarni qo'llash — 9-bo'limga qarang
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ishga tushgandan so'ng: Swagger UI — `http://localhost:8000/docs`, OpenAPI sxema — `http://localhost:8000/api/v1/openapi.json`.

**Muhim**: `ENVIRONMENT` endi **majburiy** — agar u hech qayerda (muhit o'zgaruvchisi, `.env` fayli) belgilanmagan bo'lsa, backend ishga tushmaydi (8-bo'limga qarang).

Birinchi Super Admin foydalanuvchisini yaratish uchun (migratsiyalar qo'llanilgandan keyin):

```bash
cd backend
SUPERADMIN_EMAIL=admin@example.com SUPERADMIN_PASSWORD=YOUR_STRONG_PASSWORD python scripts/seed_admin.py
```

## 7. Frontendni ishga tushirish

```bash
cd frontend
npm install
cp .env.example .env               # VITE_API_BASE_URL — standart: http://localhost:8000/api/v1
npm run dev
```

Vite dev-server odatda `http://localhost:5173`da ishga tushadi. Backend ishlab turgan bo'lishi kerak (yuqoridagi 6-bo'lim).

**API tiplarini generatsiya qilish** (backend `/openapi.json`ni xizmat qilayotganda, ixtiyoriy, lekin `src/types/api.d.ts` fayli shu buyruq orqali yaratiladi):

```bash
npm run generate:types
```

**Production build**:

```bash
npm run build      # tsc -b && vite build — natija: frontend/dist/
npm run preview     # yig'ilgan build'ni mahalliy ko'rish uchun
```

## 8. Environment variables sozlash

Backend o'zining barcha sozlamalarini `backend/app/core/config.py`'dagi `Settings` klassidan oladi (`backend/.env` fayli orqali, `pydantic-settings`). Haqiqiy namuna fayl: [`backend/.env.example`](backend/.env.example) — undan nusxa ko'chiring (`cp backend/.env.example backend/.env`) va qiymatlarni to'g'rilang. **Hech qachon haqiqiy maxfiy qiymatlarni ushbu hujjatga yoki boshqa versiyalanadigan faylga yozmang.**

| O'zgaruvchi | Majburiy? | Tasvir |
|---|---|---|
| `ENVIRONMENT` | **Ha — majburiy, standart qiymat yo'q** | `development`, `staging` yoki `production`'dan biri bo'lishi shart. Bo'sh, bo'sh joy-only yoki ro'yxatda yo'q qiymat — backend ishga tushmaydi (fail-closed, Sprint 81 Package 1 Follow-up). `staging` va `production`'da quyidagi maxfiy kalitlar standart (placeholder) qiymatda qolsa, backend ishga tushishni rad etadi. |
| `APP_NAME` | Yo'q (standart: `BilimUz`) | Ilova nomi |
| `DEBUG` | Yo'q (standart: `false`) | Debug rejimi |
| `DATABASE_URL` | Yo'q (standart: local Postgres) | PostgreSQL ulanish satri (`postgresql+psycopg2://...`) |
| `REDIS_URL` | Yo'q (standart: local Redis) | Redis ulanish satri |
| `JWT_SECRET_KEY` | **production/staging'da ha** | JWT token imzolash kaliti — standart qiymat faqat local dev uchun xavfsiz |
| `JWT_ALGORITHM` | Yo'q (standart: `HS256`) | — |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | Yo'q | Token amal qilish muddati |
| `VERIFICATION_CODE_TTL_MINUTES` / `VERIFICATION_CODE_MAX_ATTEMPTS` | Yo'q | Tasdiqlash kodi sozlamalari |
| `FILE_ENCRYPTION_KEY` | **production/staging'da ha** | Fernet kaliti — `settings` modulidagi maxfiy maydonlarni shifrlash uchun. Generatsiya: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `STORAGE_BACKEND` | Yo'q (standart: `local`) | `local` yoki `r2` |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT` | Faqat `STORAGE_BACKEND=r2` bo'lsa, production/staging'da ha | Cloudflare R2 hisob ma'lumotlari |
| `ALLOWED_ORIGINS` | Yo'q (standart: `["http://localhost:5173"]`) | CORS uchun ruxsat etilgan origin'lar ro'yxati (JSON massiv) |

Frontend uchun: [`frontend/.env.example`](frontend/.env.example) — yagona o'zgaruvchi `VITE_API_BASE_URL` (standart: `http://localhost:8000/api/v1`).

## 9. Ma'lumotlar bazasini sozlash va migratsiyalar

Ma'lumotlar bazasi — PostgreSQL 16, 62 jadval. Haqiqiy migratsiyalar `backend/alembic/versions/`da joylashgan (19 fayl, `0001`'dan `0019`'gacha) — **`database/migrations/` papkasi bo'sh**, haqiqiy migratsiya mexanizmi emas; `database/schema/schema_v2.sql` esa sxemaning hujjatlashtiruvchi (ma'lumot) nusxasi, migratsiyalarni almashtirmaydi.

Migratsiyalarni qo'llash:

```bash
cd backend
alembic upgrade head
```

Alembic `backend/app/core/config.py`'dagi `DATABASE_URL`ni o'qiydi (`backend/alembic/env.py`), shuning uchun `.env` fayl to'g'ri sozlangan bo'lishi kerak. Yangi migratsiya yaratish:

```bash
alembic revision -m "tasvir"
```

(Avtogenerate — `--autogenerate` — ehtiyotkorlik bilan ishlatilsin: barcha modul modellari `alembic/env.py`da import qilingan bo'lishi kerak, aks holda mavjud jadvallar noto'g'ri DROP qilinishi mumkin.)

## 10. Testlarni ishga tushirish

**Backend** (venv faollashtirilgan holda, `backend/` papkasidan):

```bash
# To'liq unit/mock-asoslangan test to'plami (PostgreSQL/Redis talab qilinmaydi):
python -m pytest app/ -q

# Faqat yangi ENVIRONMENT/secret-safety testlari:
python -m pytest app/core/tests/ -q

# Real PostgreSQL integratsiya testlari (backend/tests/integration/) — ALOHIDA,
# TEST_DATABASE_URL muhit o'zgaruvchisi va ishlab turgan PostgreSQL talab qiladi
# (ma'lumotlar bazasi nomi "_test" bilan tugashi shart — backend/conftest.py
# shuni tekshiradi):
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/bilimuz_test \
    python -m pytest tests/integration/ -q
```

**Frontend** (`frontend/` papkasidan):

```bash
npm run test          # vitest run — bir martalik ishga tushirish
npm run test:watch     # vitest — watch rejimi
npm run lint            # ESLint
```

## 11. Production deployment bo'yicha mavjud cheklovlar

- `docker/`, `nginx/`, root-darajadagi `scripts/` papkalari hozircha **bo'sh** (faqat `.gitkeep`) — production uchun reverse-proxy konfiguratsiyasi, deployment skriptlari hali yozilmagan.
- `.github/workflows/` bo'sh (faqat `.gitkeep`) — **haqiqiy CI/CD workflow mavjud emas**. Testlar va linting hozircha faqat qo'lda ishga tushiriladi.
- `docker-compose.yml` faqat **local development** stacki — production-darajadagi Compose/Kubernetes konfiguratsiyasi (resurs limitlari, health-check'lar, secret boshqaruvi, TLS) alohida tayyorlanishi kerak.
- `ENVIRONMENT=production` (yoki `staging`) bilan ishga tushirishda, agar `JWT_SECRET_KEY` yoki `FILE_ENCRYPTION_KEY` (va `STORAGE_BACKEND=r2` bo'lsa, `R2_*` qiymatlari) standart (`CHANGE_ME_IN_PRODUCTION...`) qiymatda qolsa — backend ishga tushishni **rad etadi** (fail-closed xavfsizlik tekshiruvi, 8-bo'limga qarang). Bu — real production checklist emas, faqat eng kritik secret-default tekshiruvi.
- Xalqaro standartlashtirilgan imtihonlar (IELTS/SAT/GRE) uchun maxsus javob turlari va band/scaled-score konversiyasi hali amalga oshirilmagan.
- Email/SMS orqali haqiqiy xabar yuborish (notifications/verification) ataylab ulanmagan — joriy holatda tasdiqlash kodi API javobida ko'rinadi (`debug_code`), real email/SMS provayder integratsiyasi yo'q.
- To'liq production-darajadagi monitoring/alerting, log-aggregatsiya, backup/restore protsedurasi hujjatlashtirilmagan.

## 12. Xavfsizlik va maxfiy ma'lumotlar

- **Hech qachon** haqiqiy `.env` faylini, maxfiy kalitlarni, parollarni yoki foydalanuvchi ma'lumotlarini ushbu repository'ga commit qilmang. `.gitignore` `.env`, `venv/`/`.venv/`, `node_modules/`, `dist/`, `*.log`, `database/backups/*`, `uploads/*` kabi fayllarni istisno qiladi.
- `backend/.env.example` va `frontend/.env.example` fayllarida faqat xavfsiz placeholder qiymatlar bor (masalan, `change-me-to-a-random-64-char-string`) — bu reporsitoriyda hech qanday haqiqiy secret saqlanmaydi.
- Parollar Argon2 bilan xeshlanadi, JWT token'lar `nbf` claim bilan imzolanadi (`backend/app/core/security/`).
- `settings` moduli maxfiy maydonlarni Fernet (`FILE_ENCRYPTION_KEY`) bilan shifrlangan holda saqlaydi.
- Production/staging muhitida standart (CHANGE_ME) secret qiymatlari bilan ishga tushirish fail-closed tarzda bloklanadi (11-bo'limga qarang).
- Rich-text kiritish maydonlari (savol matni, variant matni, izoh, guruh stimulus matni) `bleach` allowlist-sanitizatsiyasidan o'tadi — XSS'ga qarshi.
- Repository'da `git ls-files` orqali tasdiqlangan: hech qanday `.env` fayli (root, backend yoki frontend) git tomonidan kuzatilmaydi — bu xavf hozircha yo'q.

## 13. Litsenziya

Repository ildizidagi `LICENSE` fayli **bo'sh** (0 bayt). **Loyiha uchun hech qanday litsenziya aniq belgilanmagan.** GitHub'ga chiqarishdan oldin loyiha egasi litsenziya turini (masalan, MIT, Apache 2.0, yoki "All rights reserved") tanlashi va ushbu faylni to'ldirishi tavsiya etiladi.

---

**Qo'shimcha hujjatlar**: [`backend/README.md`](backend/README.md) (backend uchun batafsil), [`frontend/README.md`](frontend/README.md) (frontend uchun batafsil), [`docs/SPRINT_HISTORY.md`](docs/SPRINT_HISTORY.md) (to'liq sprint-by-sprint tarix va joriy holat jadvali), [`docs/`](docs/) (SRS, Database, API, UI-UX, Security, Deployment, Roadmap, ADR, CONTRIBUTING).
