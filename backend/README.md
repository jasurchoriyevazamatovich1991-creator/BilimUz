# BilimUz Backend

FastAPI backend — feature-based modullar (`app/modules/`, 27 modul) + Layered Architecture (Router → Service → Repository → Database). To'liq loyiha konteksti va imkoniyatlar ro'yxati uchun repository ildizidagi [`README.md`](../README.md)ga qarang; sprint-by-sprint to'liq tarix — [`../docs/SPRINT_HISTORY.md`](../docs/SPRINT_HISTORY.md)da.

## O'rnatish

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Sozlash

```bash
cp .env.example .env
```

`.env` faylida eng muhim qiymatlarni to'g'rilang — to'liq jadval uchun root README'ning 8-bo'limiga qarang. Eslatma: **`ENVIRONMENT` endi majburiy** — `development`, `staging` yoki `production`'dan biri aniq berilishi shart; aks holda ilova (`uvicorn app.main:app` ham, `alembic` ham) ishga tushmaydi (Sprint 81 — Package 1 Follow-up, fail-closed konfiguratsiya). `staging`/`production`'da `JWT_SECRET_KEY` va `FILE_ENCRYPTION_KEY` (va, agar `STORAGE_BACKEND=r2` bo'lsa, `R2_*` qiymatlari) standart (`CHANGE_ME_IN_PRODUCTION...`) qiymatda qolsa, backend ishga tushishni rad etadi.

## Ma'lumotlar bazasi va migratsiyalar

PostgreSQL 16 talab qilinadi (local o'rnatilgan yoki Docker). Migratsiyalar `alembic/versions/`da (19 fayl, `0001`–`0019`):

```bash
alembic upgrade head
```

Yangi migratsiya yaratish: `alembic revision -m "tasvir"` (avtogenerate ehtiyotkorlik bilan — `alembic/env.py` har bir modulning `models.py`sini import qilgan bo'lishi kerak).

## Ishga tushirish

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Yoki repository ildizidan Docker Compose orqali (Postgres+Redis+backend birga): `docker-compose up -d`.

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI sxema: `http://localhost:8000/api/v1/openapi.json`

Birinchi Super Admin foydalanuvchisini yaratish (migratsiyalar qo'llanilgandan keyin, idempotent — ikkinchi marta ishga tushirish xavfsiz, duplikat yaratmaydi):

```bash
SUPERADMIN_EMAIL=admin@example.com SUPERADMIN_PASSWORD=YOUR_STRONG_PASSWORD python scripts/seed_admin.py
```

## Modullar (`app/modules/`, 27 ta)

`ai, analytics, attempts, audit_logs, auth, certificates, grades, learning_centers, lessons, notifications, payments, permissions, profiles, progress, questions, results, roles, schools, settings, subjects, system_logs, tests, topics, uploads, users`

Har bir modulda odatda `router.py`, `service.py`, `repository.py`, `schemas.py` va (kerak bo'lsa) `models.py` mavjud. Real endpointlar ro'yxati uchun `http://localhost:8000/docs` (Swagger UI, ishga tushirilgandan keyin) — eng ishonchli manba, chunki u haqiqiy routerlardan avtomatik generatsiya qilinadi.

## Testlash

```bash
# To'liq unit/mock-asoslangan to'plam — PostgreSQL/Redis talab qilinmaydi:
python -m pytest app/ -q

# Faqat ENVIRONMENT/secret-safety testlari (Sprint 81):
python -m pytest app/core/tests/ -q

# Real PostgreSQL integratsiya testlari — ALOHIDA, TEST_DATABASE_URL va
# ishlab turgan PostgreSQL talab qiladi (DB nomi "_test" bilan tugashi shart,
# conftest.py shuni tekshiradi):
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/bilimuz_test \
    python -m pytest tests/integration/ -q
```

Bu sandbox muhitida (GitHub Release Preparation vazifasi doirasida) oxirgi marta ishga tushirilganda: `app/` ostidagi to'liq mock/unit to'plam — **608 passed** (shundan 28 tasi `app/core/tests/`da — ENVIRONMENT/secret-safety testlari). `tests/integration/` — PostgreSQL/Redis ishlab turmagani sababli bu muhitda ishga tushirilmagan; TEST_DATABASE_URL'ga ega ishlab turgan PostgreSQL mavjud bo'lsa, boshqa muhitda ishga tushiriladi.

## Xavfsizlik eslatmalari

- `.env` faylini hech qachon commit qilmang (`.gitignore`da istisno qilingan).
- `backend/.env.example` faqat xavfsiz placeholder qiymatlarni o'z ichiga oladi — haqiqiy secretlarni hech qachon bu faylga yoki boshqa versiyalanadigan joyga yozmang.
- Production/staging'da standart secret qiymatlari bilan ishga tushirish ataylab bloklanadi — yuqoridagi "Sozlash" bo'limiga qarang.
