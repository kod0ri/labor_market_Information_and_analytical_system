# 503Work — Технічний довідник

ETL-пайплайн + REST API + React-дашборд для аналізу IT-вакансій і резюме з work.ua.

---

## Структура проекту

```
project/
├── docker-compose.yml              # db, pgadmin, etl_worker, api, frontend
├── Dockerfile                      # образ для api та etl_worker
├── requirements.txt
├── run_pipeline.py                 # точка входу Prefect-пайплайну
│
├── src/
│   ├── scrapers/                   # асинхронний збір з work.ua
│   │   ├── utils.py
│   │   ├── workua_vacancies.py
│   │   └── workua_resumes.py
│   ├── processor/                  # LLM-обробка та збагачення
│   │   ├── nlp_vacancies.py        # Groq → витягає навички/ЗП/досвід
│   │   ├── nlp_resumes.py
│   │   ├── skill_normalizer.py     # "Python 3", "Пайтон" → одна сутність
│   │   ├── currency_converter.py   # НБУ API → *_usd_eq поля
│   │   ├── analytics_snapshot.py
│   │   ├── failure_tracker.py
│   │   ├── rate_limiter.py
│   │   ├── llm_utils.py
│   │   └── schemas.py              # Pydantic-схеми виводу LLM
│   ├── db/
│   │   └── database.py             # asyncpg connection pool (singleton)
│   ├── api/                        # FastAPI app + аналітичні routes
│   │   ├── main.py                 # CORS, lifespan, router registration
│   │   └── routes/
│   │       ├── health.py
│   │       └── analytics.py        # 11 аналітичних endpoints
│   ├── admin/                      # адмін-підсистема (SOLID)
│   │   ├── interfaces.py           # Protocol-інтерфейси (ISP/DIP)
│   │   ├── services.py             # StatsService, FailureService, PipelineService (SRP)
│   │   ├── facade.py               # AdminFacade + singleton (OCP)
│   │   └── router.py               # /api/admin/* — захищені JWT
│   ├── client/                     # клієнтська підсистема (GoF)
│   │   ├── filters.py              # Strategy-фільтри (salary, exp, location…)
│   │   ├── factory.py              # FilterStrategyFactory — Method Factory
│   │   ├── repository.py           # VacancyRepository, ResumeRepository
│   │   ├── facade.py               # MarketDataFacade + singleton
│   │   └── router.py               # /api/client/*
│   └── auth/
│       └── router.py               # JWT: /api/auth/login, /api/auth/me
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
│       │   ├── Topbar.tsx          # кнопка Вийти після авторизації
│       │   └── ...
│       └── pages/
│           ├── DashboardPage.tsx   # KPI + ринкова активність
│           ├── SkillsPage.tsx      # топ навичок + gap-аналіз
│           ├── SalaryPage.tsx      # розподіл ЗП + досвід
│           ├── GeographyPage.tsx   # топ міст
│           ├── ClientSearchPage.tsx # пошук вакансій/резюме з фільтрами
│           ├── AdminPage.tsx       # адмін-панель (потребує входу)
│           └── LoginPage.tsx       # форма входу
│
└── init_db/                        # SQL-міграції (виконуються при першому старті)
    ├── 00_schemas.sql
    ├── 01_dictionaries.sql
    ├── 02_staging.sql
    ├── 03_core.sql
    ├── 04_analytics.sql
    ├── 05_skill_normalization.sql
    ├── 06_failed_records.sql
    └── 07_constraints_and_indexes.sql
```

---

## Швидкий старт

```bash
cp .env.example .env               # заповни змінні
docker compose up -d --build       # піднімає все: db, api, frontend
```

Відкрий [http://localhost:5173](http://localhost:5173).

Перший збір даних:
```bash
docker compose run --rm etl_worker   # ~30–90 хв
docker compose logs etl_worker -f    # слідкувати за прогресом
```

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
| GET | `/api/analytics/activity` | `bucket=day\|week\|month`, `days=N` |
| GET | `/api/analytics/experience-timeline` | `type=vacancy\|resume`, `bucket`, `days` |
| GET | `/api/analytics/skills` | `type`, `limit=20`, `category=Hard\|Soft` |
| GET | `/api/analytics/skills/gap` | `limit=20` |
| GET | `/api/analytics/locations` | `type`, `limit=10` |
| GET | `/api/analytics/salary-distribution` | `type` |
| GET | `/api/analytics/english-levels` | `type` |
| GET | `/api/analytics/experience-levels` | `type` |
| GET | `/api/analytics/companies` | `limit=10` |

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

### Admin (потребує `Authorization: Bearer <token>`)

| Метод | URL | Опис |
|-------|-----|------|
| GET | `/api/admin/stats` | статистика БД (вакансії, резюме, словники, черга) |
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

4 стадії, оркестровано через Prefect:

1. **Scrape** — `workua_vacancies.py` + `workua_resumes.py` → `staging.raw_*` (до 50 сторінок)
2. **NLP** — Groq `llama-4-scout-17b` витягує навички/зарплати/досвід → `core.*`
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
                           │    dictionaries.sources
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
| `GROQ_API_KEY` | Так (для ETL) | API-ключ Groq |
| `ADMIN_USERNAME` | Ні | Логін адмін-панелі (default: `admin`) |
| `ADMIN_PASSWORD` | Ні | Пароль адмін-панелі (default: `admin`) |
| `JWT_SECRET` | Ні | Секрет для підпису JWT (змінити в prod!) |
| `CORS_ORIGINS` | Ні | Дозволені origins через кому |
| `PGADMIN_EMAIL` | Ні | Email для pgAdmin |
| `PGADMIN_PASSWORD` | Ні | Пароль для pgAdmin |

---

## Корисні команди

```bash
# ── Docker ──────────────────────────────────────────────────────────────
docker compose up -d --build           # підняти все з пересбіркою
docker compose up -d                   # підняти без rebuild
docker compose ps                      # статус контейнерів
docker compose logs api -f             # логи бекенду
docker compose logs frontend -f        # логи nginx
docker compose logs etl_worker -f      # логи ETL
docker compose restart api             # рестарт API
docker compose build api frontend      # перебудувати образи
docker compose down                    # зупинити все
docker compose down -v                 # зупинити + видалити томи (УВАГА: дані)

# ── ETL ─────────────────────────────────────────────────────────────────
docker compose run --rm etl_worker                              # повний пайплайн
docker compose run --rm etl_worker python src/processor/currency_converter.py
docker compose run --rm etl_worker python src/processor/analytics_snapshot.py backfill 30

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
| Графіки порожні | ETL не запускався | `docker compose run --rm etl_worker` |
| `avg_salary: null` | currency_converter не пройшов | `docker compose run --rm etl_worker python src/processor/currency_converter.py` |
| CORS-помилка у браузері | `CORS_ORIGINS` не налаштовано | Додай origin у `.env`, `docker compose restart api` |
| 401 при вході в адмінку | Неправильні `ADMIN_USERNAME`/`ADMIN_PASSWORD` | Перевір `.env` |
| Groq 429 у логах | Rate limit (20 RPM) | Нормально — скрипт сам ретраїть |
| `disk full` через postgres_data | Staging не очищено після NLP | `TRUNCATE staging.raw_vacancies; TRUNCATE staging.raw_resumes;` |
