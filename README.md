# 503Work — Інформаційно-аналітична система ринку праці

ETL-пайплайн + REST API + React-фронтенд для аналізу IT-вакансій і резюме з work.ua.

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ work.ua  │───▶│  Scraper │───▶│  Groq    │───▶│PostgreSQL│
└──────────┘    │  asyncio │    │  LLM     │    │   core.* │
                └──────────┘    └──────────┘    └────┬─────┘
                                                     │
                  ┌──────────────────────────────────┘
                  ▼
          ┌──────────────┐         ┌─────────────────┐
          │  FastAPI     │◀────────│  503Work UI     │
          │  :8000       │   JSON  │  React + Vite   │
          └──────────────┘         │  :5173          │
                                   └─────────────────┘
```

---

## Структура проекту

```
project/
├── src/                          # Backend (Python)
│   ├── scrapers/                 # Збір даних з work.ua
│   │   ├── utils.py
│   │   ├── workua_vacancies.py
│   │   └── workua_resumes.py
│   ├── processor/                # Обробка та збагачення
│   │   ├── nlp_vacancies.py      # LLM-екстракція з вакансій
│   │   ├── nlp_resumes.py        # LLM-екстракція з резюме
│   │   ├── currency_converter.py # НБУ → USD
│   │   ├── analytics_snapshot.py
│   │   ├── skill_normalizer.py
│   │   ├── failure_tracker.py
│   │   ├── rate_limiter.py
│   │   ├── llm_utils.py
│   │   └── schemas.py            # Pydantic-схеми
│   ├── api/                      # REST API для фронтенда
│   │   ├── main.py               # FastAPI + CORS
│   │   └── routes/
│   │       ├── health.py
│   │       ├── analytics.py      # 11 endpoints аналітики
│   │       ├── vacancies.py      # Список з фільтрами
│   │       └── resumes.py        # Список з фільтрами
│   └── db/
│       └── database.py           # asyncpg pool
├── frontend/                     # 503Work — React UI
│   ├── src/
│   │   ├── api/                  # client, hooks, types
│   │   ├── components/           # UI + charts/
│   │   ├── pages/                # Dashboard, Vacancies, Resumes, Skills, Salary, Geography
│   │   ├── lib/                  # format, theme
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── init_db/                      # SQL-міграції (виконуються при старті Docker)
│   ├── 00_schemas.sql
│   ├── 01_dictionaries.sql
│   ├── 02_staging.sql
│   ├── 03_core.sql
│   ├── 04_analytics.sql
│   ├── 05_skill_normalization.sql
│   ├── 06_failed_records.sql
│   └── 07_constraints_and_indexes.sql
├── run_pipeline.py               # Точка входу ETL (Prefect flow)
├── docker-compose.yml
├── Dockerfile
└── .env                          # Не комітити!
```

---

## Передумови

| Інструмент | Версія |
|------------|--------|
| Docker + Docker Compose | остання стабільна |
| Node.js | 18+ (рекомендовано 20+) |
| Groq API Key | безкоштовно на [console.groq.com](https://console.groq.com) |

(Python потрібен лише для локального запуску ETL без Docker — версія 3.11+.)

---

## Швидкий старт

### 1. Налаштувати `.env`

```bash
cp .env.example .env
```

Мінімум для запуску:

```env
DB_USER=admin_denis
DB_PASSWORD=your_password
DB_NAME=core_postgres
GROQ_API_KEY=gsk_...
```

### 2. Підняти БД та API

```bash
docker compose up db api -d
```

| Сервіс | Адреса |
|--------|--------|
| PostgreSQL | `localhost:5432` |
| REST API | `http://localhost:8000` |
| Swagger UI | `http://localhost:8000/docs` |
| pgAdmin | `http://localhost:5050` (опційно) |

### 3. Запустити ETL (збір даних)

```bash
docker compose run --rm etl_worker
```

⏱ Орієнтовний час: **30–90 хв** (ліміт Groq: 20 RPM). Прогрес можна дивитись:

```bash
docker compose logs etl_worker -f
```

### 4. Запустити фронтенд

```bash
cd frontend
npm install
npm run dev
```

Відкрий `http://localhost:5173`.

---

## 503Work UI — сторінки

| Маршрут | Що показує |
|---------|------------|
| `/` | Дашборд: KPI, активність ринку, структура досвіду у часі, топ навичок/міст, англійська, топ роботодавців |
| `/vacancies` | Таблиця вакансій з фільтрами (навичка, місто, мін. ЗП, досвід ≤ N) та пагінацією |
| `/resumes` | Таблиця резюме з фільтрами (навичка, місто, мін. ЗП, досвід ≥ N) та пагінацією |
| `/skills` | Топ навичок (попит/пропозиція), Gap-аналіз з топом дефіциту та перенасичення |
| `/salary` | Розподіл зарплат у USD, гістограми, ЗП по рівнях досвіду для вакансій vs резюме |
| `/geography` | Топ-20 міст за вакансіями/резюме з ранг-списком |

Тема `світла/темна` з персистенцією у `localStorage`. Бренд-колір: `#f95514` (orange).

---

## REST API

**Base URL:** `http://localhost:8000`
**Інтерактивна документація:** `http://localhost:8000/docs`

### System

| Метод | URL | Опис |
|-------|-----|------|
| GET | `/health` | Стан сервера та БД |

### Analytics

| Метод | URL | Параметри | Опис |
|-------|-----|-----------|------|
| GET | `/api/analytics/overview` | — | KPI: кількість вакансій/резюме, середні ЗП |
| GET | `/api/analytics/activity` | `bucket=day\|week\|month`, `days=N` | Нові оголошення по бакетах + сер. ЗП за період |
| GET | `/api/analytics/experience-timeline` | `type=vacancy\|resume`, `bucket`, `days` | Junior/Middle/Senior розподіл по бакетах |
| GET | `/api/analytics/snapshots` | `days=30` | Старі щоденні snapshot'и (legacy) |
| GET | `/api/analytics/skills` | `type`, `limit=20`, `category=Hard\|Soft` | Топ навичок |
| GET | `/api/analytics/skills/gap` | `limit=20` | Gap-аналіз попит vs пропозиція |
| GET | `/api/analytics/locations` | `type`, `limit=10` | Географія |
| GET | `/api/analytics/salary-distribution` | `type` | Гістограма зарплат |
| GET | `/api/analytics/english-levels` | `type` | Розподіл за рівнем англійської |
| GET | `/api/analytics/experience-levels` | `type` | Бакети досвіду + сер. ЗП у бакеті |
| GET | `/api/analytics/companies` | `limit=10` | Топ роботодавців |

### Vacancies / Resumes

| Метод | URL | Параметри |
|-------|-----|-----------|
| GET | `/api/vacancies/` | `page`, `limit`, `skill`, `location`, `min_salary_usd`, `experience_years` (≤) |
| GET | `/api/resumes/` | `page`, `limit`, `skill`, `location`, `min_salary_usd`, `experience_years` (≥) |

### Приклади відповідей

**`GET /api/analytics/overview`**
```json
{
  "total_vacancies": 314,
  "total_resumes": 324,
  "vacancies_with_salary": 121,
  "resumes_with_salary": 198,
  "avg_vacancy_salary_usd": 912,
  "avg_resume_salary_usd": 845
}
```

**`GET /api/analytics/activity?bucket=week&days=90`**
```json
[
  {"bucket_start": "2026-04-27", "new_vacancies": 150, "new_resumes": 158, "avg_vacancy_salary_usd": 917, "avg_resume_salary_usd": 884},
  {"bucket_start": "2026-05-18", "new_vacancies": 197, "new_resumes": 200, "avg_vacancy_salary_usd": 909, "avg_resume_salary_usd": 798}
]
```

**`GET /api/analytics/experience-timeline?type=vacancy&bucket=week`**
```json
[
  {"bucket_start": "2026-04-27", "junior": 67, "middle": 40, "senior": 4, "unknown": 39},
  {"bucket_start": "2026-05-18", "junior": 76, "middle": 55, "senior": 9, "unknown": 57}
]
```

**`GET /api/vacancies/?skill=Python&limit=1`**
```json
{
  "total": 14,
  "page": 1,
  "limit": 1,
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
      "created_at": "2026-04-27T10:00:00",
      "skills": ["Docker", "FastAPI", "PostgreSQL", "Python"]
    }
  ]
}
```

### CORS

Дозволено `http://localhost:3000` та `http://localhost:5173` за замовчуванням. Інше — через `.env`:

```env
CORS_ORIGINS=http://localhost:4000,http://example.com
```

---

## ETL-пайплайн

4 стадії, оркестровано через Prefect:

1. **Scrape** — `workua_vacancies.py` + `workua_resumes.py` → `staging.raw_*` (до 50 сторінок кожен)
2. **NLP** — `nlp_vacancies.py` + `nlp_resumes.py` → Groq `llama-4-scout-17b` витягує навички/зарплати/досвід → `core.*`
3. **Currency** — `currency_converter.py` → НБУ API → `*_usd_eq` поля
4. **Snapshot** — `analytics_snapshot.py` → `analytics.daily_market_snapshots`

Точка входу: `run_pipeline.py`.

---

## Схема бази даних

```
staging.raw_vacancies    ──┐
staging.raw_resumes      ──┤─→ [ETL] ─→ core.vacancies  ──→ core.vacancy_skills
staging.failed_records     │            core.resumes    ──→ core.resume_skills
                           │                 │
                           │      dictionaries.skills
                           │      dictionaries.skill_synonyms
                           │      dictionaries.locations
                           │      dictionaries.companies
                           │      dictionaries.sources
                           │
                           └──→ analytics.daily_market_snapshots
```

---

## Стек технологій

**Backend:** Python 3.11, asyncio, aiohttp, BeautifulSoup, asyncpg, Prefect, Groq API, Pydantic v2, FastAPI, PostgreSQL 16, Docker.

**Frontend:** React 19, TypeScript, Vite, Tailwind CSS 3, React Router v6, @tanstack/react-query, recharts.

---

## Корисні команди

```bash
# ── Docker ──────────────────────────────────────────────
docker compose up db api -d                # БД + API
docker compose run --rm etl_worker         # одноразовий ETL
docker compose logs api -f                 # логи API
docker compose logs etl_worker -f          # логи ETL
docker compose restart api                 # рестарт API
docker compose build api                   # перебудувати образ
docker compose down                        # зупинити все
docker compose down -v                     # зупинити + видалити дані (УВАГА)

# ── ETL ─────────────────────────────────────────────────
docker compose run --rm etl_worker python src/processor/currency_converter.py
docker compose run --rm etl_worker python src/processor/analytics_snapshot.py backfill 30

# ── База ────────────────────────────────────────────────
docker exec -it postgres_db psql -U admin_denis -d core_postgres

# Скільки даних маємо:
docker exec postgres_db psql -U admin_denis -d core_postgres -c "
  SELECT
    (SELECT COUNT(*) FROM core.vacancies)        AS vacancies,
    (SELECT COUNT(*) FROM core.resumes)          AS resumes,
    (SELECT COUNT(*) FROM staging.raw_vacancies) AS raw_vacancies,
    (SELECT COUNT(*) FROM staging.raw_resumes)   AS raw_resumes;
"

# ── Frontend ────────────────────────────────────────────
cd frontend
npm install
npm run dev                                # dev :5173
npm run build                              # production build → dist/
npm run lint
```

---

## Локальний запуск без Docker

```bash
pip install -r requirements.txt
docker compose up db -d                    # БД у Docker, інше локально
python run_pipeline.py                     # ETL
uvicorn src.api.main:app --reload --port 8000   # API

cd frontend && npm install && npm run dev  # Frontend
```

---

## Змінні оточення

| Змінна | Обов'язкова | Опис |
|--------|-------------|------|
| `DB_USER` | Так | Користувач PostgreSQL |
| `DB_PASSWORD` | Так | Пароль PostgreSQL |
| `DB_NAME` | Так | Назва бази даних |
| `DB_HOST` | Ні | Хост БД (default: `localhost`, у docker: `db`) |
| `DB_PORT` | Ні | Порт БД (default: `5432`) |
| `GROQ_API_KEY` | Так (для ETL) | API-ключ Groq для NLP |
| `PGADMIN_EMAIL` | Ні | Email для pgAdmin |
| `PGADMIN_PASSWORD` | Ні | Пароль для pgAdmin |
| `CORS_ORIGINS` | Ні | Дозволені origins для фронтенда (через кому) |
| `VITE_API_BASE_URL` | Ні | API URL для фронтенда (default: `http://localhost:8000`) — у `frontend/.env` |

---

## Часті проблеми

**API повертає 404 на нові endpoint'и** — старий образ. Перезібрати:
```bash
docker compose build api && docker compose up -d api
```

**Графіки порожні** — ETL не запускався або не догнав:
```bash
docker compose run --rm etl_worker
```

**CORS-помилка у браузері** — додати порт у `.env` і `docker compose restart api`:
```env
CORS_ORIGINS=http://localhost:5173
```

**`avg_*_salary_usd: null`** — currency_converter не пройшов:
```bash
docker compose run --rm etl_worker python src/processor/currency_converter.py
```

**Groq повертає 429 (rate limit)** — нормально, скрипт сам ретраїть. Чекай.

---

## Документація для команди

- [REACT_DEV_GUIDE.md](REACT_DEV_GUIDE.md) — повний гайд по фронтенду (legacy, перед `503work/` рефактором)
- [GUIDE_HOW_TO_UP_DB.md](GUIDE_HOW_TO_UP_DB.md) — як підняти БД з дампу
- [frontend/README.md](frontend/README.md) — README фронтенда
