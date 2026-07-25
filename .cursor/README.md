# .cursor/ — BilimUz

Cursor (va istalgan AI yordamchisi) shu papkani o'qib, loyihaning qoidalari, arxitekturasi va joriy holatini tushunadi.

```
.cursor/
├── prompts/     "Qanday fikrlash kerak" — 7 ta rol (Architect...Reviewer)
├── rules/       "Aniq chegaralar" — qisqa, qat'iy qoidalar (10 ta hujjat)
└── context/     "Bugungi haqiqat" — loyiha holati, biznes qoidalar, roadmap
```

## Qaysi papkaga qarash kerak, qachon?

| Savol | Javob shu yerda |
|---|---|
| "Yangi modul qanday tuzilishga ega bo'lishi kerak?" | `prompts/01-architect.md`, `prompts/03-backend.md` |
| "Fayl nomlash qoidasi qanday?" | `rules/02-naming-conventions.md` |
| "Bu modul allaqachon qurilganmi?" | `context/05-system-modules.md` |
| "Parol qanday talablarga javob berishi kerak?" | `prompts/05-security.md`, `rules/05-security-checklist.md` |
| "v2.0'da nima bo'ladi?" | `context/03-roadmap.md` |
| "Merge qilishdan oldin nima tekshiriladi?" | `rules/10-review-checklist.md` |

## Ishlatish tartibi

Yangi modul qurishda: **Architect → Database → Backend → Frontend → Security → QA → Reviewer** ketma-ketligi — bu `prompts/` papkasidagi fayl raqamlanishiga aynan mos.
