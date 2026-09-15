# Sprint 40 — Real PostgreSQL Integration Test Infrastructure

**Status: ✅ COMPLETE / READY FOR COMMIT**

---

## Maqsad

Backend uchun alohida real PostgreSQL integration-test infrastructure
yaratish va eng muhim critical flow'larni haqiqiy PostgreSQL bilan
avtomatlashtirilgan test qilish — mavjud 483 ta mock-asoslangan
(`MagicMock` repository/storage) testni almashtirmasdan, ularni
to'ldirish.

Sprint 1–39 ishlaydigan kodi, mavjud migratsiyalar, API contract va
frontend — barchasi o'zgarishsiz qoldirilishi shart edi.

---

## Real PostgreSQL Integration Test Infrastructure (`backend/conftest.py`)

Yangi, alohida `backend/conftest.py` fayli yaratildi. Asosiy komponentlar:

### TEST_DATABASE_URL Safety Gate

- Integration testlar uchun **alohida** `TEST_DATABASE_URL` environment
  o'zgaruvchisi ishlatiladi.
- `TEST_DATABASE_URL` **hech qachon** `DATABASE_URL`dan avtomatik
  yasalmaydi — foydalanuvchi aniq belgilashi shart.
- `TEST_DATABASE_URL` mavjud bo'lmasa, integration test fixture'ini
  so'ragan har qanday test **aniq va tushunarli xato** bilan darhol
  to'xtaydi (`pytest.fail`, misol bilan).
- Testlar **hech qachon** `DATABASE_URL`ni fallback sifatida
  ishlatmaydi.

### Test Database Safety

- Test baza nomi **`_test` bilan tugashi shart** — aks holda
  `RuntimeError` bilan darhol rad etiladi (bu tekshiruv `DATABASE_URL`
  o'zgaruvchisi almashtirilishidan **oldin** bajariladi).
- Bu qoida real sinovda ham tasdiqlangan: production-ga o'xshash baza
  nomi (`bilimuz`) berilganda darhol rad etilgan.
- Mavjud test bazasi **hech qachon qayta yaratilmaydi yoki
  o'chirilmaydi** — `CREATE DATABASE` faqat baza haqiqatan mavjud
  bo'lmagan holatda bajariladi (`pg_database`dan tekshirilib).
- Development/production `bilimuz` bazasiga integration test orqali
  yozish imkoni yo'q.

### Migration

- Test bazasi tayyorlanganda, mavjud, **o'zgartirilmagan**
  `0001 → 0011` migratsiya zanjiri dasturiy ravishda (`alembic.command.upgrade`)
  qo'llaniladi.
- `alembic/env.py`ga hech qanday o'zgartirish kiritilmadi — u allaqachon
  `settings.DATABASE_URL`ni o'qiydi, bu esa `conftest.py` tomonidan
  `TEST_DATABASE_URL`ga yo'naltiriladi.

### Transaction Isolation

- Har bir test **real PostgreSQL sessiyasi** bilan ishlaydi, tashqi
  tranzaksiya ichida.
- `join_transaction_mode="create_savepoint"` (SQLAlchemy 2.0.20+)
  ishlatiladi — bu servis darajasidagi `session.commit()`
  chaqiruvlaridan keyin ham tashqi tranzaksiyani buzilmasdan saqlaydi.
- Har bir test tugagach **majburiy rollback** — bir test yozgan
  ma'lumot boshqa testda hech qachon ko'rinmaydi (real sinovda
  tasdiqlangan: rollback isolation ishlab chiqarilgan).
- Schema testlar orasida qayta-qayta yaratilmaydi/o'chirilmaydi.

### FastAPI Dependency Override

- `client` fixture — FastAPI'ning rasmiy `app.dependency_overrides`
  mexanizmi orqali `get_db`ni bitta testning `pg_session`iga
  yo'naltiradi.
- Override har test oxirida **`finally` blokida tozalanadi** — keyingi
  testga hech qachon "sizib chiqmaydi".
- `app/main.py` va `app/db/session.py` — ikkalasi ham **o'zgartirilmagan**.

---

## 17 ta Integration Test — 17/17 PASS

Barcha testlar real PostgreSQL'da, `TEST_DATABASE_URL` orqali ishga
tushirilgan va tasdiqlangan.

### 1. Lesson Ordering — 4 test
Haqiqiy `UNIQUE(topic_id, order_number)` DB-darajasidagi cheklovni
tekshiradi — bu mock testlar bilan tekshirib bo'lmaydigan xatti-harakat.
`order_number` avtomatik tayinlanishi, turli mavzularda mustaqil
raqamlash tasdiqlangan.

### 2. Lesson Progress — 4 test
Progress yozuvi saqlanishi, ikkinchi marta bajarilganda dublikat
yaratilmasligi, haqiqiy `UNIQUE(user_id, lesson_id)` DB cheklovi,
turli talabalar mustaqil progress yaratishi tasdiqlangan.

### 3. Attempt / Result — 4 test
To'liq real oqim: attempt boshlash → savollarga javob berish → submit
→ score hisoblash → result yaratish. Real PostgreSQL yozuvlari orqali
tasdiqlangan (yangi so'rov bilan qayta o'qilib). Mavjud scoring
mantig'i o'zgartirilmadi.

### 4. Auth / RBAC — 5 test
Real FastAPI client orqali: Super Admin login (real JWT
access/refresh token), himoyalangan endpoint'ga muvaffaqiyatli kirish,
autentifikatsiyasiz so'rov rad etilishi, Student roli
Super-Admin-only endpoint'dan rad etilishi (403), noto'g'ri parol rad
etilishi. Mavjud `seed_admin.py` seed mexanizmi qayta ishlatilgan —
parallel auth implementatsiyasi yaratilmagan.

---

## Migration 0011 — `LessonProgress.deleted_at` Tuzatildi

Sprint 40 integration testlari davomida **haqiqiy, oldindan mavjud
production bug** topildi:

- `LessonProgress` modeli (`app/modules/progress/models.py`)
  `TimestampMixin`dan meros oladi, bu esa **uchta** ustunni belgilaydi:
  `created_at`, `updated_at`, **`deleted_at`**.
- Sprint 36'ning `0009_add_lesson_progress.py` migratsiyasi faqat
  `created_at`/`updated_at`ni yaratgan, **`deleted_at`ni unutgan**.
- Bu nomuvofiqlik mavjud mock-asoslangan testlar tomonidan **hech
  qachon aniqlanmagan** edi, chunki `MagicMock` hech qachon haqiqiy SQL
  so'rov yaratmaydi.
- Real PostgreSQL orqali (`SELECT ... FROM lesson_progress`) bu xato
  darhol oshkor bo'ldi: `column lesson_progress.deleted_at does not
  exist`.

**Tuzatish**: yangi, additive migratsiya —
`backend/alembic/versions/0011_add_deleted_at_to_lesson_progress.py`
— faqat `deleted_at` ustunini qo'shadi (`nullable=True`, `server_default`
yo'q — loyihaning o'z `TimestampMixin`/`0001` naqshiga mos). Boshqa
hech qanday ustun, jadval yoki mavjud migratsiya o'zgartirilmadi.

Migratsiya real `TEST_DATABASE_URL`ga qo'llanildi va tasdiqlandi.
Migratsiya zanjiri: `0001 → 0002 → ... → 0010 → 0011`, uzilishsiz.
Alembic head: `0011`.

---

## Test Natijalari

```
Integration suite:     17/17 PASSED
Full backend suite:    483 passed, 7 failed, 3 errors
```

### Baseline Failures — alohida, Sprint 40'ga aloqasi yo'q

Quyidagi 7 failed + 3 errors — **bazaviy, oldindan mavjud** muammolar,
Sprint 40 davomida yangi paydo bo'lmagan va tuzatilmagan:

- `profiles` moduli — 4 ta test (MagicMock fixture muammosi)
- `roles` moduli — 2 ta test (mock setup muammosi)
- `test_submit_computes_score_correctly` — 1 ta test
- `test_add_media_*` — 3 ta xato (`MediaService` konstruktor
  nomuvofiqligi)

Sprint 40'dan **oldin va keyin** aynan bir xil: **regressiya yo'q**.

---

## Production Code

**Production kod o'zgartirilmadi.** Sprint 40 doirasida yaratilgan
yagona ikki turdagi fayl:

1. Test infrastructure (`backend/conftest.py`,
   `backend/tests/integration/*.py`)
2. Bitta additive migratsiya (`0011`) — bu ham mavjud model bilan
   real DB schema o'rtasidagi nomuvofiqlikni tuzatuvchi, approve
   qilingan tuzatish

API contract, mavjud migratsiyalar, mavjud model/servis/repository/
controller kodlari, frontend — hech biri o'zgartirilmadi.

---

## Yaratilgan Fayllar

```
backend/conftest.py
backend/tests/__init__.py
backend/tests/integration/__init__.py
backend/tests/integration/test_lesson_order_integration.py
backend/tests/integration/test_lesson_progress_integration.py
backend/tests/integration/test_attempt_result_integration.py
backend/tests/integration/test_auth_rbac_integration.py
backend/alembic/versions/0011_add_deleted_at_to_lesson_progress.py
```

---

## Sprint 40 Yakuniy Statusi

**READY FOR COMMIT / COMPLETE**

Barcha integration testlar (17/17) real PostgreSQL'da tasdiqlangan,
mavjud backend suite'da hech qanday regressiya yo'q, production kodga
tegilmadi, migratsiya zanjiri to'liq va uzilishsiz (`0001→0011`).
