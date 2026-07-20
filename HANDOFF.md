# HANDOFF — Labor Market Information & Analytical System

Документ для наступного інженера/LLM, щоб швидко влитися й продовжити чітко.
Оновлено після ревʼю та рефакторингу (гілка `fix/security-data-correctness-perf`).

---

## 1. Що це за проєкт

Інформаційно-аналітична система ринку праці України (IT-сектор). Пайплайн:

```
Джерела → staging (сирі дані) → LLM-екстракція → core (структуровано) →
   → конвертація валют → аналітичні знімки → REST API → React-дашборд
```

- **Збір:** скрапери/адаптери тягнуть вакансії та резюме у `staging.*`.
- **NLP:** LLM-каскад (безкоштовні провайдери) витягує зі сирого тексту навички,
  зарплату, досвід, рівень англійської → пише у `core.*`.
- **Аналітика:** FastAPI віддає агрегати; React (Vite+TS) їх показує.
- **Адмінка:** JWT-автентифікація, метрики сервера/пайплайну, трекінг візитів.

**Стек:** Python 3.11 (Docker), FastAPI, asyncpg, Pydantic v2, Prefect (оркестрація
ETL), aiohttp, BeautifulSoup/lxml. Frontend: React + Vite + TypeScript + react-query
+ Tailwind, роздача через nginx. Продакшн: docker-compose + Caddy (TLS) у зовнішній
мережі `homelab`.

---

## 2. Джерела даних

| Джерело | Що | Спосіб | Файл |
|---------|----|--------|------|
| **work.ua** | вакансії **і резюме** | HTML-скрапінг (`div.card-hover`) | `src/scrapers/workua_vacancies.py`, `workua_resumes.py` |
| **DOU.ua** | лише вакансії | RSS по 15 IT-категоріях | `src/sources/dou_rss.py` |
| **robota.ua** | лише вакансії | GraphQL API `dracula.robota.ua` (за Cloudflare) | `src/sources/robota_vacancies.py` |
| **НБУ** (`bank.gov.ua`) | курси валют (не job-дані) | JSON API | `src/processor/currency_converter.py` |

Резюме — **тільки work.ua** (robota CVdb за пейволом, у DOU резюме немає).
Вакансії — усі три, усі йдуть одним LLM-шляхом через `staging.raw_vacancies`.

---

## 3. Архітектура / карта коду

**Схеми БД** (`init_db/*.sql`, застосовуються при першому старті Postgres):
- `staging` — `raw_vacancies`, `raw_resumes` (сирий текст+JSON), `failed_records`.
- `dictionaries` — `sources`, `locations`, `companies`, `skills`, `skill_synonyms`.
- `core` — `vacancies`, `resumes`, `vacancy_skills`, `resume_skills` (структуровано).
- `analytics` — `daily_market_snapshots`, `visits`.
- `auth` — `users` (створюється також у `src/auth/bootstrap.py` для наповнених БД).

**Бекенд (`src/`):**
- `api/main.py` — збірка FastAPI, CORS, lifespan (fail-fast на `JWT_SECRET`, ініт пулу,
  сид адміна, схеми). Роутери: `health`, `tracking`, `auth`, `analytics`, `admin`, `client`.
- `api/routes/analytics.py` — публічні аналітичні ендпоінти (overview, skills, gap,
  locations, salary-distribution, activity тощо). SQL з f-string, але інтерполюються
  ЛИШЕ значення зі словників за `Literal`-параметрами — інʼєкція неможлива.
- `api/ratelimit.py` — sliding-window rate limiter по IP (in-memory, один процес).
- `auth/` — `security.py` (pbkdf2 + JWT HS256), `router.py` (login/me), `repository.py`,
  `bootstrap.py`. **Усі акаунти — адміни**, реєстрації через UI немає (лише
  `scripts/create_user.py` або сид з env).
- `admin/` — SOLID-структура: `router → facade → services` (Stats/Failure/Pipeline/System).
- `client/` — пошук вакансій/резюме: `router → facade → factory → strategy(filters) →
  repository`. Патерни GoF навмисне (це навчальний проєкт — не «спрощуй» їх без потреби).
- `processor/` — `nlp_pipeline.py` (спільний LLM-оркестратор), `nlp_vacancies.py`,
  `nlp_resumes.py`, `llm_cascade.py`, `rate_limiter.py`, `llm_utils.py`, `schemas.py`,
  `skill_normalizer.py`, `currency_converter.py`, `analytics_snapshot.py`, `failure_tracker.py`.
- `tracking/` — анонімний облік відвідувачів (`visitor_id` з localStorage, без IP/PII).
- `db/database.py` — `AsyncDatabasePool` (asyncpg pool, singleton).

**LLM-каскад** (`processor/llm_cascade.py`): послідовний fallback по безкоштовних
OpenAI-сумісних провайдерах **Cerebras → Groq → Gemini → Mistral**. Активуються лише ті,
для кого заданий API-ключ у `.env`. Кожен має власний `DailyBudget` (TPD/RPD) і
token-bucket rate limiter. Порядок можна перевизначити `LLM_PROVIDER_ORDER`.

**ETL-оркестрація** (`run_pipeline.py`, Prefect flow):
1. паралельно: work.ua вакансії+резюме, DOU, robota → staging;
2. паралельно: NLP вакансій + резюме → core;
3. конвертація валют → USD;
4. аналітичний знімок.
Запуск: `docker compose run --rm etl_worker` (профіль `manual`, не стартує зі стеком).

---

## 4. Поточний стан

- **Гілка:** `fix/security-data-correctness-perf` (запушена в `origin`, від `master`).
  PR ще не створений.
- **Тести:** 61, усі зелені. `pytest` (asyncio_mode=auto). Юніт-рівень, без БД/мережі.
- **Автор комітів:** `kod0ri <mrdantezx@gmail.com>` (локальний git-конфіг репо).
- **Незакомічене:** цей `HANDOFF.md` (створений поза ревʼю).

### Коміти на гілці (від найновішого)
```
a4e2c22 refactor(processor,scrapers): extract shared LLM orchestrator and card parser
03873b3 perf(client): fetch search total via COUNT(*) OVER() in one query
7c80f2f fix(processor): correct resume snapshot counting and currency fallback
7afc96f fix(security): harden client IP resolution, session revocation and port exposure
```

---

## 5. Що було зроблено цієї сесії (ревʼю + 5 хвиль)

Провів повний ревʼю (безпека, коректність, продуктивність, якість) і виправив:

**Безпека (`7afc96f`):**
1. *Обхід rate-limit логіну.* `get_client_ip` довіряв `Cf-Connecting-Ip` і **лівому**
   елементу `X-Forwarded-For` — обидва підконтрольні клієнту → підробка ключа ліміту
   й безлімітний брутфорс `/api/auth/login`. Тепер IP береться з **хвоста** XFF за
   `TRUSTED_PROXY_HOPS`; `cf-connecting-ip` ігнорується без `TRUST_CF_CONNECTING_IP=1`;
   nginx явно чистить вхідний `CF-Connecting-IP`.
2. *Порт фронтенда.* `docker-compose.yml` мав `5173:80` на `0.0.0.0` (усі інтерфейси)
   — виставлено `127.0.0.1:5173:80`, як усі інші сервіси.
3. *Відкликання сесії.* `get_current_user` за наявності `uid` у токені пропускав
   перевірку `is_active` → деактивований акаунт жив до 24 год. Тепер `is_active`
   перевіряється на кожному запиті (`touch_and_get_active`, один round-trip).

**Коректність даних (`7c80f2f`):**
4. *Подвійний облік резюме.* `analytics_snapshot` писав добові `total_resumes` у
   КОЖЕН рядок-категорію вакансій → множення при сумуванні. Резюме тепер окремим
   рядком `category='ALL'`.
5. *Тихий фолбек курсів.* При збої НБУ фабрикувався курс `43/40`, запис конвертувався
   і БІЛЬШЕ не переоцінювався (partial-index). Тепер при збої/відсутності USD прогін
   **пропускається**, `*_usd_eq` лишається NULL → ретрай наступного разу.

**Продуктивність (`03873b3`):**
6. Пошук робив 2 послідовні запити (`find_many` + `count`). Тепер `COUNT(*) OVER()`
   рахує total у тому ж запиті; окремий `count()` — лише fallback для порожньої
   сторінки. `find_many` тепер повертає `(items, total)`.

**Рефакторинг (`a4e2c22`):**
7. Дедуплікація: `parse_card_links()` у `scrapers/utils.py` (обидва work.ua-скрапери);
   `run_llm_record()` у новому `processor/nlp_pipeline.py` — спільний каркас retry/
   JSON-екстракції/обробки помилок; `nlp_vacancies`/`nlp_resumes` дають лише
   `messages` + схему + `persist`-колбек. Поведінка не змінена.

**Тести (розкидані по хвилях):** `test_security`, `test_schemas`, `test_client_ip`,
`test_client_repository`, `test_client_facade`, `test_currency_converter`,
`test_scraper_utils`, `test_nlp_pipeline` (13 → 61).

---

## 6. ⚠️ Що НЕ вдалося / обмеження (читати обовʼязково)

- **Живий ETL НЕ перевірявся.** У сесії **Docker був недоступний** (`permission denied`
  до `/var/run/docker.sock`). Тому:
  - весь стек не піднімався, БД-залежні шляхи не ганялися end-to-end;
  - рефакторинг NLP (`run_llm_record` + persist-колбеки) верифіковано **лише статично**:
    61 юніт-тест (з фейками, без БД), pyflakes, import-check. Логіку збережено
    рядок-у-рядок, але **перший реальний прогін `docker compose run --rm etl_worker`
    має зробити людина** — це підтвердить persist на справжній схемі.
  - фікси nginx/compose не перевірені запуском контейнерів (лише читанням конфігів).
- **Тести їхали на Python 3.14** у dev-середовищі, а прод — 3.11 (Dockerfile). Різниці
  не помічено, але майте на увазі.
- **`TRUSTED_PROXY_HOPS` треба виставити під реальну топологію.** Дефолт `1` (лише nginx).
  Якщо ланцюг `Caddy → nginx → api` — постав `2` у `.env`, інакше всі клієнти
  поділять один ключ ліміту (Caddy IP). Точну топологію я НЕ підтвердив — уточни.

---

## 7. Відомі невиправлені / свідомо лишені питання

- **`/api/analytics/*` та `/api/client/*` — повністю публічні** (без auth). Схоже, за
  задумом (публічний дашборд), auth лише на `/api/admin`. Підтвердити як рішення.
- **`VisitRepository.metrics` робить `DELETE` на КОЖНЕ читання** admin `/system`
  (frontend полить кожні 30 с). Дрібна write-амплітуда; можна зробити throttled/
  імовірнісним прибиранням. Не критично.
- **Rate limiter — in-memory, один процес.** За кількох воркерів/реплік ліміт стане
  локальним. Для масштабування — спільний стор (Redis).
- **Патерни GoF у `client/` та SOLID у `admin/` — навмисні** (навчальний проєкт). НЕ
  «спрощуй» їх під виглядом рефакторингу без явного запиту.

---

## 8. Наступні етапи (пропозиція, за пріоритетом)

1. **Верифікувати наживо:** підняти стек (`docker compose up -d`), прогнати
   `docker compose run --rm etl_worker`, перевірити логін → дашборд → пошук → admin.
   Особливо — persist у `nlp_*` після рефакторингу.
2. **Створити PR** з гілки й змержити після перевірки.
3. Виставити `TRUSTED_PROXY_HOPS` під реальний проксі-ланцюг.
4. (Опційно) throttled cleanup у `VisitRepository.metrics`.
5. (Опційно) інтеграційні тести на репозиторії з тимчасовою Postgres (testcontainers).
6. (Опційно) кеш для важких аналітичних агрегатів, якщо навантаження зросте.

---

## 9. Швидкий старт для розробки

```bash
# 1. venv + залежності
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt          # включає requirements.txt

# 2. .env (ОБОВʼЯЗКОВО)
cp .env.example .env
#   JWT_SECRET       — openssl rand -hex 32 (без нього застосунок НЕ стартує)
#   DB_USER/DB_PASSWORD/DB_NAME
#   ADMIN_USERNAME/ADMIN_PASSWORD — сид першого адміна
#   хоч один з CEREBRAS/GROQ/GEMINI/MISTRAL_API_KEY — інакше NLP не працює
#   TRUSTED_PROXY_HOPS — під свій проксі-ланцюг

# 3. тести
pytest                                        # 61, asyncio_mode=auto

# 4. увесь стек (потрібен доступ до Docker)
docker compose up -d                          # db + api + frontend
docker compose run --rm etl_worker            # разовий прогін ETL (профіль manual)
docker compose --profile tools up -d pgadmin  # опційно, pgAdmin на 127.0.0.1:5050

# 5. створити акаунт
docker compose exec api python -m scripts.create_user --username NAME
```

**Порти (локально):** api `127.0.0.1:8000`, frontend `127.0.0.1:5173`, db `127.0.0.1:5432`.
Swagger: `http://127.0.0.1:8000/docs`.

---

## 10. Підводні камені

- `JWT_SECRET` fail-fast: порожній/дефолтний/<16 символів → застосунок не стартує (навмисно).
- `create_pool` вимагає `DB_USER/DB_PASSWORD/DB_NAME` в env (KeyError інакше).
- LLM-каскад «замовкає» без жодного API-ключа — `complete()` кине `RuntimeError`.
- `currency_converter` конвертує лише записи з `*_usd_eq IS NULL` (partial-index). Раз
  сконвертований запис більше не чіпається — тому фікс #5 і важливий.
- `nlp_*` при вичерпаному денному бюджеті провайдерів лишає записи в staging на
  наступний прогін (не фіксує як провал). `failed_records` — лише справжні помилки/галюцинації.
- Prefect у `run_pipeline.py`: задачі викликаються напряму в одному event loop (не
  `.submit()`), інакше `asyncpg.Pool` з іншого loop → RuntimeError.
- Frontend роздається nginx-ом (`frontend/nginx.conf`), який проксіює `/api` та `/health`
  на `labor_market_api:8000` у docker-мережі.
