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
POST /auth/login             → access_token (15 daq) + refresh_token (30 kun)
POST /auth/refresh            → yangi access_token
POST /auth/logout              → sessiyani bekor qilish
POST /auth/password/forgot      → parolni tiklash kodi yuborish
POST /auth/password/reset        → yangi parol o'rnatish
GET  /auth/me                     → joriy foydalanuvchi ma'lumoti
```

Frontend `access_token`ni xotirada (memory/state) saqlaydi, `refresh_token`ni httpOnly cookie orqali oladi — XSS xavfini kamaytirish uchun localStorage'da JWT saqlanmaydi.

**401 kelganda**: `apiClient.ts` avtomatik `/auth/refresh`ni chaqiradi, muvaffaqiyatli bo'lsa so'rovni qaytadan yuboradi; muvaffaqiyatsiz bo'lsa foydalanuvchini login sahifasiga yo'naltiradi.

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

| Endpoint turi | Limit |
|---|---|
| `/auth/login`, `/auth/register` | 5 so'rov / daqiqa / IP |
| `/ai/*` | 20 so'rov / soat / foydalanuvchi |
| Qolgan barchasi | 100 so'rov / daqiqa / foydalanuvchi |

Limit oshganda `429` + `Retry-After` header qaytadi.

## 9. Frontend integratsiya qoidasi

`frontend/src/services/` dagi har bir fayl shu hujjatdagi bitta modulga mos keladi (`testApi.ts` ↔ Test System bo'limi). Yangi endpoint qo'shilganda — avval shu hujjat yangilanadi, keyin backend va frontend parallel yoziladi.
