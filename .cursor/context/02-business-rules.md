# 02. Business Rules — BilimUz

## O'qituvchi qoidalari

- Test yaratishi mumkin, lekin nashr qilmagunicha (`status='draft'`) talabalar uni ko'rmaydi.
- Faqat o'zi yaratgan yoki o'ziga biriktirilgan fan(lar) doirasida ishlaydi (Moderator kabi cheklangan emas, lekin `created_by` orqali egalik kuzatiladi).
- Test turlari: Attestatsiya, Milliy Sertifikat, Kasb standarti, Pedagogika, Psixologiya.
- Savol bankiga savol qo'shganda kamida bitta to'g'ri variant belgilashi shart (`single_choice`/`multiple_choice` uchun).

## Abituriyent qoidalari

- Ro'yxatdan o'tgach, telefon orqali tasdiqlanmaguncha (`status='pending_verification'`) test topshira olmaydi.
- Test turlari: DTM, Blok test, Mavzuli test, Yakuniy test.
- Bir test uchun `max_attempts` dan ortiq urinish qila olmaydi (default: 1).
- Test boshlangach (`test_attempts.status='in_progress'`), taymer tugagach avtomatik yakunlanadi (`auto_finished`) — javob berish imkoniyati yopiladi.

## O'quvchi qoidalari

- Maktabga bog'langan bo'lishi mumkin (`profiles.school_id`), lekin bu majburiy emas.
- Test turlari: Chorak, Yarim yillik, Yakuniy, Olimpiada.
- `Mening fanlarim` va `Darslar` — bu rolga xos, chunki asosiy faoliyat test emas, o'qish (Lessons moduli).

## Admin vakolatlari

- Super Admin — barcha huquqlar, tizim sozlamalarini o'zgartira oladi (`settings` moduli).
- Admin — foydalanuvchilar, fanlar, testlar, to'lovlarni boshqaradi, lekin `settings`ga kira olmaydi (kelajakda `permissions` moduli orqali aniq cheklanadi — hozircha rol nomi bo'yicha tekshiriladi, `.cursor/prompts/07-reviewer.md` review'ida "High priority" deb belgilangan gap).
- Moderator — faqat o'ziga biriktirilgan fan(lar) doirasida moderatsiya qiladi.

## To'lov tizimi qoidalari

- Qo'llab-quvvatlanadigan provayderlar: Click, Payme, Uzum Bank, Humo, UzCard (mahalliy birinchi), Stripe (keyinchalik, xalqaro).
- To'lov muvaffaqiyatli bo'lguncha (`payments.status='success'`) obuna (`subscriptions`) faollashtirilmaydi.
- Har bir to'lov `transactions` jadvalida provayderning xom javobi bilan birga saqlanadi — kelishmovchilik holatida tekshirish uchun.
- Pullik test (`tests.is_paid=true`) uchun alohida to'lov, yoki tarif orqali kirish — ikkalasi ham qo'llab-quvvatlanadi.

## Sertifikat qoidalari

- Sertifikat faqat haqiqiy natijaga (`results.id`) bog'langan holda yaratiladi — soxta sertifikat berish arxitektura darajasida mumkin emas (`certificates.result_id` FK, NOT NULL).
- Har bir sertifikat noyob raqamga ega (`certificate_number`, `UNIQUE`) va QR-kod orqali ochiq tekshiriladi (`GET /certificates/verify/{code}` — autentifikatsiyasiz).
- Sertifikat faqat `results.is_passed=true` bo'lgan natijalar uchun beriladi (service-layer qoidasi, hali kod yozilmagan — `certificates` moduli navbatda).

## Test ishlash qoidalari (Test Engine)

- **Taymer** — serverda hisoblanadi, frontend faqat ko'rsatadi (firibgarlik oldini olish).
- **Auto Save** — har bir javob tanlangach darhol saqlanadi (debounce ~500ms frontend'da, backend darhol yozadi).
- **Resume** — foydalanuvchi testni tark etsa, `question_order` snapshot orqali xuddi shu tartibda davom ettira oladi.
- **Random** — `tests.shuffle_questions`/`shuffle_answers` yoqilgan bo'lsa, savollar/variantlar har bir urinish uchun alohida tartibda ko'rsatiladi.
- **Anti-cheat** — tab almashtirish/fokusdan chiqish kabi hodisalar `test_attempts.anti_cheat_flags` (JSONB) da qayd etiladi (hozircha faqat schema darajasida, backend logikasi keyingi bosqich).
- To'g'ri javob (`options.is_correct`) hech qachon `submit`dan oldin API javobida qaytmaydi (`docs/API/api_blueprint.md`da belgilangan qoida).
