# Release Packaging — distributable ZIP

Bu hujjat repository ildizidagi `README.md`ning 12-bo'limini ("Distributable ZIP arxiv tayyorlash") takrorlamaydi — undan farqli o'laroq, nima uchun har bir istisno kerakligini va yaratilgan arxivni qanday tekshirishni tasvirlaydi.

## Nega bu fayl kerak

`BilimUz/` repozitoriysi — development davomida ko'plab vaqtinchalik, mahalliy va maxfiy fayllar bilan to'ladi (`.env`, `node_modules/`, `venv/`, `__pycache__/`, test keshi, local SQLite/Postgres keshlari emas — lekin yuklangan media va local test izolyatsiya sozlamalari bo'lishi mumkin). Distributable ZIP bularning hech birini o'z ichiga olmasligi kerak — aks holda real kalitlar, shaxsiy ma'lumotlar yoki foydasiz hajm tarqatiladi.

## Har bir istisno nima uchun kerak

| Istisno | Sabab |
|---|---|
| `BilimUz/.git/*` | To'liq commit tarixi, hajmi katta, distributable arxivga kerak emas (manba kod snapshot yetarli) |
| `BilimUz/*.zip` | Eski/pre-commit backup arxivlar o'zini-o'zi ichiga olmasligi uchun (bular `.gitignore`da ham `*.zip` bilan istisno qilingan) |
| `BilimUz/backend/.env` | **Haqiqiy** maxfiy qiymatlar (`JWT_SECRET_KEY`, `FILE_ENCRYPTION_KEY`, DB parollari) — hech qachon tarqatilmasligi kerak. `.env.example` (placeholder qiymatlar bilan) saqlanadi. |
| `backend/venv/`, `backend/.venv/` | Mahalliy Python virtual muhit — platforma-bog'liq, `requirements.txt`dan qayta generatsiya qilinadi |
| `**/__pycache__/*`, `*.pyc` | Compile-time bayt-kod keshi, manba kod emas |
| `backend/.pytest_cache/`, `**/.pytest_cache/*` | Test-run keshi, versiyalanmasligi kerak |
| `backend/storage/uploads/*` | Mahalliy fayl-saqlash backend (`STORAGE_BACKEND=local`) orqali yuklangan haqiqiy foydalanuvchi fayllari (agar mavjud bo'lsa) — shaxsiy ma'lumot bo'lishi mumkin. `.gitkeep` saqlanadi, papka strukturasi yo'qolmaydi. |
| `frontend/node_modules/*` | `npm install` orqali qayta generatsiya qilinadigan paket keshi — `package.json`/`package-lock.json` saqlanadi |
| `frontend/dist/*` | Vite production build output — generatsiya qilingan artefakt, manba kod emas (`npm run build` orqali qayta yaratiladi) |
| `database/backups/*` | Haqiqiy ma'lumotlar bazasi backup dump'lari (agar mavjud bo'lsa) — ishlab chiqarish ma'lumotlari bo'lishi mumkin. `.gitkeep` saqlanadi. |
| `*.log` | Runtime log fayllari, manba kod emas |
| `frontend/tsconfig.*.tsbuildinfo` | TypeScript incremental-build keshi, platforma/mashina-bog'liq |
| `*.DS_Store` | macOS Finder meta-fayli |

Arxivga **kiritiladigan** narsalar: to'liq backend (`app/`, `alembic/`, `scripts/`, `conftest.py`, `requirements.txt`, `Dockerfile`, `.env.example`, `README.md`, `tests/`), to'liq frontend manba kodi (`src/`, `public/`, `package.json`, `package-lock.json`, `.env.example`, config fayllari — `node_modules/`/`dist/` dan tashqari), `docs/` (API blueprint, ADR, SRS, sprint tarixi), `database/schema/schema_v2.sql`, `docker-compose.yml`, `nginx/`/`docker/` (hozircha bo'sh, `.gitkeep` bilan), `.github/workflows/`.

## Arxivni yaratish

Root README'ning 12-bo'limidagi buyruqni ishlating (repository ildizining **tashqarisidan**, shunda arxiv o'zini o'z ichiga olmaydi):

```bash
cd /path/to  # BilimUz/ ning ota-katalogi
zip -r BilimUz-release-$(date +%F).zip BilimUz \
  -x "BilimUz/.git/*" -x "BilimUz/*.zip" -x "BilimUz/backend/.env" \
  -x "BilimUz/backend/venv/*" -x "BilimUz/backend/.venv/*" \
  -x "*/__pycache__/*" -x "*/.pytest_cache/*" \
  -x "BilimUz/backend/storage/uploads/*" \
  -x "BilimUz/frontend/node_modules/*" -x "BilimUz/frontend/dist/*" \
  -x "BilimUz/database/backups/*" -x "*.log" -x "*.pyc" \
  -x "BilimUz/frontend/tsconfig.app.tsbuildinfo" -x "BilimUz/frontend/tsconfig.node.tsbuildinfo" \
  -x "*.DS_Store"
```

## Arxivni tekshirish

1. **Manifest va mazmunni ko'rish** (haqiqiy fayllarni ochmasdan):
   ```bash
   unzip -l BilimUz-release-*.zip | less
   ```
   Yuqoridagi "istisno qilinadigan narsalar" ro'yxatidagi hech biri ko'rinmasligi, lekin `requirements.txt`, `package.json`, `alembic/versions/`, `tests/`, `README.md` kabi asosiy fayllar mavjud bo'lishi kerak.

2. **Butunlik (integrity) tekshiruvi** — arxiv buzilmaganligini tasdiqlaydi:
   ```bash
   unzip -t BilimUz-release-*.zip
   ```
   Oxirida `No errors detected in compressed data of ...` chiqishi kerak.

3. **Maxfiy ma'lumot/local-data skaneri** — arxivni vaqtinchalik papkaga ochib, umumiy secret pattern'larga (AWS kaliti, private key bosh qatori, ulkan API token prefikslari va h.k.) va haqiqiy `.env` faylining yo'qligini tekshirish:
   ```bash
   mkdir -p /tmp/_zip_check && cd /tmp/_zip_check
   unzip -q /path/to/BilimUz-release-*.zip
   find . -type f -name ".env"                 # bo'sh chiqish kerak
   grep -rlInE "AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----|sk-[a-zA-Z0-9]{20,}" .
   cd / && rm -rf /tmp/_zip_check
   ```
   Hech qanday haqiqiy secret qiymatini terminalga chop etmang — faqat fayl nomi/satr raqamini qaytaring, agar natija bo'lsa.

4. **`.env.example` qiymatlarini qayta ko'rib chiqish** — har ikki fayl (`backend/.env.example`, `frontend/.env.example`) faqat placeholder (`change-me-...`) yoki xavfsiz local-dev standart qiymatlarni (`localhost`, `development`) o'z ichiga olishi kerak, hech qachon haqiqiy ishlab chiqarish kalitini emas.
