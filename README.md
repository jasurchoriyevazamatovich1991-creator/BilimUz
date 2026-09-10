# BilimUz

Sun'iy intellekt yordamida ishlovchi onlayn ta'lim va test platformasi — o'qituvchilar, abituriyentlar, o'quvchilar uchun.

## Arxitektura
- **Backend**: FastAPI, feature-based modullar (`backend/app/modules/`) + Layered Architecture (Router → Service → Repository → Database), Clean Architecture tamoyillari bilan
- **Frontend**: React + TypeScript (Pages → Components → Services → API → Backend) — hali qurilmagan
- **Database**: PostgreSQL, 54 jadval, 25 modul, Alembic migratsiyalari bilan boshqariladi
- **Xavfsizlik**: Argon2 (parol xeshlash), JWT (`nbf` claim bilan) — `backend/app/core/security/`da markazlashgan yagona amalga oshirish (Sprint 4 Auth Cutover)

Batafsil: [`docs/00_Folder_Architecture.md`](docs/00_Folder_Architecture.md)

## Hujjatlar
| Bo'lim | Papka |
|---|---|
| Talablar (SRS) | `docs/SRS/` |
| Database | `docs/Database/` |
| API | `docs/API/` |
| UI/UX | `docs/UI-UX/` |
| Xavfsizlik | `docs/Security/` |
| Deploy | `docs/Deployment/` |
| Roadmap | `docs/Roadmap/` |
| Arxitektura qarorlari (ADR) | `docs/ADR/` |
| Jamoa qoidalari | [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) |
| O'zgarishlar tarixi | [`docs/CHANGELOG.md`](docs/CHANGELOG.md) |

`.cursor/` papkasi — AI yordamchilar (Cursor va h.k.) uchun rollar, qoidalar va joriy loyiha konteksti (`.cursor/prompts/`, `.cursor/rules/`, `.cursor/context/`).

## Holat

Kod yozish boshlangan va faol davom etmoqda.

| Bosqich | Qamrov | Holat |
|---|---|---|
| Sprint 1 — Foundation | FastAPI skeleti, `core/`, `db/`, Docker, Alembic, health/version endpointlar | ✅ Yakunlandi |
| Sprint 2 — Enterprise modul arxitekturasi | `auth`, `users`, `roles`, `permissions`, `subjects` — barchasi `backend/app/modules/` ostida | ✅ Yakunlandi |
| Sprint 3 — Argon2/JWT (izolyatsiyalangan sinov) | `PasswordService`, `JWTService`, Register/Login/Refresh/Me — alohida `-v2` yo'llarda qurildi va sinaldi | ✅ Yakunlandi, keyin birlashtirildi ↓ |
| Sprint 4 — Auth Cutover | Sprint 3'dagi Argon2/JWT `core/security/`ga ko'chirildi, `auth` moduli shu asosda qayta yozildi, `-v2` papkalar o'chirildi. **Endi faqat bitta auth tizimi bor.** | ✅ Yakunlandi |
| Sprint 5 — Education Core | `grades`, `topics`, `lessons` — to'liq CRUD, cross-module bog'lanish tekshiruvi (`topics→subjects/grades`, `lessons→topics`), 23 test | ✅ Yakunlandi |
| Sprint 6 — Test Engine | `tests`, `questions` (+options+media), `attempts` — to'liq test topshirish dvigateli: timer, randomizatsiya, scoring, lazy auto-finish, 47 test. Migratsiya `0002` | ✅ Yakunlandi |
| Sprint 7 — Results, Certificates, Analytics | `results` (reyting hisoblash dvigateli, leaderboard endpoint keyingi sprintga qoldirilgan), `certificates` (PDF'siz, idempotent), `analytics` (mustaqil, faqat `results`ni o'qiydi), 36 test | ✅ Yakunlandi |
| Sprint 8 — Notifications, Settings, Uploads | `settings` (Fernet shifrlash, maxfiy maydonlar strukturaviy yashirin), `uploads` (mahalliy disk, UUID nomlash), `notifications` (navbat/trigger dvigateli, haqiqiy SMTP/SMS yo'q — ataylab), 66 test | ✅ Yakunlandi |
| Sprint 9 — AI, Payments | `ai` (vendor-agnostik, real AI yo'q — faqat interfeys, 10/daqiqa rate-limit), `payments` (vendor-agnostik, 2 qatlamli idempotentlik: servis+DB, to'liq refund), migratsiya `0003`, 49 test | ✅ Yakunlandi |
| Sprint 10 — Schools, Learning Centers | Mustaqil kataloglar (`profiles` hali qurilmagani uchun iste'molchisiz, ochiq belgilangan), keng telefon validatsiyasi, 19 test | ✅ Yakunlandi |
| Sprint 11 — Profiles | `User`ning 1:1 kengaytmasi — dublikatsiz (`ProfileOut` User+Profile'ni birlashtiradi), migratsiyasiz, mavjud rollar bilan, 16 test | ✅ Yakunlandi |
| Sprint 12 — Audit Logs, System Logs | `audit_logs` (faqat o'qish, mavjud `AuditLog`ni qayta ishlatadi — dublikat model yo'q), `system_logs` (yangi, yozish+o'qish, `core/logging.py`ga hali ulanmagan — ochiq belgilangan), 28 test | ✅ Yakunlandi |
| Sprint 13 — Frontend Foundation | Birinchi frontend sprinti: auth oqimi (Login/Register/Verify), token-refresh, RBAC routing (8 haqiqiy rol), sidebar/layout skeleti, 20 test. Backendga 1 ta kichik, tasdiqlangan o'zgarish (`UserPublic.role`) | ✅ Yakunlandi |
| Sprint 14 — Header, ErrorBoundary, Dashboard | Header dropdown (Profil/Sozlamalar/Chiqish), global ErrorBoundary, dashboard rol bo'yicha to'liq vidjet ro'yxati bilan haqiqiy backend ma'lumotlariga ulandi (2 ta real API bo'shlig'i topilib, soxta ma'lumotsiz halol hal qilindi), 16 yangi test (jami 33) | ✅ Yakunlandi |
| Sprint 15 — Users Management UI | Haqiqiy topilma: backendda `POST /users`/`DELETE /users` umuman yo'q — faqat List/View/Edit/Search/Filter/Pagination qurildi, Create/Delete UI ataylab qo'shilmadi. 14 yangi test (jami 47) | ✅ Yakunlandi |
| Sprint 16 — Schools & Learning Centers UI | Farqli topilma: bu ikkalasida to'liq CRUD bor — Create/Edit/Delete qurildi. Yangi qayta ishlatiladigan `ConfirmDialog`, Moderator uchun yozish tugmalari yashirilgan (lekin o'qish ochiq qoldirilgan — jarayonda tuzatilgan), 13 yangi test (jami 60) | ✅ Yakunlandi |
| Sprint 17 — Subjects, Grades & Topics UI | Muhim topilma: Topics'ning yozish huquqi kengroq (Teacher ham kiradi), Subjects/Grades'da esa yo'q. Grades'da nom o'zgarmaydi (oddiy matn). Topics — birinchi modullararo CRUD sahifasi (Subjects/Grades'dan faqat o'qish). 9 yangi test (jami 69) | ✅ Yakunlandi |
| Sprint 18 — Lessons UI | Muhim topilma: backend "video/pdf/matndan kamida bittasi" qoidasini talab qiladi — frontend submit-vaqtida tekshiradi, tugma bloklanmaydi. RBAC Topics bilan bir xil (Teacher yozadi). `type="url"`, yangi `ContentBadges` komponenti. 11 yangi test (jami 80) | ✅ Yakunlandi |
| Sprint 19 — Tests & Questions UI | Ikki taxmin tuzatildi: Test↔Lesson yo'q (faqat Subject/Grade/Topic), Archive tugmasi yo'q (faqat Publish). Questions Test ichida joylashgan. Options — lokal holatda yig'iladi, faqat Saqlashda yuboriladi. Shartli validatsiya (single/multiple choice). 15 yangi test (jami 95) | ✅ Yakunlandi |
| Sprint 20 — Student Test Taking / Attempt UI | Birinchi Student-yo'naltirilgan sprint. Haqiqiy backend kamchiligi topildi: `selected_option` — bitta UUID, ro'yxat emas (multiple_choice uchun ham). Timer — faqat vizual, localStorage ishlatmaydi. Submit→CreateResult zanjiri, faol urinishni aniqlash, refresh-xavfsizligi. 15 yangi test (jami 110) | ✅ Yakunlandi |
| Sprint 21 — Certificates UI | Student Certificates UI, Certificate detail, public certificate verification. Backend `verification_code` qo'shildi, Certificate API bilan real integratsiya. PDF hali mavjud emas. 133 frontend test, Certificate backend testlari 18/18 | ✅ Yakunlandi |
| Sprint 22 — Roles & Permissions UI | Roles CRUD UI, Permissions CRUD UI, role-permission assign/revoke. RBAC: o'qish Admin+Super Admin, yozish faqat Super Admin. Tizim rollari himoyalangan. 170 frontend test | ✅ Yakunlandi |
| Sprint 23 — Notifications UI | Student notifications ro'yxati, pagination, Read/Read All, notification bell — real backend endpointlar bilan. 186 frontend test | ✅ Yakunlandi |
| Sprint 24 — UI/UX & Design System | Indigo + Violet + Cyan dizayn tizimi, Light+Dark tema asosi, shadcn/Tailwind token yangilanishi, qayta ishlatiladigan status/error/toast komponentlari, responsive/accessibility yaxshilanishlari. 194 frontend test | ✅ Yakunlandi |
| Sprint 25 — Full System Audit | Faqat audit — kod funksiyalari o'zgartirilmadi. Student/Teacher/Admin journey, backend, frontend, DB, xavfsizlik, R2, testlar, performance va production readiness tekshirildi. Umumiy audit balli: 68/100, kritik/yuqori darajali bo'shliqlar aniqlandi | ✅ Yakunlandi (audit) |
| Sprint 26 — Teacher Panel | Teacher dashboard, Teacher Subjects/Grades (faqat o'qish), Teacher Topics/Lessons/Tests/Questions (to'liq yozish UI) — Admin sahifalarining qayta ishlatiladigan komponentlari `basePath` orqali Teacher panelida ishlatilgan. 203 frontend test, build/TypeScript PASS | ✅ Yakunlandi |
| Sprint 27 — Cloudflare R2 Media Storage | Private R2 arxitekturasi, presigned upload, xavfsiz signed view URL, fayl metadata PostgreSQL'da, Admin file manager asosi, Lesson↔media integratsiyasi, Teacher/Admin/Super Admin upload RBAC, 2GB videogacha multipart upload, browser→R2 to'g'ridan-to'g'ri yuklash, haqiqiy progress, retry/cancel. 71 backend upload testi, 252 frontend testi, build/TypeScript PASS | ✅ Yakunlandi |
| Sprint 28 — Full System Audit | Faqat audit. Backend: 384 passed, 6 eski (oldindan mavjud) xato, 3 modul collection muammosi. Frontend: 252/252 PASS, TypeScript/build PASS. Umumiy ball: 68/100. Kritik topilma **G-01**: eski `POST /uploads` orqali katta videoning RAM'ga to'liq o'qilish xavfi. Shuningdek qayd etilgan: **G-03** — `multiple_choice` bir nechta javobni qo'llamaydi; Progress tizimi yo'q; Results history yo'q; real PostgreSQL/R2 E2E test muhiti yo'q; README eskirganligi | ✅ Yakunlandi (audit) |
| Sprint 29 — Legacy Upload Security Fix | Sprint 28'da aniqlangan **G-01** tuzatildi: eski `POST /uploads` uchun video limiti 20 MB qilib belgilandi, haqiqiy stream hajmi bounded/chunked read orqali tekshiriladi (mijoz e'lon qilgan hajmga ko'r-ko'rona ishonilmaydi). R2/presigned/multipart videoning 2 GB limiti **o'zgarishsiz** qoldi. 9 yangi test, `uploads` moduli 80/80 PASS, to'liq backend 393 passed (6 eski xato/3 collection muammosi o'zgarishsiz), frontend 252/252 PASS, TypeScript/build/`py_compile` PASS. Migratsiya talab qilinmadi | ✅ Yakunlandi |

To'liq qaror tarixi: [`docs/ADR/ADR-009-Auth-Cutover.md`](docs/ADR/ADR-009-Auth-Cutover.md).

**Ochiq eslatma (Sprint 28/29 auditlarida tasdiqlangan, hali bajarilmagan ishlar)**:

- Test to'plami (390+ unit test) hali **haqiqiy PostgreSQL muhitida ishga tushirilmagan** — barcha backend testlar `repository`/`storage` qatlamlarini mock qiladi.
- Real Cloudflare R2 bilan **end-to-end sinov o'tkazilmagan** (bu muhitda real hisob ma'lumotlari yo'q).
- `multiple_choice` savol turi — backend `SaveAnswerRequest.selected_option` hali ham bitta UUID, bir nechta javobni qo'llamaydi (Sprint 19'dan beri).
- **Student Progress** tizimi — umuman mavjud emas (model, endpoint, UI — yo'q).
- **Results History** (natijalar tarixi ro'yxati) — Student uchun sahifa yo'q, faqat bitta natija ko'rish mavjud.
- **Student Video Player** — mavjud emas, `Lesson.video` faqat xavfsiz tashqi havola sifatida ko'rsatiladi.
- **Teacher Media/File UI** — `FileUploader` komponenti tayyor, lekin Teacher paneliga ulanmagan.
- **Certificate PDF** — hech qachon generatsiya qilinmaydi (`pdf_url` doim `null`).
- **Rate limiting** — faqat `auth` endpointlarida, boshqa modullarda kengaytirilmagan.
- **Performance/code splitting** — frontend bitta ~540KB chunk, `React.lazy` qo'llanilmagan.
- **`Lesson.order_number`** — jadvalda yo'q, darslar tartiblanmaydi.
- **`Test.max_attempts`** — konfiguratsiya qilinmaydi, backend konstantasi orqali qattiq `1`ga belgilangan.

Reja: [`docs/Roadmap/roadmap_v1_to_v5.md`](docs/Roadmap/roadmap_v1_to_v5.md)
