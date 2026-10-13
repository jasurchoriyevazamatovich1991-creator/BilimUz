# 05. API Blueprint — BilimUz

Frontend va Backend orasidagi shartnoma. Barcha endpointlar shu hujjatga mos yozilishi kerak — frontend backend kodini kutmasdan shu spetsifikatsiya asosida ishlashni boshlashi mumkin (mock data bilan).

## 1. Umumiy qoidalar

- **Base URL**: `https://api.bilimuz.uz/api/v1`
- **Format**: JSON, `Content-Type: application/json`
- **Autentifikatsiya**: `Authorization: Bearer <access_token>` (JWT)
- **Versiyalash**: URL orqali (`/api/v1/...`), kelajakda `/api/v2` qo'shilishi mumkin, eski versiya darhol o'chirilmaydi.

## 2. Javob formati (Response Envelope)

Har bir javob bir xil "konvert" ichida keladi — frontend har doim bir xil strukturani kutadi:

**Muvaffaqiyatli javob:**
```json
{
  "success": true,
  "data": { "...": "..." },
  "meta": { "page": 1, "per_page": 20, "total": 143 }
}
```

**Xato javobi:**
```json
{
  "success": false,
  "error": {
    "code": "TEST_ALREADY_SUBMITTED",
    "message": "Bu urinish allaqachon yakunlangan",
    "details": null
  }
}
```

`meta` faqat ro'yxat (list) endpointlarida bo'ladi. `error.code` — frontend shu kod bo'yicha aniq xabar/harakatni tanlaydi (masalan modal ochish), `message` esa foydalanuvchiga to'g'ridan-to'g'ri ko'rsatiladigan matn.

## 3. HTTP status kodlari

| Kod | Qachon ishlatiladi |
|---|---|
| 200 | Muvaffaqiyatli GET/PUT/PATCH |
| 201 | Muvaffaqiyatli POST (resurs yaratildi) |
| 204 | Muvaffaqiyatli DELETE (body yo'q) |
| 400 | Noto'g'ri so'rov (validatsiya xatosi) |
| 401 | Token yo'q yoki eskirgan |
| 403 | Token bor, lekin ruxsat yo'q (RBAC) |
| 404 | Resurs topilmadi |
| 409 | Konflikt (masalan email allaqachon band) |
| 422 | Semantik validatsiya xatosi (Pydantic) |
| 429 | Rate limit oshib ketdi |
| 500 | Server xatosi |

## 4. Autentifikatsiya oqimi

```
POST /auth/register        → ro'yxatdan o'tish (telefon/email + parol)
POST /auth/verify           → SMS/email kodni tasdiqlash
POST /auth/login             → access_token (15 daq) JSON'da + refresh_token (30 kun) HttpOnly cookie'da
POST /auth/refresh            → yangi access_token (cookie'dagi refresh_token asosida, rotatsiya bilan)
POST /auth/logout              → sessiyani bekor qilish + cookie'larni tozalash
GET  /auth/me                     → joriy foydalanuvchi ma'lumoti
```

**Sprint 86 — refresh token endi HttpOnly cookie orqali**: avvalgi versiyada bu hujjat `refresh_token`
HttpOnly cookie orqali uzatiladi deb da'vo qilgan edi, lekin haqiqiy implementatsiya uni oddiy JSON
maydonida qaytarar va frontend uni `localStorage`da saqlar edi (`frontend/src/store/authStore.ts`,
o'sha paytdagi kod sharhida ataylab qabul qilingan xavf sifatida belgilangan). Sprint 86 shu
nomuvofiqlikni implementatsiyani hujjatga moslashtirish orqali emas, balki haqiqatan ham HttpOnly
cookie oqimini qurish orqali yopdi:

- `POST /auth/login` va `POST /auth/refresh` javob tanasida (`data`) endi **faqat** `access_token` va
  `token_type` bor — `refresh_token` maydoni butunlay olib tashlandi, uni frontend hech qachon o'qiy
  olmaydi.
- Refresh token ikkita `Set-Cookie` orqali yetkaziladi: `refresh_token` (HttpOnly, `Path=/api/v1/auth`,
  `Max-Age`=`REFRESH_TOKEN_EXPIRE_DAYS`, `SameSite` — sozlanadigan, standart `Lax`, `Secure` — faqat
  `ENVIRONMENT != development`da) va `csrf_token` (HttpOnly **emas**, `Path=/`, xuddi shu muddat/SameSite/
  Secure) — ikkinchisi frontend uchun ataylab o'qilishi mumkin qilib qo'yilgan (quyiga qarang).
- `POST /auth/refresh` va `POST /auth/logout` endi **CSRF himoyasi** bilan: so'rov `X-CSRF-Token`
  header'ini `csrf_token` cookie qiymati bilan aynan bir xil holda yuborishi shart (double-submit
  pattern, `backend/app/core/security/csrf.py`) — mos kelmasa yoki yo'q bo'lsa `403`. `HttpOnly` o'zi
  CSRF himoyasi emasligi aniq hisobga olingan — brauzer `refresh_token` cookie'ni forged cross-site
  so'rovga ham avtomatik qo'shib yuboradi, shuning uchun bu ikkinchi, mustaqil tekshiruv kerak.
- Bu — **moslik nuqtai nazaridan buzuvchi o'zgarish**: `refresh_token`ni javob tanasidan o'qiydigan
  har qanday eski/tashqi klient (frontenddan tashqari) endi ishlamaydi. Ushbu repository ichida
  frontend bilan bir vaqtda yangilandi (`frontend/src/api/auth.ts`, `api/client.ts`, `store/authStore.ts`).
- Batafsil: `backend/README.md`ning "Sprint 86" bo'limi va `backend/app/core/security/cookies.py`/`csrf.py`
  modullarining o'z hujjat-izohlari (turli domenlarda joylashtirish uchun `REFRESH_TOKEN_COOKIE_DOMAIN`/
  `SAMESITE` sozlamalari bilan birga).

Frontend `access_token`ni xotirada/`localStorage`da (Zustand `persist`) saqlaydi — bu o'zgarmadi, chunki
u qisqa muddatli (15 daqiqa); faqat `refresh_token` frontend state'idan butunlay olib tashlandi.

**401 kelganda**: `apiClient.ts` avtomatik `/auth/refresh`ni chaqiradi (cookie avtomatik yuboriladi,
`X-CSRF-Token` `csrf_token` cookie'dan o'qib qo'shiladi), muvaffaqiyatli bo'lsa so'rovni qaytadan
yuboradi; muvaffaqiyatsiz bo'lsa foydalanuvchini login sahifasiga yo'naltiradi.

## 5. Modul bo'yicha endpointlar

### Users & Profiles
| Method | Path | Tavsif | Ruxsat |
|---|---|---|---|
| GET | `/users` | Foydalanuvchilar ro'yxati (filter: role, status) | Admin |
| GET | `/users/{id}` | Bitta foydalanuvchi | Admin, Self |
| PATCH | `/users/{id}` | Ma'lumotni yangilash | Admin, Self |
| DELETE | `/users/{id}` | O'chirish/bloklash | Admin |
| GET | `/users/me/profile` | Profil | Self |
| PUT | `/users/me/profile` | Profilni yangilash | Self |

### Education (Subjects → Topics → Lessons)
| Method | Path | Tavsif | Ruxsat |
|---|---|---|---|
| GET | `/subjects` | Fanlar ro'yxati | Public |
| POST | `/subjects` | Fan qo'shish | Admin |
| GET | `/subjects/{id}/topics` | Fan mavzulari | Public |
| POST | `/topics` | Mavzu qo'shish | Admin, Teacher |
| GET | `/topics/{id}/lessons` | Mavzu darslari | Public |
| POST | `/lessons` | Dars qo'shish | Admin, Teacher |

### Test System — yuragi
| Method | Path | Tavsif | Ruxsat |
|---|---|---|---|
| GET | `/tests` | Testlar ro'yxati (filter: subject, category, grade) | Public/Auth |
| POST | `/tests` | Test yaratish | Teacher, Admin |
| GET | `/tests/{id}` | Test tafsilotlari (savolsiz — meta) | Auth |
| POST | `/tests/{id}/questions` | Savol qo'shish | Teacher, Admin |
| POST | `/questions/{id}/options` | Variant qo'shish | Teacher, Admin |
| **POST** | **`/attempts/start`** | **Testni boshlash** — `{test_id}` → yangi `attempt_id`, random savol tartibi bilan | Student, Applicant |
| GET | `/attempts/{id}` | Joriy holatni olish (Resume uchun) | Owner |
| **PATCH** | **`/attempts/{id}/answer`** | **Bitta savolga javob saqlash** (Auto Save) — `{question_id, selected_option}` | Owner |
| POST | `/attempts/{id}/submit` | Testni yakunlash, ball hisoblash | Owner |
| GET | `/attempts/{id}/result` | Natijani olish | Owner |

**Muhim**: `/attempts/{id}` javobida **to'g'ri javob qaysi ekani hech qachon qaytmaydi** — faqat `submit`dan keyin. Bu Test Engine'ning xavfsizlik qoidasi.

### Results & Statistics
| Method | Path | Tavsif |
|---|---|---|
| GET | `/results/me` | Mening barcha natijalarim |
| GET | `/statistics/me` | Shaxsiy statistikam (fan bo'yicha) |
| GET | `/ranking?subject_id=&period=` | Reyting jadvali |
| GET | `/achievements/me` | Mening nishonlarim |

### Certificates
| Method | Path | Tavsif |
|---|---|---|
| POST | `/certificates/generate` | Sertifikat yaratish (natija asosida) |
| GET | `/certificates/{id}` | Sertifikat ma'lumoti + PDF havolasi |
| GET | `/certificates/verify/{code}` | **Public** — sertifikat haqiqiyligini tekshirish |

### AI Center
| Method | Path | Tavsif |
|---|---|---|
| POST | `/ai/chat` | AI bilan suhbat (savol-javob) |
| POST | `/ai/generate-questions` | Mavzu bo'yicha savollar generatsiya qilish (Teacher) |
| POST | `/ai/analyze-errors` | Xatolarni tahlil qilish (attempt_id asosida) |
| POST | `/ai/study-plan` | Shaxsiy o'qish rejasi tuzish |

### Payments
| Method | Path | Tavsif |
|---|---|---|
| GET | `/plans` | Tariflar ro'yxati |
| POST | `/payments/create` | To'lov yaratish (Click/Payme uchun invoice) |
| POST | `/payments/webhook/{provider}` | **Provider → Bizga** — to'lov holatini tasdiqlash (webhook) |
| GET | `/subscriptions/me` | Mening obunam |

### Notifications
| Method | Path | Tavsif |
|---|---|---|
| GET | `/notifications/me` | Bildirishnomalarim |
| PATCH | `/notifications/{id}/read` | O'qilgan deb belgilash |

## 6. Pagination

Barcha ro'yxat endpointlari query parametrlarni qabul qiladi:
```
GET /tests?page=1&per_page=20&sort=-created_at&subject_id=<uuid>
```
Javobdagi `meta` obyekti: `{ "page": 1, "per_page": 20, "total": 143, "total_pages": 8 }`.

## 7. Real-vaqt (WebSocket) — Test Engine uchun

`wss://api.bilimuz.uz/ws/attempts/{attempt_id}` — quyidagilar uchun ishlatiladi:
- Taymer serverda hisoblanadi, frontend faqat ko'rsatadi (vaqtni frontendda hisoblash — firibgarlik xavfi).
- `time_up` hodisasi kelganda frontend avtomatik `submit` chaqiradi (Auto Finish).

## 8. Rate limiting

**Sprint 84 — Package 1 tuzatish**: quyidagi jadval haqiqiy
implementatsiya bilan bevosita tekshirilib, mos keladigan qiymatlarga
yangilandi (manba: `backend/app/modules/auth/constants.py`,
`backend/app/modules/ai/constants.py`,
`backend/app/modules/certificates/router.py`). Oldingi versiyada: (a)
`/auth/register` uchun limit noto'g'ri (5 emas, 3) ko'rsatilgan edi,
(b) `/ai/*` uchun soat/foydalanuvchi birligi noto'g'ri edi (haqiqiyi —
daqiqa/foydalanuvchi), (c) "Qolgan barchasi" uchun 100 so'rov/daqiqa/
foydalanuvchi degan GLOBAL limit hech qachon amalga oshirilmagan —
`rate_limit()` faqat quyida sanab o'tilgan muayyan endpoint'larga
qo'llanadi, boshqa hech bir endpoint'da (hatto oddiy IP asosida ham)
umuman rate limit yo'q, va (d) `Retry-After` header hech qachon
qaytarilmagan (`core/exceptions.py`'ning `app_exception_handler`'i
faqat JSON tanasini qaytaradi, hech qanday maxsus header
qo'shmaydi) — bu bo'lim shu uchta noaniqlikni tuzatadi, implementatsiya
o'zgartirilmagan.

| Endpoint | Limit | Kalit |
|---|---|---|
| `POST /auth/register` | 3 so'rov / daqiqa | IP |
| `POST /auth/login` | 5 so'rov / daqiqa | IP |
| `POST /auth/verify` | 5 so'rov / daqiqa | IP |
| `POST /auth/refresh` | 20 so'rov / daqiqa | IP |
| `POST /auth/change-password` | 5 so'rov / daqiqa | IP |
| `GET /certificates/verify/{code}` | 20 so'rov / daqiqa | IP |
| `POST /ai/chats/{id}/messages` | 10 so'rov / daqiqa | foydalanuvchi (autentifikatsiyalangan) |
| Boshqa barcha endpoint'lar | Hech qanday rate limit yo'q (hozircha) | — |

Limit oshganda faqat `429` status kodi va standart xatolik envelope'i
(`{success: false, message, data: null, errors}`) qaytadi — hech
qanday `Retry-After` yoki boshqa maxsus header qo'shilmaydi.

**Bilinadigan cheklov (yashirilmagan)**: barcha limitlar faqat so'rov
yuboruvchining IP manzili bo'yicha hisoblanadi (bitta `ai/*` endpoint'i
bundan mustasno — u autentifikatsiyalangan foydalanuvchi bo'yicha
hisoblanadi). Hech bir auth endpoint so'rov tanasidagi identifikator
(telefon/email) bo'yicha qo'shimcha cheklov qo'ymaydi — botnet orqali
IP cheklovini aylanib o'tib, bitta qurbon hisobini cheksiz urinish
bilan hujjum qilish nazariy jihatdan hali ham mumkin. Bu — ataylab
qilingan, hujjatlashtirilgan qaror (qarang:
`backend/app/modules/auth/README.md`'ning "Known deviation" va "Future
improvements" bo'limlari), shu sprint doirasida o'zgartirilmagan.

## 9. Frontend integratsiya qoidasi

`frontend/src/services/` dagi har bir fayl shu hujjatdagi bitta modulga mos keladi (`testApi.ts` ↔ Test System bo'limi). Yangi endpoint qo'shilganda — avval shu hujjat yangilanadi, keyin backend va frontend parallel yoziladi.
