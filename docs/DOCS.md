# 503Work — Технічний довідник

ETL-пайплайн + REST API + React-дашборд для аналізу IT-вакансій і резюме.
Джерела: **work.ua** (HTML), **DOU** (RSS) та **robota.ua** (GraphQL) — усі через LLM-обробку.

> **Версія:** 2.0.0 — багатоджерельний збір + каскад безкоштовних LLM (Cerebras → Groq → Gemini → Mistral).

---

## Структура проекту

```
project/
├── docker-compose.yml              # db, pgadmin, etl_worker, api, frontend
├── Dockerfile                      # образ для api та etl_worker
├── requirements.txt                # прод-залежності
├── requirements-dev.txt            # + pytest, pytest-asyncio
├── pytest.ini / conftest.py        # конфіг тестів (sys.path → корінь)
├── run_pipeline.py                 # точка входу Prefect-пайплайну
│
├── src/
│   ├── scrapers/                   # work.ua (HTML)
│   │   ├── utils.py
│   │   ├── workua_vacancies.py
│   │   └── workua_resumes.py
│   ├── sources/                    # додаткові джерела (теж → LLM-обробка)
│   │   ├── dou_rss.py              # DOU — RSS-стрічки вакансій
│   │   └── robota_vacancies.py     # robota.ua — GraphQL (браузерні заголовки, Cloudflare)
│   ├── processor/                  # LLM-обробка та збагачення
│   │   ├── llm_cascade.py          # каскад провайдерів: complete() + fallback/cooldown
│   │   ├── rate_limiter.py         # DailyBudget (TPD/RPD) + TokenBucketRateLimiter
│   │   ├── llm_utils.py            # парсинг retry-after з 429 тощо
│   │   ├── nlp_vacancies.py        # drain-режим → витягає навички/ЗП/досвід → core.*
│   │   ├── nlp_resumes.py
│   │   ├── skill_normalizer.py     # "Python 3", "Пайтон" → одна сутність
│   │   ├── currency_converter.py   # НБУ API → *_usd_eq поля
│   │   ├── analytics_snapshot.py
│   │   ├── failure_tracker.py
│   │   └── schemas.py              # Pydantic-схеми виводу LLM
│   ├── db/
│   │   └── database.py             # asyncpg connection pool (singleton)
│   ├── api/                        # FastAPI app
│   │   ├── main.py                 # CORS, lifespan, router registration
│   │   ├── ratelimit.py            # IP-rate-limit для публічних ендпоінтів
│   │   └── routes/
│   │       ├── health.py
│   │       ├── analytics.py        # 12 аналітичних endpoints
│   │       └── tracking.py         # POST /api/track — анонімний beacon
│   ├── admin/                      # адмін-підсистема (SOLID)
│   │   ├── interfaces.py           # Protocol-інтерфейси (ISP/DIP)
│   │   ├── services.py             # Stats / Failure / Pipeline / System Service (SRP)
│   │   ├── facade.py               # AdminFacade + singleton (OCP)
│   │   └── router.py               # /api/admin/* — захищені JWT
│   ├── client/                     # клієнтська підсистема (GoF)
│   │   ├── filters.py              # Strategy-фільтри (salary, exp, location…)
│   │   ├── factory.py              # FilterStrategyFactory — Method Factory
│   │   ├── repository.py           # VacancyRepository, ResumeRepository
│   │   ├── facade.py               # MarketDataFacade + singleton
│   │   └── router.py               # /api/client/*
│   ├── auth/                       # JWT-автентифікація (акаунти в auth.users)
│   │   ├── bootstrap.py            # засів адміна з ADMIN_USERNAME/PASSWORD
│   │   ├── repository.py
│   │   ├── security.py             # хешування пароля, видача/перевірка JWT
│   │   └── router.py               # /api/auth/login, /api/auth/me
│   └── tracking/                   # облік анонімних візитів
│       ├── bootstrap.py
│       └── repository.py
│
├── scripts/
│   └── create_user.py              # python -m scripts.create_user --username NAME
│
├── tests/
│   ├── test_llm_cascade.py         # вибір провайдера, fallback на 429, cooldown, бюджет
│   └── test_rate_limiter.py        # DailyBudget + TokenBucketRateLimiter
│
├── frontend/
│   ├── Dockerfile                  # multi-stage: node build → nginx
│   ├── nginx.conf                  # роздача dist/ + proxy /api → api:8000
│   ├── vite.config.ts              # proxy для локальної розробки
│   └── src/
│       ├── auth/
│       │   └── AuthContext.tsx     # токен у localStorage, login/logout
│       ├── api/
│       │   ├── client.ts           # fetch-обгортки, authHeaders
│       │   ├── hooks.ts            # TanStack Query hooks
│       │   └── types.ts            # TypeScript-інтерфейси
│       ├── components/
│       │   ├── charts/             # recharts-компоненти
│       │   ├── ProtectedRoute.tsx  # редірект на /login якщо немає токена
│       │   ├── Sidebar.tsx
│       │   ├── Topbar.tsx
│       │   └── ...
│       └── pages/
│           ├── DashboardPage.tsx   # KPI + ринкова активність
│           ├── SkillsPage.tsx      # топ навичок + gap-аналіз
│           ├── SalaryPage.tsx      # розподіл ЗП + досвід
│           ├── GeographyPage.tsx   # топ міст
│           ├── ClientSearchPage.tsx # пошук вакансій/резюме з фільтрами
│           ├── AdminPage.tsx       # адмін-панель (потребує входу)
│           ├── LoginPage.tsx       # форма входу
│           └── NotFoundPage.tsx
│
└── init_db/                        # SQL-міграції (виконуються при першому старті)
    ├── 00_schemas.sql
    ├── 01_dictionaries.sql
    ├── 02_staging.sql
    ├── 03_core.sql
    ├── 04_analytics.sql
    ├── 05_skill_normalization.sql
    ├── 06_failed_records.sql
    ├── 07_constraints_and_indexes.sql
    ├── 08_auth_users.sql            # auth.users (адмін-акаунти)
    └── 09_visits.sql                # облік анонімних візитів
```

---

## Швидкий старт

```bash
cp .env.example .env               # заповни: ≥1 LLM-ключ, JWT_SECRET, DB_PASSWORD
docker compose up -d --build       # піднімає все: db, api, frontend
```

Відкрий [http://localhost:5173](http://localhost:5173).

Перший збір даних:
```bash
docker compose run --rm etl_worker   # ~30–90 хв
docker compose logs etl_worker -f    # слідкувати за прогресом
```

---

## LLM-каскад

NLP-обробка (`src/processor/llm_cascade.py`) — це **послідовний fallback** по безкоштовних
OpenAI-сумісних провайдерах. Усі викликаються через `openai.AsyncOpenAI` з різним `base_url`
і однаковою формою запиту (`chat.completions` + `response_format=json_object`).

**Як працює:**
- На кожен запис береться перший провайдер, чий **денний бюджет** ще не вичерпано.
- Кожен провайдер має власні `DailyBudget` (TPD/RPD, стоп на 96%) і `TokenBucketRateLimiter` (пейсинг під RPM).
- При `429`/помилці провайдер «остуджують» (cooldown на час із `retry-after`), і всі паралельні задачі його пропускають → падають на наступного.
- Сумарна добова продуктивність = **сума денних квот** усіх увімкнених провайдерів.
- Активуються лише провайдери з заданим API-ключем. Достатньо одного.

**Провайдери за замовчуванням** (`Cerebras → Groq → Gemini → Mistral`):

| Провайдер | Модель (default) | Безкоштовна стеля | Примітка |
|-----------|------------------|-------------------|----------|
| Cerebras  | `gpt-oss-120b`   | ~1 млн ток/добу, 5 RPM / 2400 RPD | reasoning-модель; `reasoning_effort=low` ріже output ~2–3× |
| Groq      | `meta-llama/llama-4-scout-17b-16e-instruct` | 500K ток/добу, 1K RPD | — |
| Gemini    | `gemini-3.1-flash-lite` | 500 RPD (free tier) | 2.5-flash має лише 20 RPD |
| Mistral   | `mistral-small-latest` | ~1 млрд ток/міс | free «Experiment», 1 req/s |

**Drain-режим:** `nlp_vacancies.main()` / `nlp_resumes.main()` крутять порції по
`NLP_BATCH_LIMIT` записів, поки черга не спорожніє **або** денні бюджети всіх провайдерів
не вичерпаються. Тобто один cron/добу вже вибирає денну стелю. Тимчасове вичерпання
(усі провайдери в cooldown) **не** пише в `failed_records` — запис повторюється на
наступному прогоні.

**Справедливість джерел:** черга вакансій вибирається round-robin по `source_name`
(`ROW_NUMBER() OVER (PARTITION BY source_name ORDER BY id)`), тож кожен батч тягне
work.ua / DOU / robota.ua порівну. Інакше старіший беклог work.ua (нижчі id) забивав би
весь денний бюджет, а нові джерела «голодували» б. Резюме — лише work.ua, тож там без змін.

---

## REST API

**Base URL:** `http://localhost:8000`  
**Swagger UI:** `http://localhost:8000/docs`

### System

| Метод | URL | Опис |
|-------|-----|------|
| GET | `/health` | Стан сервера та БД |

### Analytics

| Метод | URL | Параметри |
|-------|-----|-----------|
| GET | `/api/analytics/overview` | — |
| GET | `/api/analytics/snapshots` | `days=N` |
| GET | `/api/analytics/activity` | `bucket=day\|week\|month`, `days=N` |
| GET | `/api/analytics/experience-timeline` | `type=vacancy\|resume`, `bucket`, `days` |
| GET | `/api/analytics/skills` | `type`, `limit=20`, `category=Hard\|Soft` |
| GET | `/api/analytics/skills/gap` | `limit=20` |
| GET | `/api/analytics/locations` | `type`, `limit=10` |
| GET | `/api/analytics/salary-distribution` | `type` |
| GET | `/api/analytics/english-levels` | `type` |
| GET | `/api/analytics/experience-levels` | `type` |
| GET | `/api/analytics/companies` | `limit=10` |
| GET | `/api/analytics/sources` | — (розбивка обсягів за джерелами) |

### Tracking

| Метод | URL | Опис |
|-------|-----|------|
| POST | `/api/track` | Анонімний beacon відвідувача → `204` (IP-rate-limited) |

### Client (пошук)

| Метод | URL | Параметри |
|-------|-----|-----------|
| GET | `/api/client/vacancies/search` | `page`, `page_size`, `skill`, `location`, `min_salary_usd`, `experience_max`, `english_level` |
| GET | `/api/client/resumes/search` | `page`, `page_size`, `skill`, `location`, `min_salary_usd`, `experience_min`, `english_level` |

### Auth

| Метод | URL | Опис |
|-------|-----|------|
| POST | `/api/auth/login` | `{ username, password }` → `{ access_token }` |
| GET | `/api/auth/me` | перевірка токена |

Акаунти зберігаються в `auth.users` (пароль — лише хеш). Перший адмін засівається з
`ADMIN_USERNAME`/`ADMIN_PASSWORD` на старті; додати ще — `python -m scripts.create_user --username NAME`.
Реєстрації через UI немає.

### Admin (потребує `Authorization: Bearer <token>`)

| Метод | URL | Опис |
|-------|-----|------|
| GET | `/api/admin/stats` | статистика БД (вакансії, резюме, словники, черга) |
| GET | `/api/admin/system` | метрики сервера (диск/CPU/пам'ять) + користувачі/візити |
| GET | `/api/admin/pipeline/status` | черга + помилки за типами + останній запис |
| GET | `/api/admin/failures` | список нерозв'язаних помилок (`limit=50`) |
| PATCH | `/api/admin/failures/{id}/resolve` | позначити помилку як вирішену |

### Приклади відповідей

**`GET /api/analytics/overview`**
```json
{
  "total_vacancies": 696,
  "total_resumes": 712,
  "vacancies_with_salary": 280,
  "resumes_with_salary": 430,
  "avg_vacancy_salary_usd": 912,
  "avg_resume_salary_usd": 845
}
```

**`GET /api/analytics/sources`**
```json
[
  { "source": "work.ua",   "vacancies": 412, "resumes": 712 },
  { "source": "DOU",       "vacancies": 168, "resumes": 0 },
  { "source": "robota.ua", "vacancies": 116, "resumes": 0 }
]
```

**`GET /api/client/vacancies/search?skill=Python&page_size=1`**
```json
{
  "total": 48,
  "page": 1,
  "page_size": 1,
  "pages": 48,
  "items": [
    {
      "id": 1,
      "title": "Python Developer",
      "company_name": "TechCorp",
      "city_name": "Київ",
      "region": "Київська область",
      "min_salary_usd_eq": 2000.0,
      "max_salary_usd_eq": 3500.0,
      "experience_years": 2,
      "english_level": "Intermediate",
      "created_at": "2026-05-01T10:00:00",
      "skills": ["Docker", "FastAPI", "PostgreSQL", "Python"]
    }
  ]
}
```

**`POST /api/auth/login`**
```json
{ "username": "admin", "password": "admin" }
→ { "access_token": "eyJ...", "token_type": "bearer" }
```

---

## ETL-пайплайн

4 стадії, оркестровано через Prefect (`run_pipeline.py`):

1. **Collect** (паралельно) — work.ua вакансії+резюме (`workua_*`), DOU RSS (`dou_rss`),
   robota.ua GraphQL (`robota_vacancies`) → `staging.raw_*`
2. **NLP** — LLM-каскад (Cerebras → Groq → Gemini → Mistral) у drain-режимі витягує
   навички/зарплати/досвід → `core.*`
3. **Currency** — НБУ API → конвертація в USD → `*_usd_eq` поля
4. **Snapshot** — `analytics.daily_market_snapshots`

---

## Схема бази даних

```
staging.raw_vacancies    ──┐
staging.raw_resumes      ──┤──▶ [ETL] ──▶ core.vacancies ──▶ core.vacancy_skills
staging.failed_records     │             core.resumes    ──▶ core.resume_skills
                           │
                           │    dictionaries.skills / skill_synonyms
                           │    dictionaries.locations
                           │    dictionaries.companies
                           │    dictionaries.sources        (work.ua / DOU / robota.ua)
                           │
                           │    auth.users                  (адмін-акаунти)
                           │    analytics.visits            (анонімні візити)
                           │
                           └──▶ analytics.daily_market_snapshots
```

---

## Змінні середовища

| Змінна | Обов'язкова | Опис |
|--------|-------------|------|
| `DB_USER` | Так | Користувач PostgreSQL |
| `DB_PASSWORD` | Так | Пароль PostgreSQL |
| `DB_NAME` | Так | Назва бази |
| `DB_HOST` | Ні | Хост БД (default: `localhost`, у Docker: `db`) |
| `DB_PORT` | Ні | Порт БД (default: `5432`) |
| `CEREBRAS_API_KEY` | Хоча б один | Ключ Cerebras для каскаду |
| `GROQ_API_KEY` | Хоча б один | Ключ Groq для каскаду |
| `GEMINI_API_KEY` | Хоча б один | Ключ Gemini для каскаду |
| `MISTRAL_API_KEY` | Хоча б один | Ключ Mistral для каскаду |
| `LLM_PROVIDER_ORDER` | Ні | Порядок/склад каскаду через кому, напр. `cerebras,groq` |
| `CEREBRAS_MODEL` / `GROQ_MODEL` / `GEMINI_MODEL` / `MISTRAL_MODEL` | Ні | Перевизначення моделей |
| `NLP_BATCH_LIMIT` | Ні | Розмір порції в drain-режимі (default: `200`) |
| `ROBOTA_MAX_PAGES` | Ні | Сторінок robota.ua за прогін (default: `25`) |
| `JWT_SECRET` | **Так** | Секрет для підпису JWT — без нього застосунок не стартує (`openssl rand -hex 32`) |
| `ADMIN_USERNAME` | Ні | Логін засіяного адміна (default: `admin`) |
| `ADMIN_PASSWORD` | Ні | Пароль засіяного адміна |
| `CORS_ORIGINS` | Ні | Дозволені origins через кому |
| `METRICS_DISK_PATH` | Ні | Шлях для метрики диска в адмінці (default: `/`) |
| `TRACK_RATE_LIMIT` | Ні | Ліміт `POST /api/track` (запитів/хв з IP) |
| `LOGIN_RATE_LIMIT` | Ні | Ліміт `POST /api/auth/login` (захист від перебору) |
| `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` | Ні | Доступ до pgAdmin |

> Достатньо **одного** LLM-ключа — решта провайдерів просто не вмикаються.
> Рекомендований мінімум для пристойної денної стелі: `CEREBRAS_API_KEY` + `GROQ_API_KEY`.

---

## Корисні команди

```bash
# ── Docker ──────────────────────────────────────────────────────────────
docker compose up -d --build           # підняти все з пересбіркою
docker compose up -d                   # підняти без rebuild
docker compose ps                      # статус контейнерів
docker compose logs api -f             # логи бекенду
docker compose logs frontend -f        # логи nginx
docker compose logs etl_worker -f      # логи ETL (видно [provider/model] на кожен запис)
docker compose restart api             # рестарт API
docker compose build api frontend      # перебудувати образи
docker compose down                    # зупинити все
docker compose down -v                 # зупинити + видалити томи (УВАГА: дані)

# ── ETL ─────────────────────────────────────────────────────────────────
docker compose run --rm etl_worker                              # повний пайплайн
docker compose run --rm etl_worker python src/processor/currency_converter.py
docker compose run --rm etl_worker python src/processor/analytics_snapshot.py backfill 30

# ── Користувачі ──────────────────────────────────────────────────────────
docker compose exec api python -m scripts.create_user --username NAME

# ── Тести ────────────────────────────────────────────────────────────────
pip install -r requirements-dev.txt && pytest    # каскад + бюджети + rate-limiter

# ── База ─────────────────────────────────────────────────────────────────
docker exec -it postgres_db psql -U <DB_USER> -d <DB_NAME>

# Скільки даних:
docker exec postgres_db psql -U <DB_USER> -d <DB_NAME> -c "
  SELECT
    (SELECT COUNT(*) FROM core.vacancies)        AS vacancies,
    (SELECT COUNT(*) FROM core.resumes)          AS resumes,
    (SELECT COUNT(*) FROM staging.raw_vacancies) AS raw_vac,
    (SELECT COUNT(*) FROM staging.raw_resumes)   AS raw_res;
"
```

---

## Локальна розробка без Docker

```bash
# Потрібен conda env або venv з requirements.txt
conda activate labor_market

# БД у Docker, решта — локально
docker compose up db -d

# Backend
uvicorn src.api.main:app --reload --port 8000

# Frontend (Vite проксує /api → :8000 автоматично)
cd frontend && npm install && npm run dev
```

---

## Часті проблеми

| Симптом | Причина | Рішення |
|---------|---------|---------|
| API 404 на нові endpoints | Старий Docker-образ | `docker compose build api && docker compose up -d api` |
| Застосунок не стартує: «JWT_SECRET» | Порожній/дефолтний `JWT_SECRET` | Згенеруй `openssl rand -hex 32`, додай у `.env`, перезапусти |
| `НЕМАЄ ПРОВАЙДЕРІВ` у логах ETL | Не задано жодного LLM-ключа | Додай хоча б один `*_API_KEY` у `.env` |
| Графіки порожні | ETL не запускався | `docker compose run --rm etl_worker` |
| `avg_salary: null` | currency_converter не пройшов | `docker compose run --rm etl_worker python src/processor/currency_converter.py` |
| CORS-помилка у браузері | `CORS_ORIGINS` не налаштовано | Додай origin у `.env`, `docker compose restart api` |
| 401 при вході в адмінку | Невірні креди / акаунт не засіяний | Перевір `ADMIN_*` або `python -m scripts.create_user` |
| `429` від провайдера у логах | Rate limit | Норма — каскад остуджує провайдера й падає на наступного |
| robota.ua повертає 403 | Cloudflare-челендж | Збирач шле браузерні заголовки; зменш `ROBOTA_MAX_PAGES`, спробуй пізніше |
| `PrefectRouter has no attribute 'routes'` | FastAPI ≥ 0.137 ламає Prefect 3.x | Закріплено `fastapi<0.137` у requirements — пересобери образ |
| `disk full` через postgres_data | Staging не очищено після NLP | `TRUNCATE staging.raw_vacancies; TRUNCATE staging.raw_resumes;` |
