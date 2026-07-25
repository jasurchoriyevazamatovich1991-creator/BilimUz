# 06. UI/UX Blueprint — BilimUz

Har bir sahifa, uning maqsadi va asosiy elementlari. Bu hujjat `frontend/src/pages/` tuzilmasining asosi.

## 1. Rol bo'yicha navigatsiya xaritasi

```
Mehmon (Guest)
  └─ Public Website → Login/Register

Foydalanuvchi login qilgach → rolga qarab yo'naltiriladi:
  ├─ Super Admin / Admin  → Admin Panel
  ├─ Moderator             → Admin Panel (cheklangan: faqat o'z fanlari)
  ├─ Teacher                → Teacher Panel
  ├─ Applicant / Student     → Student Panel
  └─ Parent                   → Parent Panel (v2)
```

## 2. Public Website

| Sahifa | Maqsad | Asosiy elementlar |
|---|---|---|
| Bosh sahifa | Birinchi taassurot, CTA | Hero + "Ro'yxatdan o'tish" tugmasi, mashhur fanlar, statistika (N ta test, N ta foydalanuvchi) |
| Platforma haqida | Ishonch hosil qilish | Missiya/vizyon, jamoa |
| Tariflar | Konversiya | 3 ustunli narx kartochkalari (Bepul / Standart / Premium), har birida feature ro'yxati |
| Bog'lanish | Support | Forma (ism, email, xabar) + Telegram/telefon |
| Savol-javob | Ishonch + SEO | Akkordeon (FAQ) |
| Sertifikat tekshirish | Ochiq tekshiruv | Bitta input (sertifikat kodi) → natija kartochkasi |

## 3. Authentication oqimi

```
Login → [telefon/email + parol]
   ↓ (agar tasdiqlanmagan)
Verify → [SMS/Email kod, 6 ta katak, avtomatik fokus]
   ↓
Rolga mos Dashboard
```

- **Login sahifasi**: bitta forma, pastida "Google bilan kirish" va "Telegram bilan kirish" tugmalari, "Parolni unutdingizmi?" havolasi.
- Xato holatida forma ustida qizil banner (`toast` emas — forma bilan bog'liq xato doim forma yonida ko'rinishi kerak).

## 4. Student / Applicant Panel — platformaning yuragi

### 4.1 Dashboard
- Karta qatorlari: "Faol testlar", "So'nggi natijalar", "Tavsiya etilgan mavzular" (AI).
- Yon panel: fanlar ro'yxati (icon + progress bar).

### 4.2 Test ro'yxati sahifasi
- Filtr paneli (chap tomonda desktopda, yuqorida mobilda): Fan, Turi (DTM/Blok/Mavzuli), Qiyinlik.
- Har bir test kartasi: nomi, savollar soni, davomiyligi, "Boshlash" tugmasi.

### 4.3 Test topshirish ekrani — eng muhim ekran

```
┌─────────────────────────────────────────────┐
│  [Fan nomi]              ⏱ 14:32   [Chiqish] │  ← Header: taymer doim ko'rinadi
├───────────────┬─────────────────────────────┤
│               │  Savol 7 / 30                │
│  1  2  3  4   │                               │
│  5  6 [7] 8   │  Savol matni...               │
│  9  10 11 12  │                               │
│  ...          │  ○ Variant A                  │
│               │  ● Variant B (tanlangan)      │
│  ▢ belgilangan│  ○ Variant C                  │
│  ▪ javob berilgan                             │
│  ▫ bo'sh      │  [Belgilash 🏳]                │
│               │                               │
│               │  [← Oldingi]      [Keyingi →] │
└───────────────┴─────────────────────────────┘
```

- **Chap panel** (savollar navigatori): raqamlar rangi bilan holat ko'rsatiladi — javob berilgan (to'liq), belgilangan (bayroqcha), bo'sh (kontur). Istalgan raqamga bosib o'sha savolga o'tish mumkin.
- **Taymer** — doim ko'rinadi, 5 daqiqa qolganda rangi qizarib ogohlantiradi.
- **Auto Save** — variant tanlanishi bilan darhol (debounce 500ms) serverga yuboriladi, foydalanuvchi buni bilmaydi (fon jarayoni).
- **Chiqish** tugmasi — "Testni to'xtatasizmi? Javoblaringiz saqlanadi, keyinroq davom ettirishingiz mumkin" tasdiqlash oynasi bilan (Resume imkoniyati).
- Oxirgi savoldan keyin "Keyingi" o'rniga **"Yakunlash"** tugmasi — bosilganda "N ta savol javobsiz qoldi, baribir yakunlaysizmi?" ogohlantirishi (agar bor bo'lsa).

### 4.4 Natija sahifasi
- Katta doira grafik: ball / foizi (masalan 78%).
- Pastda: fan bo'yicha taqsimot (qaysi mavzuda ko'p xato bo'lgan — AI tahlili).
- Tugmalar: "Sertifikatni ko'rish" (agar o'tgan bo'lsa), "Xatolarni ko'rish" (savol-javob ro'yxati, izohlar bilan), "Qayta urinish".

### 4.5 Sertifikat sahifasi
- A4 nisbatidagi vizual preview + QR kod.
- "Yuklab olish (PDF)" va "Ulashish" tugmalari.

## 5. Teacher Panel

| Sahifa | Maqsad |
|---|---|
| Dashboard | O'z testlari statistikasi, oxirgi natijalar |
| Test yaratish (wizard) | 3 qadam: 1) Meta (nomi, fan, davomiyligi) → 2) Savollar qo'shish → 3) Ko'rib chiqish va nashr qilish |
| Savol banki | Barcha savollarni filtrlash (fan/mavzu/qiyinlik), qidiruv, "Testga qo'shish" |
| Natijalar jurnali | Jadval: talaba, ball, sana; Excel eksport |

**Savol qo'shish formasi** — eng ko'p ishlatiladigan element:
- Savol matni (rich text + LaTeX tugmasi `∑`)
- Rasm/audio/video yuklash (drag-and-drop)
- Variantlar (dinamik ro'yxat, + tugma bilan qo'shiladi, checkbox — to'g'ri javob)
- Qiyinlik va ball inputlari yon-yonda

## 6. Admin Panel

Chap tomonda doimiy sidebar (12 modulga mos bo'limlar), yuqorida qidiruv + profil menyu.

| Bo'lim | Asosiy ko'rinish |
|---|---|
| Dashboard | KPI kartalar (jami foydalanuvchi, faol testlar, kunlik daromad) + grafik |
| Users | Jadval + filter (rol, status) + "Bloklash/Faollashtirish" tez amallar |
| Subjects/Topics | Ierarxik daraxt ko'rinishi (drag-and-drop tartiblash) |
| Tests | Jadval, status badge (draft/published/archived) |
| Payments | Tranzaksiyalar jadvali + status filtri |
| Settings | Tablar: General / SMTP / Payment / AI |

## 7. Umumiy komponentlar kutubxonasi

`frontend/src/components/ui/` — barcha sahifalarda qayta ishlatiladi:

- `Button` (primary/secondary/danger/ghost)
- `Card`
- `Modal` / `ConfirmDialog`
- `Table` (sort, filter, pagination bilan)
- `Timer` (test-engine uchun maxsus)
- `QuestionNavigator` (test-engine uchun maxsus)
- `Toast` (muvaffaqiyat/xato bildirishnomalari)
- `Badge` (status ko'rsatish uchun)
- `ProgressBar`

## 8. Dizayn tokenlari

- **Ranglar**: asosiy — ko'k (`#0C447C` atrofida), muvaffaqiyat — yashil, ogohlantirish — amber, xato — qizil (Tailwind default palette + shadcn).
- **Shrift**: sarlavhalar uchun keng, o'qilishi oson shrift; test matnlari uchun katta o'lcham (savol matni kamida 16px, ko'zni charchatmaslik uchun).
- **Responsivlik**: Test topshirish ekrani mobilda — savol navigatori pastki "sheet" (slide-up panel) sifatida.

## 9. Keyingi qadam

Shu blueprint asosida frontendni qurishni boshlaganda, har bir sahifa uchun avval interaktiv mockup (Figma yoki to'g'ridan-to'g'ri React komponent) tayyorlanishi tavsiya etiladi — ayniqsa **Test topshirish ekrani**, chunki bu platformaning eng murakkab va eng muhim UI qismi.
