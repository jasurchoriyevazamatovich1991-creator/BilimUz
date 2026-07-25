# BilimUz Database Blueprint v1.0

`schema_v1.sql` — sizning 12-modulli blueprintingizga aynan mos PostgreSQL schema (**52 jadval**).

## Ishga tushirish

```bash
createdb bilimuz
psql -d bilimuz -f schema_v1.sql
```

## Modul → Jadval xaritasi

| # | Modul | Jadvallar | Soni |
|---|---|---|---|
| 1 | Authentication | roles, permissions, role_permissions, users, sessions, login_history | 6 |
| 2 | User Management | profiles, schools, universities, education_centers | 4 |
| 3 | Education | subjects, grades, topics, lessons | 4 |
| 4 | Test System | tests, questions, options, question_files, test_attempts, answers | 6 |
| 5 | Results | results, statistics, ranking, badges, achievements | 5 |
| 6 | Certificates | certificates, certificate_templates, certificate_verification | 3 |
| 7 | AI | ai_chats, ai_history, ai_recommendations, study_plans | 4 |
| 8 | Payments | plans, subscriptions, payments, transactions | 4 |
| 9 | Notifications | notifications, notification_templates, email_queue, sms_queue | 4 |
| 10 | Files | uploads, images, videos, documents | 4 |
| 11 | Analytics | daily_statistics, monthly_statistics, system_logs, audit_logs | 4 |
| 12 | Settings | general_settings, smtp_settings, payment_settings, ai_settings | 4 |
| | **Jami** | | **52** |

## Sizning blueprintingizdan qo'shilgan texnik detallar

Har bir jadval nomi va ustunlari aynan siz bergan tuzilishga mos; quyidagilarni men texnik zarurat sifatida qo'shdim:

- **Tiplar**: `id` — barcha jadvallarda `UUID` (xavfsizroq, tarmoqlangan tizimlar uchun qulay). `created_at`/`updated_at` — `TIMESTAMPTZ`.
- **Enumlar**: `user_status`, `test_status`, `attempt_status`, `question_type`, `difficulty_level`, `payment_provider`, `payment_status`, `subscription_status`, `queue_status` — noto'g'ri qiymat kiritilishini oldini olish uchun.
- **Foreign Key'lar**: jadval nomlaridan (`user_id`, `subject_id`, `test_id` va h.k.) kelib chiqib bog'landi.
- **`profiles`** jadvaliga `school_id` / `university_id` / `education_center_id` qo'shildi — bu 2-modulning maqsadiga (foydalanuvchini muassasaga bog'lash) xizmat qiladi.
- **Indekslar**: tez-tez qidiriladigan ustunlarga (`user_id`, `status`, `created_at` va h.k.) qo'yildi.
- **`set_updated_at()` trigger** — `users` va `tests` jadvallarida `updated_at` avtomatik yangilanadi.

## Diqqat qilinishi kerak joylar

- `role_permissions` orqali har bir rolga (Super Admin, Admin, Moderator...) aniq huquqlar (`permissions.code`) biriktiriladi — bu RBAC tizimining markazi.
- `test_attempts` → `answers` → `results` zanjiri Test Engine'ning yuragi: urinish boshlanadi, javoblar saqlanadi, keyin natija hisoblanadi.
- `certificates.result_id` orqali sertifikat faqat haqiqiy natijaga bog'lanadi — soxta sertifikat berilishi mumkin emas.
- `payments.subscription_id` — agar to'lov obuna uchun bo'lsa; agar bitta pullik test uchun bo'lsa, kelajakda `test_id` ustuni qo'shish mumkin.

## Keyingi qadam

Endi shu 52 jadval ustiga **FastAPI backend** (SQLAlchemy modellari + JWT autentifikatsiya + har bir modul uchun API endpointlar) yozishni boshlashim mumkin.
