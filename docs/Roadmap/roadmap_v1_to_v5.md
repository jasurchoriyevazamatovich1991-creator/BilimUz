# BilimUz Roadmap

## v1.0 — MVP (poydevor)
- Login / autentifikatsiya (JWT, RBAC)
- Admin panel (asosiy boshqaruv)
- Fanlar, mavzular, darslar (Education moduli)
- Testlar va savollar (Test System)
- Natijalar (Results)

**Maqsad**: platforma real foydalanuvchilar bilan ishlay oladigan minimal, lekin to'liq ishlaydigan holatga kelishi.

## v2.0 — Aqlli va pullik platforma
- AI moduli (AI Ustoz, Test Generator, Xatolar Tahlili)
- To'lov tizimi (Click, Payme, Uzum Bank)
- Sertifikatlar (PDF + QR tekshiruv)
- Mobil dizayn (responsive, PWA darajasida)

**Maqsad**: platforma daromad keltira boshlaydi va AI orqali farqlanadi.

## v3.0 — Ko'p platformali
- Android ilova
- iOS ilova
- Telegram bot (test topshirish, bildirishnoma)

**Maqsad**: foydalanuvchilar veb-saytga bog'lanib qolmasdan, qulay bo'lgan kanalda foydalansin.

## v4.0 — To'liq ta'lim ekotizimi
- Video kurslar
- Jonli dars (video conference)
- LMS (Learning Management System — kurs dasturi, progress tracking)

**Maqsad**: faqat test emas, to'liq o'qitish platformasiga aylanish.

## v5.0 — Miqyoslash va institutsional
- AI Proktor (imtihon paytida video orqali nazorat)
- Marketplace (o'qituvchilar/markazlar o'z kurslarini sotadi)
- Maktab boshqaruvi (maktablar uchun to'liq boshqaruv tizimi — davomat, jurnal)

**Maqsad**: BilimUz nafaqat individual foydalanuvchilar, balki maktab va o'quv markazlari uchun institutsional yechimga aylanadi.

---

## Generic Exam Engine — Sprint 44-49 (bajarilgan fundament)

Sprint 39-43 real PostgreSQL/test infratuzilmasi va Certificate PDF ishlaridan so'ng, Sprint 44'dan boshlab platforma fizika-maxsus test tizimidan **generic (universal) imtihon dvigateli**ga qarab evolyutsiya qildi — kelajakda IELTS/SAT/GRE kabi standartlashtirilgan imtihonlarni bir xil, qayta ishlatiladigan fundament ustida qo'llab-quvvatlash maqsadida. Bu ish v1.0/v2.0'ning mavjud Test System'ini **almashtirmaydi**, balki uni ixtiyoriy, orqaga moslikni to'liq saqlagan holda kengaytiradi.

**Bajarilgan (audit + fundament)**:
- Sprint 44 — Generic Exam Engine architecture audit (faqat audit)
- Sprint 45 — `Test.max_attempts`, `Answer.text_answer`, `ExamSection`, `ScoringStrategy`
- Sprint 46 — `ExamModule`, `Question.module_id`, `AttemptModuleProgress`
- Sprint 47 — `Test.exam_variant`, `QuestionGroup`, `ResultSection`
- Sprint 48 — `AdaptiveRoutingStrategy` foundation, `routing_group`/`routing_variant`
- Sprint 49 — `PerformanceThresholdRoutingStrategy` (birinchi haqiqiy routing strategiyasi)

**Hali bajarilmagan (kelajakdagi ish, aniq sprint raqamlari hali belgilanmagan)**:
- Modul-darajasidagi ijro workflow'i (submit → lock → keyingi modulga o'tish, server-side enforce qilingan)
- Adaptive routing strategiyasini haqiqiy servis/endpoint bilan bog'lash
- IELTS uchun: matching javob turi, Writing/Speaking javob saqlash, band score konversiyasi
- SAT/GRE uchun: scaled score konversiyasi, haqiqiy adaptive algoritm
- Reusable savol banki (hozircha `Question.test_id` majburiy, bitta testga tegishli)
- Frontend: generic exam UI (section/module navigator, question group ko'rsatish, adaptive transition, numeric input, essay editor)

Bu ish v1.0'ning "Testlar va savollar" va v2.0'ning kelajakdagi kengaytmalari orasida, alohida, mustaqil qatlam sifatida rivojlanmoqda — mavjud fizika testlari, Attestation, National Certificate tizimlariga hech qanday ta'sir qilmasdan.

---

## Versiyalar orasidagi bog'liqlik

```
v1.0 (poydevor)
  → v2.0 AI va to'lov shu poydevor ustiga qo'shiladi
      → v3.0 mobil/bot mavjud API'ni iste'mol qiladi (yangi backend logika kam)
          → v4.0 LMS uchun database/schema'ga yangi modullar qo'shiladi
              → v5.0 institutsional xususiyatlar — eng ko'p yangi jadval va rol talab qiladi
```

Har bir versiya oldingisining ustiga quriladi — shuning uchun `Folder Architecture v1.0` dagi modulli tuzilma muhim: v3.0 uchun Telegram bot qo'shilganda, mavjud `app/tests/service.py` dagi logika o'zgarishsiz qayta ishlatiladi, faqat yangi `app/telegram/` modul qo'shiladi.
