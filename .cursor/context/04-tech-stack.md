# 04. Tech Stack — BilimUz

Har bir texnologiya bo'yicha qaror va **hozirgi holat** (nazariy reja emas, kod bazasida haqiqatan borligi):

| Texnologiya | Qaror | Holat |
|---|---|---|
| **Python 3.13+** | Backend tili — zamonaviy tip-xavfsizlik (`str \| None` sintaksisi) uchun | ✅ Ishlatilmoqda |
| **FastAPI** | Avtomatik OpenAPI/Swagger, dependency injection tizimi tayyor, async-ready | ✅ Ishlatilmoqda |
| **PostgreSQL** | JSONB, to'liq matnli qidiruv, enum tiplar, katta hajmni qo'llab-quvvatlaydi | ✅ Schema v2.0 tayyor (54 jadval) |
| **SQLAlchemy 2.x** | `Mapped[]` sintaksisi bilan tip-xavfsiz ORM | ✅ Ishlatilmoqda |
| **Redis** | Boshida faqat kelajak uchun rejalashtirilgan edi, lekin **xavfsizlik talabi (rate limiting) tufayli v1.0'dayoq ishga tushirildi** | ✅ Rate limiting uchun ishlatilmoqda (`core/middleware/rate_limit.py`). Keshlash uchun hali yo'q — `docs/Roadmap`da rejalashtirilgan |
| **React 19+ / TypeScript** | Frontend | ⏳ Hali qurilmagan — faqat skelet papkalar |
| **Tailwind CSS + shadcn/ui** | Dizayn tizimi | ⏳ Hali qurilmagan |
| **Docker** | Konteynerizatsiya | ✅ `backend/Dockerfile` va root `docker-compose.yml` yozilgan (Postgres+Redis+Backend) |
| **Nginx** | Reverse proxy, statik fayllar | ⏳ `nginx/` papkasi hali bo'sh — frontend qurilgach kerak bo'ladi |
| **GitHub** | Versiya nazorati, CI/CD (`.github/workflows/`) | ⏳ Workflow fayllari hali yozilmagan |
| **Celery** | Kelajakda — email/SMS navbat (`email_queue`/`sms_queue` jadvallari) uchun background worker | ⏳ Kelajakda (v2.0 atrofida, notifications moduli bilan) |
| **MinIO / S3** | Kelajakda — fayl saqlash (`uploads` moduli hozircha lokal `uploads/` papkaga yo'naltirilgan) | ⏳ Kelajakda |
| **Alembic** | Bazaviy migratsiya vositasi | ✅ Ishga tushirildi (`backend/alembic/`). Boshlang'ich baseline migratsiya (`0001_initial_schema.py`) yozilgan, lekin hali real Postgres'ga qo'llanilmagan (bu muhitda DB yo'q). `--autogenerate` hozircha faqat 4 modul (`auth`,`roles`,`subjects`,`users`) uchun xavfsiz — `backend/alembic/README.md`ga qarang |

## Muhim izoh

Bu jadval **haqiqatni** aks ettiradi, reja emas — "kelajakda" deb belgilangan narsalar hali yozilmagan, "ishlatilmoqda" deb belgilanganlari kod bazasida tekshirilishi mumkin. Yangi texnologiya qo'shilganda (masalan Celery ishga tushganda) shu jadval yangilanadi, aks holda Cursor eskirgan holatga ishonib kod yozadi.
