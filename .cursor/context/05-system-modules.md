# 05. System Modules — BilimUz

Har bir modulning vazifasi va **hozirgi qurilish holati**. To'liq 25-modulli backend xaritasi uchun: `docs/00_Folder_Architecture.md`; database jadvallari uchun: `docs/Database/database_blueprint.md`.

| Modul | Vazifasi | Holat |
|---|---|---|
| **Authentication** | Ro'yxatdan o'tish, login, JWT+refresh, parol siyosati, qurilmalarni boshqarish, audit log | ✅ Qurilgan (`backend/app/auth/`) — xavfsizlik kuchaytirilgan |
| **Users** | Foydalanuvchi profili, `User` ORM modeli (auth shu yerga bog'lanadi) | 🟡 Qisman — faqat `models.py` bor, CRUD API yo'q |
| **Roles** | Rol ta'rifi (Super Admin...Guest), seed qilingan | 🟡 Qisman — faqat `models.py` bor |
| **Permissions** | Rol-permission bog'lanishi (`role_permissions`) — DB'da to'liq, lekin backend kod yo'q | ❌ Faqat schema darajasida — Senior Review'da "High priority" gap sifatida belgilangan |
| **Subjects** | Fanlar (Matematika, Fizika...) — CRUD, filter/sort/search | ✅ Qurilgan va QA review'dan o'tgan (`backend/app/subjects/`) |
| **Lessons** | Mavzu ichidagi darslar (video/pdf/matn) | ❌ Hali qurilmagan |
| **Tests** | Test yaratish, savol biriktirish, Test Engine (taymer, random, auto-save) | ❌ Hali qurilmagan — v1.0 uchun navbatdagi eng muhim modul |
| **Questions** | Savol banki, variantlar, media (rasm/audio/video/formula) | ❌ Hali qurilmagan |
| **Results** | Test natijalari, statistika, reyting | ❌ Hali qurilmagan |
| **AI** | AI Ustoz, Test Generator, Xatolar Tahlili, O'qish Rejasi, Chat — bosqichma-bosqich (`.cursor/context/03-roadmap.md` v2.0) | ❌ v2.0 uchun rejalashtirilgan |
| **Certificates** | PDF sertifikat, QR tekshiruv | ❌ v2.0 uchun rejalashtirilgan |
| **Analytics** | Kunlik/oylik statistika, tizim loglari | ❌ Hali qurilmagan |
| **Payments** | Click/Payme/Uzum/Humo/UzCard integratsiyasi | ❌ v2.0 uchun rejalashtirilgan |
| **Notifications** | Email/SMS/Telegram/Push, navbat (`email_queue`/`sms_queue`) | ❌ Hali qurilmagan — `auth`dagi tasdiqlash kodi hozircha shu modulga bog'liq (`TODO` sifatida belgilangan) |
| **Settings** | Tizim sozlamalari (SMTP, to'lov, AI kalitlari) | ❌ Hali qurilmagan — sirlarni shifrlash mexanizmi ham hali yo'q (Senior Review'da "High priority" xavfsizlik gap'i) |

## Belgilar

- ✅ Qurilgan va tekshirilgan (kamida QA/unit-test darajasida)
- 🟡 Qisman — faqat ma'lumotlar modeli bor, to'liq API yo'q
- ❌ Hali boshlanmagan

Bu jadval har safar yangi modul qurilganda yoki holati o'zgarganda yangilanishi kerak — Cursor shu faylga qarab "bu modul allaqachon bormi" degan savolga javob topadi.
