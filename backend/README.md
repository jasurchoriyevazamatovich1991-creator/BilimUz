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
python -m pytest app/ scripts/ -q

# Faqat core/ testlari (ENVIRONMENT/secret-safety — Sprint 81; rate-limit
# hujjat muvofiqligi, OpenAPI sxema generatsiyasi, Redis test-izolyatsiya
# validatsiyasi — Sprint 84):
python -m pytest app/core/tests/ -q

# Real PostgreSQL integratsiya testlari — ALOHIDA, TEST_DATABASE_URL va
# ishlab turgan PostgreSQL talab qiladi (DB nomi "_test" bilan tugashi shart,
# conftest.py shuni tekshiradi). TEST_REDIS_URL — ixtiyoriy (Sprint 84):
# berilsa, Redis-bog'liq testlar (masalan rate-limit) shu izolyatsiya
# qilingan DB'ga yo'naltiriladi — DB indeksi 0/1 bo'lishi taqiqlanadi
# (xavfsizlik gate, conftest.py):
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/bilimuz_test \
TEST_REDIS_URL=redis://localhost:6379/15 \
    python -m pytest tests/integration/ -q

# OpenAPI sxema validatsiyasi (Sprint 84) — CI'da ham shu ishga tushadi,
# PostgreSQL/Redis talab qilinmaydi:
python -m pytest app/core/tests/test_openapi_schema_generation.py -q
```

Bu sandbox muhitida (2026-10-13'da) qayta tasdiqlangan, haqiqiy natijalar: `app/ scripts/` birgalikda (yuqoridagi birinchi buyruq) — **659 passed, 1 skipped**. `1 skipped` — `TEST_REDIS_URL` berilmagan holatda qasddan skip qilinadigan bitta Redis-redirect tasdiqlash testi (Sprint 84), xato emas.

`tests/integration/` — PostgreSQL va (rate-limit/Redis-bog'liq testlar uchun) Redis talab qiladi. Sprint 86 — Final Integration Verification sessiyasida (2026-10-13) bu to'plam **birinchi marta real Postgres/Redis'ga qarshi to'liq ishga tushirilgan va tasdiqlangan**: izolyatsiya uchun alohida `bilimuz_test` PostgreSQL bazasi (asosiy `bilimuz` bazasidan butunlay alohida, `backend/.env`'dagi `DATABASE_URL` hech qachon ishlatilmagan) va Redis DB indeksi `15` (hech qachon 0/1 emas, har safar ishga tushirishdan oldin `flushdb`) ishlatilgan. Natijalar: Sprint 86'ga bevosita tegishli uch fayl (`test_sprint86_refresh_cookie_flow.py` 5/5, `test_auth_rbac_integration.py` 5/5, `test_sprint73_rate_limiting_and_hardening.py` 4/4) — **14/14 passed**; to'liq `tests/integration/` to'plami — **326 passed, 0 failed** (78 ogohlantirish, barchasi oldindan mavjud/zararsiz — SQLAlchemy model klasslari nomi `Test*` bilan boshlanganligi haqidagi `PytestCollectionWarning`lar va passlib/anyio/FastAPI eskirish ogohlantirishlari). Hech qanday regressiya yoki yangi nosozlik topilmadi.

## Refresh token — HttpOnly cookie (Sprint 86)

Sprint 85'ning auditida aniqlangan nomuvofiqlik (`docs/API/api_blueprint.md` HttpOnly cookie deb da'vo
qilgan, lekin haqiqiy kod `refresh_token`ni JSON javobida qaytarib, frontend uni `localStorage`da
saqlar edi) shu sprintda yopildi — hujjat emas, implementatsiyaning o'zi tuzatildi:

- `POST /auth/login` va `POST /auth/refresh`ning JSON javobida (`data`) endi faqat `access_token` va
  `token_type` bor (`auth/schemas.py::AccessTokenOut`) — `refresh_token` maydoni butunlay yo'q.
- Refresh token endi faqat ikkita cookie orqali uzatiladi (`app/core/security/cookies.py`):
  - `refresh_token` — **HttpOnly**, `Path={API_V1_PREFIX}/auth`, `Max-Age=REFRESH_TOKEN_EXPIRE_DAYS`
    (kun), `SameSite`=`REFRESH_TOKEN_COOKIE_SAMESITE` sozlamasi (standart `lax`), `Secure`=`True` faqat
    `ENVIRONMENT != development`da (dev'da oddiy HTTP orqali ishlashi uchun).
  - `csrf_token` — HttpOnly **emas** (frontend ataylab o'qiy oladi), `Path=/`, xuddi shu muddat/attributlar.
- `POST /auth/refresh` va `POST /auth/logout` endi **double-submit CSRF tekshiruvi** bilan himoyalangan
  (`app/core/security/csrf.py`): so'rov `X-CSRF-Token` header'ini `csrf_token` cookie qiymati bilan
  aynan bir xil yuborishi shart, aks holda `403 CSRF_VALIDATION_FAILED`. `HttpOnly` CSRF himoyasi
  EMASLIGI ataylab hisobga olingan — brauzer `refresh_token` cookie'ni forged cross-site so'rovga ham
  avtomatik biriktiradi, shuning uchun bu alohida, mustaqil tekshiruv.
- Yangi, ixtiyoriy sozlamalar (`app/core/config.py`, hammasi xavfsiz standart qiymat bilan — hech biri
  majburiy emas): `REFRESH_TOKEN_COOKIE_SAMESITE` (`lax`/`strict`/`none`) va `REFRESH_TOKEN_COOKIE_DOMAIN`
  (standart `None` — host-only cookie). **Muhim**: frontend va backend turli (umumiy registrable domenga
  ega bo'lmagan) hostnamelarda joylashtirilsa, `csrf_token` cookie frontend JavaScript'ga umuman ko'rinmay
  qoladi (cookie'lar hostname bo'yicha ajratiladi) — bu holatda yoki `REFRESH_TOKEN_COOKIE_DOMAIN`ni
  umumiy registrable domenga o'rnating (masalan ikkalasi ham `*.bilimuz.uz` subdomeni bo'lsa), yoki CSRF
  token'ni boshqa yo'l bilan (masalan javob tanasida) yetkazishni ko'rib chiqing — bu sprintning real
  deployment-topologiyaga bog'liq, hal qilinmagan tomoni (bir xostname'li joriy dev topologiyasida
  muammo yo'q, amalda real Postgres/Redis'ga qarshi tasdiqlangan — yuqoridagi "Testlash" bo'limiga qarang).
- Frontend (`frontend/src/store/authStore.ts`, `api/client.ts`, `api/auth.ts`) mos ravishda yangilandi:
  `refreshToken` maydoni state'dan butunlay olib tashlandi (eski `localStorage` yozuvidan ham `migrate()`
  orqali avtomatik tozalanadi), `httpClient` endi `withCredentials: true`, CSRF header
  `frontend/src/utils/csrfCookie.ts` orqali o'qiladi.
- **Moslik buzilishi**: bu JSON javob konraktining buzuvchi o'zgarishi — `refresh_token`ni javob
  tanasidan o'qiydigan har qanday tashqi/eski klient (shu repodagi frontenddan tashqari) endi ishlamaydi;
  shu sprint doirasida frontend ham bir vaqtda yangilandi.
- Testlar: `app/modules/auth/tests/test_sprint86_refresh_cookie_auth.py` (real Postgres/Redis'siz,
  `get_auth_service` dependency-override + monkeypatch'langan Redis orqali, 13/13 passed),
  `app/core/tests/test_sprint86_cookie_config.py` (config/CORS, 11/11 passed),
  `tests/integration/test_sprint86_refresh_cookie_flow.py` (real Postgres bilan to'liq login→refresh→
  logout, rotatsiya, revoke, CSRF-rad etish — Sprint 86 Final Integration Verification sessiyasida
  (2026-10-13) izolyatsiya qilingan `bilimuz_test` bazasiga qarshi ishga tushirilgan va **5/5 passed**).
  Batafsil izolyatsiya metodologiyasi uchun yuqoridagi "Testlash" bo'limiga qarang.

## CI (Sprint 84)

`../.github/workflows/openapi-schema-validation.yml` — `backend/**`ga tegishli push/PR'da yuqoridagi so'nggi buyruqni (`test_openapi_schema_generation.py`) ishga tushiradi. Bu **to'liq CI emas** — faqat OpenAPI sxemasi haqiqatan generatsiya qilinishini va to'g'ri JSON ekanligini tekshiradi; umumiy test to'plami, linting va build/deploy hamon qo'lda bajariladi.

## Xavfsizlik eslatmalari

- `.env` faylini hech qachon commit qilmang (`.gitignore`da istisno qilingan).
- `backend/.env.example` faqat xavfsiz placeholder qiymatlarni o'z ichiga oladi — haqiqiy secretlarni hech qachon bu faylga yoki boshqa versiyalanadigan joyga yozmang.
- Rate limiting (`app/core/middleware/rate_limit.py`) — haqiqiy, tekshirilgan qiymatlar va bilingan cheklov (faqat IP, `ai/*`dan tashqari) uchun [`../docs/API/api_blueprint.md`](../docs/API/api_blueprint.md)ning 8-bo'limiga qarang (Sprint 84'da hujjat koddan qayta tekshirilib tuzatildi).
- Refresh token endi HttpOnly cookie orqali (Sprint 86) — yuqoridagi bo'limga qarang.
- Production/staging'da standart secret qiymatlari bilan ishga tushirish ataylab bloklanadi — yuqoridagi "Sozlash" bo'limiga qarang.
