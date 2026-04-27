# Інформаційно-аналітична система ринку праці

ETL-пайплайн + REST API для аналізу вакансій і резюме з work.ua (IT-сектор).

---

## Структура проекту

```
project/
├── src/
│   ├── scrapers/          # Збір даних з work.ua
│   │   ├── utils.py       # Спільний fetch_html
│   │   ├── workua_vacancies.py
│   │   └── workua_resumes.py
│   ├── processor/         # Обробка та збагачення даних
│   │   ├── nlp_vacancies.py   # LLM-екстракція з вакансій
│   │   ├── nlp_resumes.py     # LLM-екстракція з резюме
│   │   ├── currency_converter.py
│   │   ├── analytics_snapshot.py
│   │   ├── skill_normalizer.py
│   │   ├── failure_tracker.py
│   │   ├── rate_limiter.py
│   │   ├── llm_utils.py   # Спільні NLP утиліти
│   │   └── schemas.py     # Pydantic-схеми
│   ├── api/               # REST API для React-застосунку
│   │   ├── main.py        # FastAPI app + CORS
│   │   └── routes/
│   │       ├── health.py
│   │       ├── analytics.py
│   │       └── vacancies.py
│   └── db/
│       └── database.py    # asyncpg пул з'єднань
├── init_db/               # SQL-міграції (виконуються при старті Docker)
│   ├── 00_schemas.sql
│   ├── 01_dictionaries.sql
│   ├── 02_staging.sql
│   ├── 03_core.sql
│   ├── 04_analytics.sql
│   ├── 05_skill_normalization.sql
│   ├── 06_failed_records.sql
│   └── 07_constraints_and_indexes.sql
├── run_pipeline.py        # Точка входу ETL (Prefect flow)
├── docker-compose.yml
├── Dockerfile
└── .env                   # Не комітити! (в .gitignore)
```

---

## Передумови

| Інструмент | Версія |
|------------|--------|
| Python | 3.11+ |
| Docker + Docker Compose | остання стабільна |
| Groq API Key | безкоштовно на [console.groq.com](https://console.groq.com) |

---

## Швидкий старт (Docker — рекомендовано)

### 1. Налаштуй `.env`

Скопіюй приклад і заповни своїми значеннями:

```bash
cp .env.example .env
```

Мінімальний `.env`:

```env
DB_USER=admin
DB_PASSWORD=your_password
DB_NAME=labor_market

PGADMIN_EMAIL=admin@admin.com
PGADMIN_PASSWORD=admin_password

GROQ_API_KEY=gsk_...        # з console.groq.com
```

### 2. Запусти базу даних та API

```bash
docker compose up db api -d
```

- **PostgreSQL** — `localhost:5432`
- **REST API** — `http://localhost:8000`
- **Swagger UI** — `http://localhost:8000/docs`
- **pgAdmin** — `http://localhost:5050` (якщо потрібно)

### 3. Запусти ETL-пайплайн (збір та обробка даних)

```bash
docker compose run --rm etl_worker
```

Пайплайн виконає 4 стадії послідовно:
1. Збір вакансій і резюме з work.ua (~50 сторінок кожен)
2. NLP-обробка через Groq LLM (llama-4-scout) — паралельно
3. Конвертація зарплат у USD (курс НБУ)
4. Побудова аналітичного знімку за поточний день

> Орієнтовний час: 30–90 хв залежно від кількості нових записів (ліміт Groq: 20 RPM combined).

---

## Локальний запуск без Docker

```bash
# 1. Встанови залежності
pip install -r requirements.txt

# 2. Підніми лише базу даних
docker compose up db -d

# 3. Запусти ETL
python run_pipeline.py

# 4. Запусти API
uvicorn src.api.main:app --reload --port 8000
```

---

## API для React-розробника

**Base URL:** `http://localhost:8000`

Повна інтерактивна документація: **`http://localhost:8000/docs`** (Swagger UI)

### Endpoints

#### System

| Метод | URL | Опис |
|-------|-----|------|
| GET | `/health` | Перевірка стану сервера та БД |

#### Analytics

| Метод | URL | Параметри | Опис |
|-------|-----|-----------|------|
| GET | `/api/analytics/overview` | — | Загальна статистика: кількість вакансій/резюме, середні зарплати |
| GET | `/api/analytics/snapshots` | `days=30` | Часовий ряд по дням (для лінійних графіків) |
| GET | `/api/analytics/skills` | `type=vacancy\|resume`, `limit=20`, `category=Hard\|Soft` | Топ навичок по попиту або пропозиції |
| GET | `/api/analytics/skills/gap` | `limit=20` | Gap-аналіз: попит мінус пропозиція по кожній навичці |
| GET | `/api/analytics/locations` | `type=vacancy\|resume`, `limit=10` | Географічний розподіл |
| GET | `/api/analytics/salary-distribution` | `type=vacancy\|resume` | Гістограма зарплат по діапазонах |

#### Vacancies

| Метод | URL | Параметри | Опис |
|-------|-----|-----------|------|
| GET | `/api/vacancies/` | `page`, `limit`, `skill`, `location`, `min_salary_usd`, `experience_years` | Список вакансій з пагінацією та фільтрами |

### Приклади відповідей

**`GET /api/analytics/overview`**
```json
{
  "total_vacancies": 1250,
  "total_resumes": 890,
  "vacancies_with_salary": 420,
  "resumes_with_salary": 310,
  "avg_vacancy_salary_usd": 2800.0,
  "avg_resume_salary_usd": 2200.0
}
```

**`GET /api/analytics/skills?type=vacancy&limit=5`**
```json
[
  {"name": "Python",     "category": "Hard", "count": 342},
  {"name": "JavaScript", "category": "Hard", "count": 298},
  {"name": "React",      "category": "Hard", "count": 187},
  {"name": "SQL",        "category": "Hard", "count": 165},
  {"name": "Docker",     "category": "Hard", "count": 143}
]
```

**`GET /api/analytics/skills/gap?limit=5`**
```json
[
  {"name": "Python", "category": "Hard", "vacancy_count": 342, "resume_count": 210, "gap": 132},
  {"name": "React",  "category": "Hard", "vacancy_count": 187, "resume_count": 95,  "gap": 92}
]
```

**`GET /api/analytics/salary-distribution?type=vacancy`**
```json
[
  {"range_label": "<$500",    "min_usd": null, "max_usd": 500,  "count": 12},
  {"range_label": "$500–1k",  "min_usd": 500,  "max_usd": 1000, "count": 45},
  {"range_label": "$1k–2k",   "min_usd": 1000, "max_usd": 2000, "count": 98},
  {"range_label": "$2k–3k",   "min_usd": 2000, "max_usd": 3000, "count": 134},
  {"range_label": "$3k–5k",   "min_usd": 3000, "max_usd": 5000, "count": 87},
  {"range_label": ">$5k",     "min_usd": 5000, "max_usd": null, "count": 44}
]
```

**`GET /api/vacancies/?skill=Python&limit=2`**
```json
{
  "total": 342,
  "page": 1,
  "limit": 2,
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

Для локальної розробки React API вже налаштований на `http://localhost:3000` і `http://localhost:5173` (Vite).

Якщо порт інший — додай у `.env`:
```env
CORS_ORIGINS=http://localhost:4000,http://localhost:3000
```

---

## Рекомендований стек для React-застосунку

| Категорія | Бібліотека |
|-----------|-----------|
| HTTP-клієнт | `axios` або `fetch` (вбудований) |
| State / кешування | `@tanstack/react-query` (рекомендовано) |
| Графіки | `recharts` або `chart.js` + `react-chartjs-2` |
| UI | `shadcn/ui` або `MUI` |
| Маршрутизація | `react-router-dom` v6 |

Приклад запиту з React Query:

```typescript
import { useQuery } from '@tanstack/react-query';

const API = 'http://localhost:8000';

function useOverview() {
  return useQuery({
    queryKey: ['overview'],
    queryFn: () => fetch(`${API}/api/analytics/overview`).then(r => r.json()),
  });
}

function useTopSkills(type: 'vacancy' | 'resume' = 'vacancy', limit = 20) {
  return useQuery({
    queryKey: ['skills', type, limit],
    queryFn: () =>
      fetch(`${API}/api/analytics/skills?type=${type}&limit=${limit}`).then(r => r.json()),
  });
}
```

---

## Змінні оточення (`.env`)

| Змінна | Обов'язкова | Опис |
|--------|-------------|------|
| `DB_USER` | Так | Користувач PostgreSQL |
| `DB_PASSWORD` | Так | Пароль PostgreSQL |
| `DB_NAME` | Так | Назва бази даних |
| `DB_HOST` | Ні | Хост БД (default: `localhost`) |
| `DB_PORT` | Ні | Порт БД (default: `5432`) |
| `GROQ_API_KEY` | Так | API-ключ Groq (для NLP) |
| `PGADMIN_EMAIL` | Ні | Email для pgAdmin |
| `PGADMIN_PASSWORD` | Ні | Пароль для pgAdmin |
| `CORS_ORIGINS` | Ні | Дозволені origins для React (через кому) |

---

## Схема бази даних

```
staging.raw_vacancies    ──┐
staging.raw_resumes      ──┤─→ [ETL] ─→ core.vacancies ──→ core.vacancy_skills
staging.failed_records     │            core.resumes    ──→ core.resume_skills
                           │                 │
                           │      dictionaries.skills
                           │      dictionaries.skill_synonyms
                           │      dictionaries.locations
                           │      dictionaries.companies
                           │
                           └──→ analytics.daily_market_snapshots
```

---

## Команди

```bash
# Підняти все (БД + API)
docker compose up db api -d

# Запустити ETL один раз
docker compose run --rm etl_worker

# Переглянути логи ETL
docker compose logs etl_worker -f

# Зупинити все
docker compose down

# Перебудувати образ після зміни коду
docker compose build

# Бекфіл аналітики за останні 30 днів
docker compose run --rm etl_worker python src/processor/analytics_snapshot.py backfill 30
```
