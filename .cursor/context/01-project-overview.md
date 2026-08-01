# 01. Project Overview — BilimUz

## Maqsad

O'zbekistondagi eng yirik ta'lim ekotizimini qurish — sun'iy intellekt yordamida ishlovchi onlayn ta'lim va test platformasi.

## Platforma vazifasi (missiya)

Har bir inson uchun sifatli ta'limni zamonaviy texnologiyalar orqali qulay va ishonchli qilish.

## Vizyon

2030-yilgacha O'zbekistondagi eng yirik ta'lim platformalaridan biriga aylanish.

## Kimlar foydalanadi

| Rol | Tavsif |
|---|---|
| Super Admin | Platforma egasi |
| Admin | Platformani boshqaradi |
| Moderator | Muayyan fanlarni boshqaradi |
| Teacher (O'qituvchi) | Testlar va natijalar bilan ishlaydi |
| Applicant (Abituriyent) | DTM/Blok testlarga tayyorlanadi |
| Student (O'quvchi) | Maktab testlarini ishlaydi |
| Parent (Ota-ona) | Farzand natijalarini kuzatadi — v2.0 |
| Schools / Learning Centers | Muassasa sifatida bog'langan foydalanuvchilar |
| Guest | Ro'yxatdan o'tmagan foydalanuvchi |

Platforma millionlab foydalanuvchini qo'llab-quvvatlashi kerak — bu talab har bir arxitektura qaroriga (UUID, indekslash, modulli monolit, keyingi mikroservislarga o'tish imkoniyati) asos bo'ladi.

## Texnologiyalar

**Backend**: Python 3.13+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Redis, JWT+Refresh Token, Argon2 (parol xeshlash — Sprint 4'da bcrypt'dan almashtirildi, `docs/ADR/ADR-009-Auth-Cutover.md`).
**Frontend**: React 19+, TypeScript, Vite, Tailwind CSS, shadcn/ui, Redux Toolkit, TanStack Query.
**Infratuzilma**: Docker, Nginx, GitHub (+ GitHub Actions CI/CD).

To'liq qarorlar va sabablar: `04-tech-stack.md`.

## Arxitektura

- **Clean/Layered Architecture + DDD-yaqin yondashuv**: `Router → Dependencies → Service → Repository → Database`.
- **Modulli monolit** — kelajakda mikroservislarga bo'linish imkoniyati bilan (har bir modul o'z papkasida, boshqa modul ichiga bevosita kirmaydi).
- **Feature-based backend**: `backend/app/{module}/` — 25 ta modul, har biri bir xil 8 qatlamli shablon bilan (`models, schemas, repository, service, router, dependencies, validators, exceptions, constants, tests/, README.md`).
- To'liq tafsilot: `docs/00_Folder_Architecture.md`, `.cursor/prompts/01-architect.md`.

## Hozirgi holat (2026-yil, loyihaning boshlang'ich bosqichi)

- Database schema v2.0 — 54 jadval, to'liq audit trail, tayyor.
- Backend: `auth`, `users`, `roles`, `permissions`, `subjects` — 5 modul to'liq qurilgan (`backend/app/modules/`). Auth — Argon2 + JWT (`nbf` claim), yagona tizim (Sprint 4 Auth Cutover, `docs/ADR/ADR-009-Auth-Cutover.md`).
- Frontend: hali qurilmagan (skelet papkalar bor).
- Test suite (100+ unit test) yozilgan, lekin haqiqiy Postgres muhitida hali ishga tushirilmagan.
- Umumiy loyiha tayyorligi: ~18-22% (backend 5/25 modul, frontend 0%) — batafsil: `05-system-modules.md`.

## Kelajakdagi reja

Qisqa versiya: `03-roadmap.md`. To'liq versiya (5 bosqich, o'zaro bog'liqlik bilan): `docs/Roadmap/roadmap_v1_to_v5.md`.
