# Sprint 20 — Student Test Taking UI

**Status: READY FOR GIT**

## 1. Sprint maqsadi

Student uchun PUBLISHED testni haqiqiy backend endpointlari orqali boshlash, savollarni ko'rish, javob berish, yuborish va natijaga o'tish imkoniyatini frontendda qurish. Bu — loyihaning birinchi genuinely Student-yo'naltirilgan sprinti; Sprint 15–19 barchasi faqat Admin panelida edi.

## 2. Scope

- Test ro'yxati (faqat `published`)
- Test detail
- Boshlash
- Davom ettirish
- Attempt
- Savollarga javob berish
- Next / Previous
- Progress
- Timer
- Submit
- Create Result
- Result page

**Certificates Sprint 20 scope'iga kirmaydi** — auditda tasdiqlangan qaror bo'yicha keyingi sprintga qoldirilgan (§15).

## 3. Backend endpointlar

Barchasi audit bosqichida backend router va schema kodidan bevosita tekshirilgan, taxmin qilinmagan:

| Endpoint | Vazifasi | Tasdiqlangan manba |
|---|---|---|
| `POST /attempts/start` | Yangi urinish boshlash (`{test_id}`) | `attempts/router.py::start_attempt` |
| `GET /attempts/me` | O'z urinishlari ro'yxati (`page, per_page, test_id, status`) | `attempts/router.py::list_my_attempts` |
| `GET /attempts/{id}` | Urinish to'liq holati (savollar + javob berilganlik) | `attempts/router.py::get_attempt` |
| `PATCH /attempts/{id}/answer` | Bitta javobni saqlash (`{question_id, selected_option}`) | `attempts/router.py::save_answer` |
| `POST /attempts/{id}/submit` | Urinishni yakunlash, ephemeral natija qaytaradi | `attempts/router.py::submit_attempt` |
| `POST /results` | Yakunlangan urinishdan doimiy natija yaratish (`{attempt_id}`, idempotent) | `results/router.py::create_result` |
| `GET /results/{id}` | Doimiy natijani ko'rish | `results/router.py::get_result` |

Har birining request body, path/query parametrlari va response sxemasi implementatsiyadan oldin backend kodi bilan birma-bir solishtirilgan (Final Code Review'ning 1-bandi).

## 4. Frontend architecture

**Kengaytirilgan** (mavjud fayllar, `count()`/`myCount()` — Sprint 14 — o'zgarishsiz qoldirilgan):
- `api/attempts.ts` — `listMine, start, get, saveAnswer, submit, getResult`
- `api/results.ts` — `create, get`

**Yangi fayllar**:
- `hooks/useAttempt.ts` — `useActiveAttemptForTest`, `useStartAttempt`, `useAttempt`, `useSaveAnswer`, `useSubmitAndCreateResult`
- `hooks/useResults.ts` — `useResult`, `useCreateResultForFinishedAttempt`
- `components/attempts/Timer.tsx`
- `components/attempts/QuestionNavigator.tsx`
- `pages/student/TestsListPage.tsx`
- `pages/student/TestDetailPage.tsx`
- `pages/student/AttemptPage.tsx`
- `pages/student/ResultPage.tsx`

**Marshrutlash** (`routes/AppRoutes.tsx`ga qo'shildi, Sprint 15–19'dagi `excludePaths` mexanizmi orqali):
```
/student/tests
/student/tests/:testId
/student/tests/:testId/attempt/:attemptId
/student/results/:resultId
```

**Qayta ishlatilgan komponentlar**: `ConfirmDialog`, `ErrorState`, `ErrorBoundary`, toast tizimi, `Button`/`Input`/`Card`, `useDebouncedValue`, `useTest`/`useTestsList` (Sprint 19), `ProtectedRoute`, `StudentLayout`.

## 5. Test flow

```
Tests List (GET /tests?status=published)
  → Test Detail (GET /tests/{id})
  → Active Attempt Check (GET /attempts/me?test_id=X&status=in_progress)
  → Start (POST /attempts/start) YOKI Continue (mavjud attemptga navigatsiya)
  → Attempt (GET /attempts/{id})
  → Answer (PATCH /attempts/{id}/answer, har bir tanlovda)
  → Submit (POST /attempts/{id}/submit)
  → Create Result (POST /results, submit muvaffaqiyatli bo'lgandan keyin avtomatik)
  → Result Page (GET /results/{id})
```

## 6. Timer

- Har bir render/interval tikida `expires_at`dan (backend qaytargan) yangidan hisoblanadi.
- Lokal countdown — **faqat UX vazifasini bajaradi**, yakuniy qaror emas.
- Countdown 0ga yetganda `onExpire` orqali avtomatik submit chaqiriladi.
- **Backend authoritative**: har bir so'rovda (`get_attempt`, `save_answer`, `submit`, `get_result`) backend `expires_at`ni mustaqil tekshiradi va lozim bo'lsa avtomatik yakunlaydi — frontend timeri buni faqat signal qiladi, hech qachon mustaqil hal qilmaydi.
- **`localStorage` hech qayerda ishlatilmaydi** — `Timer.test.tsx`da `Storage.prototype` spy orqali aniq tasdiqlangan.
- Refreshdan keyin: komponent qayta mount bo'ladi, `expires_at` backenddan qayta olinadi, countdown to'g'ri qayta hisoblanadi — alohida saqlash mexanizmi kerak emas.
- **Double-submit himoyasi**: manual Submit va Timer'ning `onExpire`i bitta `fireSubmit()` funksiyasiga yo'naltiriladi, `useRef` (sinxron) + mutatsiya `isPending` (asinxron) ikki qatlamli himoya bilan.
- `useEffect`ning cleanup funksiyasida `clearInterval` — komponent unmount bo'lganda yoki qayta render bo'lganda interval davom etib qolmaydi.

## 7. Active Attempt

`start_attempt` backend darajasida mavjud faol urinishni **tekshirmaydi** (faqat umumiy urinish sonini). Shu sababli frontend "Boshlash" bosilishidan oldin `GET /attempts/me?test_id=X&status=in_progress` orqali faol urinish borligini tekshiradi:
- Faol urinish topilsa → "Davom ettirish", mavjud attemptga to'g'ridan-to'g'ri yo'naltiriladi, `start()` **hech qachon** chaqirilmaydi.
- Topilmasa → "Boshlash" ko'rinadi, bosilganda `start()` chaqiriladi.

Bu mantiq `TestDetailPage.test.tsx`da aniq tasdiqlangan (`start()` chaqirilmagani alohida test qilingan).

## 8. Refresh persistence

`attempt_id` **faqat URL'da** saqlanadi (`/student/tests/:testId/attempt/:attemptId`, `useParams()` orqali o'qiladi). Sahifa yangilanganda:
- `useAttempt(attemptId)` yangidan ishga tushadi, `GET /attempts/{id}`ni chaqiradi.
- Backend savollarni **saqlangan tartibda** va **avvalgi javoblar bilan birga** qaytaradi.
- Hech qanday muhim holat faqat React state yoki `localStorage`ga bog'lanmagan.

## 9. Answer saving

Har bir variant tanlanganda `PATCH /attempts/{id}/answer` haqiqiy chaqiriladi. Muvaffaqiyatli bo'lsa, javob keshi to'liq qayta yuklanmasdan (`setQueryData` orqali) yangilanadi — har bir bosishda keraksiz tarmoq so'rovi bo'lmaydi. Xato bo'lsa — toast orqali xabar beriladi. Tanlangan javob holati **yagona manba** (query keshi)dan olinadi — lokal va backend holati ajralib qolish imkoniyati yo'q.

## 10. Multiple Choice backend limitation

**Backend fakti**: `SaveAnswerRequest.selected_option` — bitta UUID (`uuid.UUID | None`), ro'yxat emas. Bu `multiple_choice` savol turi uchun ham amal qiladi — variantlar yaratilishida bir nechta to'g'ri javob belgilash mumkin bo'lsa-da, **javob saqlash endpointi faqat bitta tanlovni qabul qiladi**.

Shu sababli `AttemptPage.tsx` **barcha savol turlari uchun** (`single_choice`, `multiple_choice`, `true_false`) `type="radio"` ishlatadi — hech qanday checkbox yoki "bir nechta variant tanlang" degan matn yo'q. **Bu frontend cheklovi emas — mavjud backend cheklovi**, kodning o'zida (`AttemptPage.tsx`ning boshidagi izohda) aniq hujjatlashtirilgan.

## 11. Backend gaps

Auditda va implementatsiya jarayonida aniqlangan, frontend hal qila olmaydigan haqiqiy backend kamchiliklar:

1. **`shuffle_answers` — o'lik maydon**: `Test.shuffle_answers` mavjud, lekin `attempts/service.py`da hech qayerda ishlatilmaydi — variantlar doim tabiiy tartibda qaytadi.
2. **Savol-bo'yicha to'g'ri/noto'g'ri "review" endpointi yo'q**: `ResultOut`da faqat umumiy `score/percentage/is_passed` bor, har bir savol bo'yicha tafsilot mavjud emas.
3. **`max_attempts` konfiguratsiyasi yo'q**: `DEFAULT_MAX_ATTEMPTS = 1` qattiq kodlangan; `tests.max_attempts` degan maydon backendda umuman mavjud emas (faqat izohda eslatilgan).
4. **`multiple_choice` uchun bitta `selected_option`**: §10'da batafsil tasvirlangan.

## 12. Security

- **`is_correct` frontendga hech qachon yuborilmaydi** — `QuestionForAttemptOut`/`OptionForAttemptOut` sxemalarida bu maydon ataylab yo'q. Frontend kodida (`api/attempts.ts`) buni tasdiqlovchi aniq izoh bor, va hech qayerda bu maydon ishlatilmaydi (grep orqali tasdiqlangan).
- **Backend authoritative**: vaqt limiti, urinish holati, natija hisob-kitobi — barchasi backendda hal qilinadi, frontend faqat aks ettiradi.
- **Attempt egaligi backend tomonidan himoyalangan**: boshqa foydalanuvchining urinishiga kirishga urinish **404** qaytaradi (403 emas — resurs-enumeratsiya himoyasi), frontendda alohida tekshiruv talab qilinmaydi.

## 13. Testing

Final Code Review bosqichida haqiqatan ishga tushirilgan (`npm run test`, `npm run build`, `python3 -m py_compile`), taxmin qilinmagan:

```
Test Files: 25 passed / 0 failed
Tests: 116 passed / 0 failed
TypeScript/build: PASS
Backend py_compile: PASS
Regression: PASS
```

## 14. Sprint 20 build blocker fixes

Final Review'da aniqlangan 6 ta muammo minimal, maqsadli o'zgartirishlar bilan tuzatildi — **hech biri biznes-mantiqqa ta'sir qilmagan**:

1. **`useDashboardStats.ts`** — ishlatilmagan `attemptsApi`/`aiApi` importlari olib tashlandi (Sprint 14'dan qolgan, grep orqali "hech qayerda chaqirilmaydi" deb tasdiqlangandan keyin).
2. **`QuestionFormPage.tsx`** — `handleSubmit` funksiyasiga explicit `if (!testId) return;` guard qo'shildi (komponent darajasidagi mavjud tekshiruv ichki closure'ga tarqalmagani uchun; blind `!` ishlatilmadi).
3. **`VerifyPage.tsx`** — `handleDigitChange` funksiyasiga xuddi shunday explicit `if (!state) return;` guard qo'shildi.
4. **`Header.test.tsx`** — test o'rami mavjud loyiha naqshiga mos (`TopicsListPage.test.tsx` uslubida) `QueryClientProvider` bilan o'raldi, chunki `useLogout()` `useQueryClient()`ga tayanadi.
5. **`TopicsListPage.test.tsx`** — `getByText("Matematika")` (jadval katagi va filtr dropdown'ida ikki marta uchraydi) `getByRole("cell", {name: "Matematika"})`ga almashtirildi — testning maqsadi o'zgarmadi.
6. **`useAttempt.test.tsx`** — ikkinchi `describe` blokiga `beforeEach(() => vi.clearAllMocks())` qo'shildi, mock chaqiruv tarixi testlar orasida sizib chiqmasligi uchun; production kod (`useAttempt.ts`) tegilmadi.

Uchtasi (2, 4, 5) Sprint 13/14/17'dan qolgan, hech qachon ishga tushirilmagan (sandbox'da `npm install` avval ishlamagani sababli) yashirin nuqsonlar edi — Sprint 20'ning o'zi sabab bo'lgani faqat #6.

## 15. Certificates

**Sprint 20ga kiritilmagan.** Audit bosqichida tasdiqlangan qaror: Attempt+Result oqimi allaqachon yetarlicha murakkab, Certificate yaratish (`POST /certificates`) alohida, ochiq, `is_passed`ga bog'liq chaqiruv — keyingi sprintga qoldirilgan.

## 16. Final status

**READY FOR GIT**
