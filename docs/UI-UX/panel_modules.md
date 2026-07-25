# Panel Modullari — BilimUz

Har bir rol uchun sidebar/navigatsiya tarkibi. `frontend/src/pages/{role}/` papkalari shu ro'yxatga mos quriladi.

## Admin panel
```
Dashboard
Users
Roles
Permissions
Subjects
Grades
Topics
Lessons
Tests
Questions
Results
Certificates
Analytics
Payments
Notifications
AI
Settings
```
Har biri `backend/app/{module}/` dagi mos modulning to'liq CRUD boshqaruvi bilan bog'lanadi.

## O'qituvchi paneli
```
Dashboard
Attestatsiya
Milliy Sertifikat
Testlar
Natijalar
Statistika
Profil
```
`Attestatsiya` va `Milliy Sertifikat` — `test_category` enumidagi maxsus turlar uchun alohida bo'lim, chunki o'qituvchi ko'proq shu ikki test turi bilan ishlaydi.

## Abituriyent paneli
```
Dashboard
DTM
Blok Test
Mavzular
Natijalar
Reyting
AI Ustoz
Profil
```

## O'quvchi paneli
```
Dashboard
Mening fanlarim
Darslar
Testlar
Natijalar
Yutuqlar
Profil
```
`Mening fanlarim` va `Darslar` — bu panelga xos, chunki o'quvchi (maktab o'quvchisi) uchun asosiy faoliyat testdan oldin **o'qish** (Education moduli — lessons) bo'ladi.

## AI moduli — bosqichma-bosqich kengaytirish

AI Center v2.0 da quyidagi tartibda qo'shiladi (`docs/Roadmap/roadmap_v1_to_v5.md` bilan sinxron):

1. **AI Ustoz** — mavzuni tushuntirish (savol-javob chat)
2. **AI Test Generator** — o'qituvchi uchun mavzu bo'yicha savollar generatsiyasi
3. **AI Xatolar Tahlili** — attempt natijasi asosida qaysi mavzularda ko'p xato borligini aniqlash
4. **AI O'qish Rejasi** — shaxsiy study plan tuzish
5. **AI Chat** — umumiy erkin suhbat

Bu tartib tasodifiy emas: **AI Ustoz** va **AI Xatolar Tahlili** eng ko'p foydalanuvchi qiymatini beradi (retention'ga bevosita ta'sir qiladi), shuning uchun birinchi navbatda ishlab chiqiladi; **AI Chat** eng umumiy va oxirgi navbatda, chunki aniq foydalanish holati (use case) kamroq.
