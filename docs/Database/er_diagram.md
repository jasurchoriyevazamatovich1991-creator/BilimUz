# 04. ER Diagram — BilimUz

Asosiy oqim bo'yicha (Auth → Test Engine → Results → Certificates, Education ierarxiyasi, AI/Payments/Notifications) qisqartirilgan Entity-Relationship diagrammasi. To'liq 52 jadval uchun `database/schema_v1.sql` manbadir — bu yerda faqat asosiy bog'lanishlar ko'rsatilgan.

GitHub avtomatik mermaid'ni render qiladi — quyidagi blok GitHub'da to'g'ridan-to'g'ri diagramma sifatida ko'rinadi.

```mermaid
erDiagram
  ROLES ||--o{ USERS : has
  USERS ||--o{ SESSIONS : has
  USERS ||--o{ LOGIN_HISTORY : has
  USERS ||--|| PROFILES : has
  USERS ||--o{ TEST_ATTEMPTS : takes
  TESTS ||--o{ TEST_ATTEMPTS : attempted_in
  TEST_ATTEMPTS ||--o{ ANSWERS : contains
  TEST_ATTEMPTS ||--|| RESULTS : produces
  QUESTIONS ||--o{ ANSWERS : answered_in
  OPTIONS ||--o{ ANSWERS : chosen_as
  RESULTS ||--o{ CERTIFICATES : generates
  SUBJECTS ||--o{ TOPICS : has
  TOPICS ||--o{ LESSONS : has
  SUBJECTS ||--o{ TESTS : has
  TESTS ||--o{ QUESTIONS : has
  QUESTIONS ||--o{ OPTIONS : has
  QUESTIONS ||--o{ QUESTION_FILES : has
  USERS ||--o{ AI_CHATS : has
  USERS ||--o{ PAYMENTS : has
  USERS ||--o{ NOTIFICATIONS : has

  ROLES {
    uuid id PK
    string name
  }
  USERS {
    uuid id PK
    uuid role_id FK
    string first_name
    string email
    string status
  }
  TEST_ATTEMPTS {
    uuid id PK
    uuid user_id FK
    uuid test_id FK
    string status
  }
  ANSWERS {
    uuid id PK
    uuid attempt_id FK
    uuid question_id FK
    uuid selected_option FK
  }
  RESULTS {
    uuid id PK
    uuid attempt_id FK
    numeric score
  }
  CERTIFICATES {
    uuid id PK
    uuid result_id FK
    string certificate_number
  }
```

## Izoh

- Diagramma chat ichida interaktiv widget sifatida ham ko'rsatilgan edi (oldingi javobga qarang) — bu fayl o'sha diagrammaning GitHub'da render bo'ladigan versiyasi.
- `badges`, `plans`, `smtp_settings` kabi mustaqil/konfiguratsiya jadvallari asosiy oqimga bevosita bog'lanmagani uchun bu qisqartirilgan diagrammaga kiritilmadi — ular `database/schema_v1.sql` da to'liq mavjud.
- To'liq ustunlar ro'yxati (barcha 52 jadval) uchun: `docs/03_Database.md` va `database/schema_v1.sql`.
