# Folder Architecture v1.0 — BilimUz

Bu hujjat loyiha 5–10 yil davomida rivojlantirilsa ham tartibli qolishi uchun ishlab chiqilgan tuzilmani belgilaydi.

## Repo ildizi

```
BilimUz/
├── docs/            # Hujjatlar (bo'lim bo'yicha papkalar)
├── backend/         # FastAPI, feature-based + Layered Architecture
├── frontend/        # React + TypeScript
├── database/        # SQL schema, migratsiya, seed, backup
├── uploads/          # Yuklangan fayllar (dev muhitida; prod'da S3/MinIO)
├── docker/            # Har bir servis uchun Dockerfile'lar
├── nginx/              # Reverse proxy konfiguratsiyasi
├── scripts/             # Yordamchi skriptlar (backup, seed, deploy)
├── .github/workflows/    # CI/CD
├── docker-compose.yml
├── README.md
├── LICENSE
├── .gitignore
└── CHANGELOG.md
```

## `docs/` — bo'lim bo'yicha papkalar

Har bir mavzu endi bitta fayl emas, **bitta papka** — chunki loyiha o'sgani sari (5–10 yil) har bir bo'lim bir nechta hujjatga bo'linadi:

```
docs/
├── SRS/            # Software Requirements Specification (funksional talablar, user stories)
├── Database/        # Database Blueprint, jadval lug'ati
├── API/               # API Blueprint, endpoint referensi, Postman kolleksiya
├── UI-UX/              # Sahifalar, wireframe, dizayn tokenlari
├── Security/            # RBAC matritsasi, JWT siyosati, audit
├── Deployment/            # Docker, CI/CD, hosting
└── Roadmap/                # v1.0 dan v5.0 gacha reja
```

## `backend/` — Feature-based + Layered Architecture

**Ikki tamoyil birlashtirilgan:**
1. **Feature-based** — har bir domen (`tests`, `users`, `payments`...) o'z papkasiga ega, bir-biriga aralashmaydi.
2. **Layered Architecture** — har bir domen papkasi ichida so'rov shu zanjir bo'ylab o'tadi:

```
API  →  Controller  →  Service  →  Repository  →  Database
```

| Qatlam | Vazifasi | Nima qilmaydi |
|---|---|---|
| **API** (`router.py`) | HTTP so'rovni qabul qiladi, Pydantic bilan validatsiya, controller'ni chaqiradi | Biznes-logika yozmaydi, SQL yozmaydi |
| **Controller** (`controller.py`) | So'rov/javobni orkestratsiya qiladi, ruxsatlarni tekshiradi, service'ni chaqiradi | To'g'ridan-to'g'ri DB bilan ishlamaydi |
| **Service** (`service.py`) | Biznes-logika: ball hisoblash, random savol tanlash, PDF generatsiya | HTTP haqida bilmaydi (request/response obyektlarini ko'rmaydi) |
| **Repository** (`repository.py`) | Faqat SQLAlchemy so'rovlari (CRUD) | Biznes qoidalarni bilmaydi |
| **Database** | PostgreSQL, `database/` dagi schema | — |

**Nega bu muhim**: `service.py` ni o'zgartirmasdan `repository.py` ni almashtirish mumkin (masalan PostgreSQL'dan boshqa DB'ga o'tish), yoki `service.py` dagi logikani Telegram bot yoki CLI skriptdan ham chaqirish mumkin — chunki u HTTP'ga bog'liq emas.

### Har bir modul papkasi bir xil shablonga ega:

```
backend/app/tests/
├── __init__.py
├── router.py        # APIRouter — /api/v1/tests/*
├── controller.py     # TestController — validatsiya, ruxsat, orkestratsiya
├── service.py          # TestService — random savol tanlash, ball hisoblash
├── repository.py        # TestRepository — SQLAlchemy CRUD
├── schemas.py             # Pydantic: TestCreate, TestOut, TestUpdate
└── models.py                # SQLAlchemy: Test ORM modeli
```

Xuddi shu shablon 19 ta modulda takrorlanadi: `auth, users, roles, permissions, subjects, grades, topics, lessons, tests, questions, options, attempts, results, certificates, ai, notifications, payments, analytics, settings, uploads`.

### Umumiy (shared) papkalar

```
backend/app/
├── api/              # Barcha router'larni yig'ib /api/v1 ga ulaydi (main.py shu yerni chaqiradi); api/v1/health.py, api/v1/version.py — infratuzilma endpointlari
├── core/              # config.py, security.py (JWT), logging.py, exceptions.py, schemas.py (javob konverti), audit.py, middleware/ (CORS, rate-limit, security headers)
├── db/                  # database.py (engine), base.py (SQLAlchemy Base), session.py (SessionLocal + get_db()) — Sprint 1'da core/database.py'dan ajratildi, har biri bitta mas'uliyat
├── services/                # Modullar orasida umumiy servislar: email/SMS yuborish, S3 yuklash
├── utils/                     # Sof funksiyalar: sana formatlash, slug yaratish
└── main.py                      # FastAPI() instance, middleware va api/ ni ulash
```

**Qoida**: agar logika ikkitadan ortiq modulga kerak bo'lsa (masalan "email yuborish" — `auth` ham, `notifications` ham ishlatadi), u `app/services/` ga chiqariladi, aks holda modul ichida qoladi.

## `frontend/` — oqim

```
Pages → Components → Services → API → Backend
```

- **`pages/`** — marshrut (route) darajasidagi ekranlar, rol bo'yicha subfolder (`admin/`, `teacher/`, `applicant/`, `student/`).
- **`components/`** — qayta ishlatiladigan UI qismlar, `pages/` dan kelib chaqiriladi.
- **`services/`** — komponentlar to'g'ridan-to'g'ri `fetch` chaqirmaydi, `services/` dagi funksiyalarni chaqiradi.
- **`api/`** — HTTP client konfiguratsiyasi (`axios` instance, token refresh interceptor) — `services/` shu yerdan foydalanadi.
- **`routes/`** — React Router konfiguratsiyasi, rol bo'yicha himoyalangan marshrutlar (`ProtectedRoute`).
- **`store/`** — global holat (auth holati, joriy test urinishi).
- **`hooks/`** — `useAuth`, `useTimer`, `useTestAttempt`.

## `database/`

```
database/
├── schema/         # Boshlang'ich to'liq schema (schema_v1.sql, 52 jadval)
├── migrations/       # Alembic revizyalari — schema o'zgarganda shu yerga versiya qo'shiladi
├── seeds/               # Dev/staging uchun namunaviy ma'lumot skriptlari
└── backups/               # Avtomatik backup fayllari (prod'da alohida saqlanadi, repo'ga commit qilinmaydi)
```

## `uploads/`

Faqat **lokal dev muhiti** uchun (`file_type` bo'yicha bo'lingan). Production'da bu papka ishlatilmaydi — `payment_settings`/`ai_settings` kabi `database/schema` dagi fayl URL'lari S3/MinIO'ga ishora qiladi. `temp/` — yuklash jarayonidagi vaqtinchalik fayllar, cron orqali tozalanadi.

## `docker/`, `nginx/`, `scripts/`

- **`docker/`** — `backend.Dockerfile`, `frontend.Dockerfile` — har bir servis alohida image.
- **`nginx/`** — production'da frontend statik fayllarini va `/api` so'rovlarini backend'ga proksi qiladigan konfiguratsiya.
- **`scripts/`** — `seed_db.sh`, `backup_db.sh`, `deploy.sh` — takrorlanadigan amallar.

## Nega bu tuzilma 5–10 yilga chidaydi

1. **Modul qo'shish oson** — yangi domen (masalan v3.0'dagi "Video kurslar") kerak bo'lsa, xuddi shu 6 faylli shablon bilan yangi papka ochiladi, mavjud kod tegilmaydi.
2. **Jamoa kattalashganda konflikt kamayadi** — har bir dasturchi bitta modul papkasida ishlaydi, Git merge-conflict ehtimoli pasayadi.
3. **Qatlamlar mustaqil test qilinadi** — `service.py` ni HTTP'siz, to'g'ridan-to'g'ri unit-test qilish mumkin.
4. **Hujjatlar ham shu bilan sinxron o'sadi** — `docs/` dagi har bir bo'lim endi papka, ichida bir nechta faylga bo'linishi mumkin (masalan `docs/Security/rbac_matrix.md`, `docs/Security/jwt_policy.md`).
