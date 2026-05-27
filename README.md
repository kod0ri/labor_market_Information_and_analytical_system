<div align="center">

# 503Work

### Аналітика українського IT-ринку праці

*ETL-пайплайн і дашборд, що перетворює сирі дані з work.ua на готову аналітику попиту, зарплат і географії.*

![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

</div>

---

## Що це

**503Work** збирає вакансії та резюме з [work.ua](https://www.work.ua), витягує навички/зарплати/досвід через LLM (Groq `llama-4-scout-17b`), конвертує оплату в USD за курсом НБУ і подає все через REST API та React-дашборд.

---

## Швидкий старт

```bash
git clone <repo>
cd project
cp .env.example .env      # заповни GROQ_API_KEY, DB_PASSWORD та ін.

docker compose up -d --build
```

Відкрий [http://localhost:5173](http://localhost:5173) — готово.

> Перший запуск ETL-пайплайну (збір + LLM-обробка) займає 30–90 хв:
> ```bash
> docker compose run --rm etl_worker
> ```

---

## Архітектура

```
┌──────────┐    ┌───────────────┐    ┌──────────┐    ┌────────────┐
│ work.ua  │───▶│ src/scrapers  │───▶│   Groq   │───▶│ PostgreSQL │
│  (HTML)  │    │ aiohttp + bs4 │    │ llama-4  │    │  core.*    │
└──────────┘    └───────────────┘    └──────────┘    └─────┬──────┘
                                                           │
                        ┌──────────────────────────────────┘
                        ▼
                ┌──────────────┐         ┌──────────────────────┐
                │  FastAPI     │◀────────│  nginx               │
                │  :8000       │   JSON  │  :5173               │
                │  src/api     │         │  React + Vite        │
                │  src/admin   │         │  recharts            │
                │  src/client  │         └──────────────────────┘
                │  src/auth    │
                └──────────────┘
                       ▲
               ┌───────┴──────┐
               │   Prefect    │
               │   flow       │  scrape → NLP → currency → snapshot
               └──────────────┘
```

---

## Структура проекту

```
project/
├── docker-compose.yml          # db, pgadmin, etl_worker, api, frontend
├── Dockerfile                  # образ для api та etl_worker
├── requirements.txt
├── run_pipeline.py             # точка входу Prefect-пайплайну
│
├── src/
│   ├── scrapers/               # асинхронний збір з work.ua
│   │   ├── workua_vacancies.py
│   │   └── workua_resumes.py
│   ├── processor/              # LLM-обробка, нормалізація, валюта
│   │   ├── nlp_vacancies.py
│   │   ├── nlp_resumes.py
│   │   ├── skill_normalizer.py
│   │   ├── currency_converter.py
│   │   ├── analytics_snapshot.py
│   │   └── failure_tracker.py
│   ├── db/                     # пул asyncpg-з'єднань
│   ├── api/                    # FastAPI app + аналітичні endpoints
│   │   └── routes/
│   │       ├── analytics.py    # 11 аналітичних endpoints
│   │       └── health.py
│   ├── admin/                  # адмін-підсистема (SOLID)
│   │   ├── interfaces.py       # Protocol-інтерфейси (ISP/DIP)
│   │   ├── services.py         # StatsService, FailureService, PipelineService (SRP)
│   │   ├── facade.py           # AdminFacade singleton
│   │   └── router.py           # /api/admin/* (захищені JWT)
│   ├── client/                 # клієнтська підсистема (GoF)
│   │   ├── filters.py          # Strategy-фільтри
│   │   ├── factory.py          # FilterStrategyFactory
│   │   ├── repository.py       # VacancyRepository, ResumeRepository
│   │   ├── facade.py           # MarketDataFacade singleton
│   │   └── router.py           # /api/client/*
│   └── auth/                   # JWT-автентифікація
│       └── router.py           # /api/auth/login, /api/auth/me
│
├── frontend/
│   ├── Dockerfile              # multi-stage: node build → nginx
│   ├── nginx.conf              # роздача статики + proxy /api → backend
│   ├── vite.config.ts          # proxy для локальної розробки
│   └── src/
│       ├── auth/               # AuthContext (токен у localStorage)
│       ├── api/                # client.ts, hooks.ts, types.ts
│       ├── components/         # UI-компоненти + charts/
│       └── pages/
│           ├── DashboardPage   # KPI + огляд
│           ├── SkillsPage      # топ навичок + gap-аналіз
│           ├── SalaryPage      # розподіл зарплат + досвід
│           ├── GeographyPage   # географія
│           ├── ClientSearchPage # пошук вакансій/резюме з фільтрами
│           ├── AdminPage       # адмін-панель (потребує входу)
│           └── LoginPage       # форма входу
│
└── init_db/                    # SQL-міграції (00–07)
```

---

## REST API

```
GET  /health                              # стан API + БД

# Аналітика
GET  /api/analytics/overview              # KPI ринку
GET  /api/analytics/activity              # нові оголошення по бакетах
GET  /api/analytics/experience-timeline   # junior/middle/senior у часі
GET  /api/analytics/skills                # топ навичок
GET  /api/analytics/skills/gap            # gap-аналіз
GET  /api/analytics/salary-distribution   # гістограма ЗП
GET  /api/analytics/experience-levels     # ЗП по рівнях досвіду
GET  /api/analytics/english-levels        # рівні англійської
GET  /api/analytics/locations             # географія
GET  /api/analytics/companies             # топ роботодавців

# Клієнтська підсистема — пошук з фільтрами
GET  /api/client/vacancies/search         # skill, location, salary, english_level
GET  /api/client/resumes/search           # skill, location, salary, experience_min

# Адмін-підсистема — потребує Bearer-токена
POST /api/auth/login                      # → { access_token }
GET  /api/auth/me
GET  /api/admin/stats                     # статистика БД
GET  /api/admin/pipeline/status           # черга + помилки
GET  /api/admin/failures                  # список нерозв'язаних помилок
PATCH /api/admin/failures/{id}/resolve    # позначити як вирішену
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Змінні середовища

Скопіюй `.env.example` → `.env` і заповни:

| Змінна | Опис |
|--------|------|
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | PostgreSQL |
| `GROQ_API_KEY` | API-ключ Groq |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Логін/пароль адмін-панелі (default: `admin`/`admin`) |
| `JWT_SECRET` | Секрет для підпису JWT (змінити в prod) |
| `CORS_ORIGINS` | Дозволені origins для браузера |

---

## Docker-сервіси

| Сервіс | Образ | Порт |
|--------|-------|------|
| `db` | postgres:16-alpine | 5432 |
| `pgadmin` | dpage/pgadmin4 | 5050 |
| `api` | ./Dockerfile | 8000 |
| `etl_worker` | ./Dockerfile | — |
| `frontend` | ./frontend/Dockerfile | 5173 |

---

## Локальна розробка (без Docker)

```bash
# Backend
conda activate labor_market   # або будь-який venv з requirements.txt
uvicorn src.api.main:app --reload --port 8000

# Frontend (Vite проксує /api → localhost:8000 автоматично)
cd frontend && npm install && npm run dev
```

---

## Документація

| Файл | Зміст |
|------|-------|
| [docs/DOCS.md](docs/DOCS.md) | Технічний довідник: схема БД, env, troubleshooting |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Production-деплой: nginx, Let's Encrypt, systemd |

---

<div align="center">

Дані: [work.ua](https://www.work.ua) · LLM: [Groq](https://groq.com)

</div>
