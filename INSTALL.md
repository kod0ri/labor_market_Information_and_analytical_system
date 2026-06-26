# Розгортання 503Work (production)

Інструкція з інсталяції та експлуатації self-hosted-розгортання **503Work**
(PostgreSQL + FastAPI + React/nginx + ETL) на сервері засобами Docker Compose.
Усім життєвим циклом керує деплой-CLI [`install.sh`](install.sh).

---

## 1. Склад розгортання

Компоненти, їх джерела та цільові розташування:

| Компонент | Джерело | Цільове розташування |
|---|---|---|
| **Backend (API + ETL)** | `src/`, `run_pipeline.py`, `requirements.txt` → [`Dockerfile`](Dockerfile) | образ → контейнери `labor_market_api`, `etl_pipeline_worker`, `/app` |
| **Frontend** | `frontend/src/` → build `node:20-alpine` (`npm run build`) | `dist/` → `nginx:alpine` `/usr/share/nginx/html`; `nginx.conf` → `/etc/nginx/conf.d/default.conf` |
| **Сервер БД** | образ `postgres:16-alpine` (Docker Hub) | контейнер `postgres_db`; дані → named volume `postgres_data` |
| **Схема БД** | `init_db/00..09_*.sql` (bind-mount) | `/docker-entrypoint-initdb.d` — авто-прогін на порожньому томі |
| **Конфігурація / секрети** | `.env` (з [`.env.example`](.env.example)) | `env_file` усіх сервісів |
| **Оркестрація** | [`docker-compose.yml`](docker-compose.yml) + [`docker-compose.prod.yml`](docker-compose.prod.yml) | каталог деплою (напр. `/data/503work`) |
| **Деплой-CLI** | [`install.sh`](install.sh) | каталог деплою |
| **Резервне копіювання** | [`backup.sh`](backup.sh) | `/data/503work/backup.sh` + cron `0 3 * * *` |
| **Адмінка БД (опційно)** | `dpage/pgadmin4` (профіль `tools`) | контейнер `pgadmin_web`, лише `127.0.0.1` |
| **Мережа** | зовнішня docker-мережа `homelab` | спільна мережа з reverse-proxy / TLS |

PostgreSQL ставиться окремим сервісом: образ тягнеться з Docker Hub, дані ізолюються
в томі `postgres_data`, схема накочується ідемпотентно через
`/docker-entrypoint-initdb.d` (скрипти `init_db/*.sql` — лише на порожньому томі).

---

## 2. Топологія

```
Інтернет ──HTTPS──► reverse-proxy (Caddy/Traefik/nginx, TLS)
                          │   мережа homelab
          ┌───────────────┼────────────────┐
      frontend            api            db (лише внутрішньо)
      nginx:80       FastAPI:8000      postgres:5432 (127.0.0.1)
```

Публічний доступ — лише через reverse-proxy з TLS; СУБД назовні не публікується.

---

## 3. Передумови

- Linux-сервер (x86-64), Docker Engine 24+, Docker **Compose ≥ 2.24.4**.
- Reverse-proxy з TLS у мережі `homelab` (`docker network create homelab`).
- Щонайменше **один** ключ LLM-провайдера (рекомендовано Cerebras + Groq).
- Доменне ім'я — для `CORS_ORIGINS` і TLS-сертифіката.

---

## 4. Конфігурація `.env`

Заповнюються лише «людські» секрети — «машинні» генерує деплой-CLI автоматично.

| Параметр | Тип | Призначення |
|---|---|---|
| `JWT_SECRET` | машинний | Генерується авто (`openssl rand`); застосунок не стартує з порожнім |
| `DB_PASSWORD` | машинний | Генерується авто на першому деплої; не змінюється, якщо том БД існує |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | людський | Обов'язкові; пароль ≥ 8; інакше деплой зупиняється |
| `*_API_KEY` (≥ 1) | людський | Ключ LLM-провайдера; без жодного валідного — стоп |
| `CORS_ORIGINS` | людський | Лише робочий домен (без `localhost` у проді) |
| `COMPOSE_FILE` | конфіг | `docker-compose.yml:docker-compose.prod.yml` — БД не публікується |

---

## 5. Розгортання

```bash
git clone <repo> /data/503work && cd /data/503work
cp .env.example .env          # вписати людські секрети
./install.sh deploy
```

`deploy` виконує етапи послідовно:

| Етап | Дія |
|---|---|
| `check_requirements` | Docker / Compose ≥ 2.24.4, openssl, мережа `homelab` |
| `configure` | Авто-генерація машинних секретів; fail-fast на шаблонних людських |
| `build_and_up` | `docker compose build --pull` + `up -d` (db, api, frontend) |
| `wait_db` / `verify` | Готовність БД + smoke-перевірка (розділ 6) |

Схема БД накочується автоматично з `init_db/*.sql`. ETL-worker має профіль `manual`
і не стартує разом зі стеком — запуск за cron (розділ 7).

---

## 6. Перевірка

```bash
./install.sh verify
```

1. `docker compose config -q` — валідація конфігурації.
2. Очікування статусу `healthy` для `api`.
3. `GET /health` → `200`.
4. Підрахунок таблиць у `staging / core / analytics / auth`.

Очікуваний вивід:
```
✔ Docker + Compose 2.29.2
✔ Мережа 'homelab' існує
✔ Згенеровано JWT_SECRET
✔ Згенеровано пароль БД
✔ Секрети валідні
✔ Стек запущено (db, api, frontend)
✔ PostgreSQL готовий
✔ compose-конфіг валідний
✔ api: healthy
✔ GET /health → 200
✔ Схема БД застосована (N таблиць)
═══ 503Work розгорнуто ═══
```

---

## 7. Експлуатація

### Деплой-CLI
| Команда | Призначення |
|---|---|
| `./install.sh deploy` | Розгортання (ідемпотентне) |
| `./install.sh update` | Оновлення: бекап → rebuild → рестарт → перевірка |
| `./install.sh verify` | Smoke-перевірка |
| `./install.sh backup` | Резервна копія БД |
| `./install.sh status` / `logs [svc]` | Стан / журнали |

### Перший збір даних
```bash
docker compose run --rm etl_worker      # далі — за cron, 1 раз/добу
```

### Оновлення та відкат
```bash
git fetch --tags && git checkout v2.0.0
./install.sh update           # бекап → rebuild → рестарт → перевірка

# відкат:
git checkout <попередній_тег>
./install.sh update
```

### Резервне копіювання
```bash
./install.sh backup                       # разово
# cron: 0 3 * * * /data/503work/install.sh backup >> /data/backups/backup.log 2>&1
```

### Чеклист безпеки прода
- [ ] `JWT_SECRET` і `DB_PASSWORD` — згенеровані, не дефолтні.
- [ ] `COMPOSE_FILE` містить `docker-compose.prod.yml` — БД не публікується назовні.
- [ ] Публічний доступ — лише HTTPS через reverse-proxy; firewall закриває прямі порти.
- [ ] `CORS_ORIGINS` — лише робочий домен, без `localhost`.
- [ ] Налаштований cron на `backup` і `etl_worker`.
- [ ] `pgAdmin` не піднятий у проді (профіль `tools` вимкнено).
