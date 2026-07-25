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

## Versiyalar orasidagi bog'liqlik

```
v1.0 (poydevor)
  → v2.0 AI va to'lov shu poydevor ustiga qo'shiladi
      → v3.0 mobil/bot mavjud API'ni iste'mol qiladi (yangi backend logika kam)
          → v4.0 LMS uchun database/schema'ga yangi modullar qo'shiladi
              → v5.0 institutsional xususiyatlar — eng ko'p yangi jadval va rol talab qiladi
```

Har bir versiya oldingisining ustiga quriladi — shuning uchun `Folder Architecture v1.0` dagi modulli tuzilma muhim: v3.0 uchun Telegram bot qo'shilganda, mavjud `app/tests/service.py` dagi logika o'zgarishsiz qayta ishlatiladi, faqat yangi `app/telegram/` modul qo'shiladi.
