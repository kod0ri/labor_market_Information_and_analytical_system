# 503Work — Інструкція з деплою

Покроковий гайд для розгортання системи на production-сервері. Найпрактичніший шлях — VPS + Docker Compose + nginx + Let's Encrypt.

---

## 1. Передумови

### Сервер

| Параметр | Мінімум | Рекомендовано |
|----------|---------|----------------|
| CPU | 2 vCPU | 2–4 vCPU |
| RAM | 2 ГБ | 4 ГБ |
| Диск | 20 ГБ SSD | 40 ГБ SSD |
| ОС | Ubuntu 22.04 / Debian 12 | Ubuntu 24.04 LTS |

Підійдуть Hetzner Cloud (CX22 €4/міс), DigitalOcean ($6/міс), Contabo (€4/міс).

### Що ще знадобиться

- Зареєстрований домен (наприклад, `503work.example.com`)
- DNS A-запис вашого домену на IP сервера
- Робочий `GROQ_API_KEY` з [console.groq.com](https://console.groq.com)
- SSH-доступ до сервера як `root` або користувач з `sudo`

---

## 2. Підготовка сервера

### 2.1. Базові пакети

```bash
ssh root@your-server-ip
apt update && apt upgrade -y
apt install -y curl git ufw fail2ban
```

### 2.2. Firewall

```bash
ufw allow OpenSSH
ufw allow 80/tcp     # HTTP (для Let's Encrypt)
ufw allow 443/tcp    # HTTPS
ufw --force enable
```

> **Не відкривай** `5432`, `8000`, `5173`, `5050` — ці порти мають бути лише локально (через nginx).

### 2.3. Docker + Docker Compose

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker compose version   # перевірка
```

### 2.4. Окремий користувач (рекомендовано)

```bash
adduser deploy
usermod -aG docker,sudo deploy
su - deploy
```

Далі всі команди — від `deploy`.

---

## 3. Розгортання застосунку

### 3.1. Клонувати репозиторій

```bash
cd ~
git clone https://github.com/<your-org>/<repo>.git 503work
cd 503work
```

### 3.2. Налаштувати `.env` для production

```bash
cp .env.example .env
nano .env
```

Production-варіант `.env`:

```env
# База даних — НЕ ВИКОРИСТОВУЙ DEFAULT ПАРОЛІ
DB_USER=labor_market
DB_PASSWORD=<довгий-випадковий-пароль>     # openssl rand -base64 32
DB_NAME=core_postgres
DB_HOST=db
DB_PORT=5432

# Groq для NLP
GROQ_API_KEY=gsk_...

# pgAdmin — взагалі не запускай у production, або сильний пароль
PGADMIN_EMAIL=admin@yourdomain.com
PGADMIN_PASSWORD=<сильний-пароль>

# CORS — лише ваш фронтенд-домен
CORS_ORIGINS=https://503work.example.com
```

> Згенерувати пароль:
> ```bash
> openssl rand -base64 32
> ```

### 3.3. Запустити БД + API

```bash
docker compose up db api -d
docker compose ps           # обидва healthy?
```

Перевірити локально на сервері:

```bash
curl http://localhost:8000/health
# {"status": "ok", "database": "connected"}
```

### 3.4. Запустити перший ETL

```bash
docker compose run --rm etl_worker
```

⏱ ~30–90 хв. Можна запустити у фоні та слідкувати:

```bash
docker compose run --rm -d etl_worker
docker compose logs etl_worker -f
```

### 3.5. Зібрати фронтенд

```bash
# Встанови Node.js (якщо ще не встановлено)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs

cd frontend
echo "VITE_API_BASE_URL=https://503work.example.com/api" > .env
npm ci
npm run build
```

Результат: `frontend/dist/` — статичні файли для nginx.

> Альтернатива: збирай локально та копіюй `dist/` на сервер через `rsync`. Це швидше та не вимагає Node.js на VPS.

---

## 4. Nginx як reverse proxy + статичний хостинг

### 4.1. Встановити

```bash
sudo apt install -y nginx
```

### 4.2. Конфіг

```bash
sudo nano /etc/nginx/sites-available/503work
```

```nginx
# /etc/nginx/sites-available/503work

server {
    listen 80;
    server_name 503work.example.com;

    # Frontend — статика з frontend/dist
    root /home/deploy/503work/frontend/dist;
    index index.html;

    # SPA fallback — будь-який роут віддає index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API — проксі на FastAPI у Docker
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # Health endpoint
    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    # Swagger UI (опційно — можна закрити)
    location = /docs {
        proxy_pass http://127.0.0.1:8000/docs;
    }
    location = /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
    }

    # Кеш статичних ассетів
    location ~* \.(js|css|svg|woff2?|png|jpg|webp)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Gzip
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;

    # Security headers
    add_header X-Content-Type-Options "nosniff";
    add_header X-Frame-Options "SAMEORIGIN";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
}
```

```bash
sudo ln -s /etc/nginx/sites-available/503work /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default     # якщо є
sudo nginx -t                                 # перевірити синтаксис
sudo systemctl reload nginx
```

### 4.3. Дати nginx доступ до frontend/dist

```bash
sudo chmod o+x /home/deploy
sudo chmod -R o+rX /home/deploy/503work/frontend/dist
```

Перевір: `curl http://503work.example.com` має повернути HTML фронтенда.

---

## 5. SSL з Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d 503work.example.com
```

Certbot сам:
1. Підтвердить домен
2. Отримає сертифікат
3. Допише `listen 443 ssl;`, шляхи до сертифікатів у конфіг nginx
4. Налаштує auto-redirect HTTP → HTTPS

Авто-оновлення вже працює (systemd timer `certbot.timer`). Перевір:

```bash
sudo certbot renew --dry-run
```

> Після SSL не забудь оновити `CORS_ORIGINS=https://503work.example.com` у `.env` та зробити `docker compose restart api`.

---

## 6. Регулярний ETL

ETL запускається вручну — для production треба автоматизувати. Найпростіше — `cron`.

### 6.1. Cron щодня о 03:00

```bash
crontab -e
```

```cron
# Щодня о 03:00 — повний ETL
0 3 * * * cd /home/deploy/503work && /usr/bin/docker compose run --rm etl_worker >> /var/log/503work-etl.log 2>&1
```

Створи лог-файл і дай права:

```bash
sudo touch /var/log/503work-etl.log
sudo chown deploy /var/log/503work-etl.log
```

### 6.2. Або через systemd timer (краще для моніторингу)

```bash
sudo nano /etc/systemd/system/503work-etl.service
```

```ini
[Unit]
Description=503Work ETL — daily scrape and NLP
After=docker.service

[Service]
Type=oneshot
User=deploy
WorkingDirectory=/home/deploy/503work
ExecStart=/usr/bin/docker compose run --rm etl_worker
```

```bash
sudo nano /etc/systemd/system/503work-etl.timer
```

```ini
[Unit]
Description=Run 503Work ETL daily

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now 503work-etl.timer
sudo systemctl list-timers 503work-etl
```

Перегляд логів:

```bash
sudo journalctl -u 503work-etl -e
```

---

## 7. Бекапи БД

### 7.1. Щоденний dump

```bash
mkdir -p ~/backups
nano ~/backup-db.sh
```

```bash
#!/usr/bin/env bash
set -euo pipefail
TIMESTAMP=$(date +%F-%H%M)
DEST=~/backups
docker exec postgres_db pg_dump -U labor_market -d core_postgres -Fc \
  > "$DEST/core_postgres-$TIMESTAMP.dump"

# Залишити останні 14 днів
find "$DEST" -name 'core_postgres-*.dump' -mtime +14 -delete
```

```bash
chmod +x ~/backup-db.sh
crontab -e
```

```cron
# Бекап щодня о 02:30 (до ETL)
30 2 * * * /home/deploy/backup-db.sh >> /var/log/503work-backup.log 2>&1
```

### 7.2. Відновлення

```bash
docker exec -i postgres_db pg_restore -U labor_market -d core_postgres --clean \
  < ~/backups/core_postgres-2026-05-19-0230.dump
```

### 7.3. Off-site (рекомендовано)

Закидати дампи на S3 / Backblaze B2 / rsync.net через `rclone` чи `restic`. Локальні бекапи на тому ж диску — це не бекапи.

---

## 8. Моніторинг та логи

### 8.1. Логи

```bash
docker compose logs api -f --tail=200
docker compose logs db -f --tail=200
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
sudo journalctl -u 503work-etl -e
```

### 8.2. Health-check

Простий cron, який пінгує `/health` і шле в Telegram при недоступності:

```bash
nano ~/healthcheck.sh
```

```bash
#!/usr/bin/env bash
URL="https://503work.example.com/health"
TG_TOKEN="<bot-token>"
TG_CHAT="<chat-id>"

if ! curl -fsS "$URL" -o /dev/null; then
  curl -s -X POST "https://api.telegram.org/bot$TG_TOKEN/sendMessage" \
    -d "chat_id=$TG_CHAT" \
    -d "text=⚠ 503Work API недоступний: $URL"
fi
```

```cron
*/5 * * * * /home/deploy/healthcheck.sh
```

### 8.3. Краще рішення — Uptime Kuma

Безкоштовний self-hosted моніторинг:

```bash
docker run -d --restart=always -p 3001:3001 \
  -v uptime-kuma:/app/data --name uptime-kuma louislam/uptime-kuma:1
```

Прокинь його через nginx на піддомен `status.503work.example.com`.

---

## 9. Оновлення коду

### 9.1. Бекенд + ETL

```bash
cd ~/503work
git pull
docker compose build api etl_worker
docker compose up -d api      # тільки API; ETL запуститься з нової версії при наступному cron
```

### 9.2. Фронтенд

```bash
cd ~/503work/frontend
git pull          # якщо не зробив у п. 9.1
npm ci            # тільки якщо змінився package-lock.json
npm run build
sudo systemctl reload nginx
```

### 9.3. Зміна схеми БД

Якщо в `init_db/` додали міграцію — **вона не виконається на існуючій БД**. Виконай SQL вручну:

```bash
docker exec -i postgres_db psql -U labor_market -d core_postgres < init_db/08_new_migration.sql
```

---

## 10. Security checklist

- [ ] Сильні паролі для `DB_PASSWORD` та `PGADMIN_PASSWORD` (32+ символи)
- [ ] `CORS_ORIGINS` обмежений лише production-доменом
- [ ] `5432`, `8000`, `5050` НЕ відкриті в інтернет (`ufw status`)
- [ ] SSH тільки по ключу (`PasswordAuthentication no` у `/etc/ssh/sshd_config`)
- [ ] `fail2ban` активний (`systemctl status fail2ban`)
- [ ] `unattended-upgrades` для security-патчів ОС:
  ```bash
  sudo apt install unattended-upgrades
  sudo dpkg-reconfigure -plow unattended-upgrades
  ```
- [ ] Бекапи перевірені відновленням на staging
- [ ] Swagger UI закритий або винесений під basic-auth (видали locations `/docs` та `/openapi.json` з nginx-конфігу)
- [ ] pgAdmin не запущений у production (не додавай `pgadmin` у `docker compose up`)

---

## 11. Альтернативні варіанти деплою

Якщо не хочеш керувати VPS:

### Backend на Railway / Fly.io

| Сервіс | Особливості |
|--------|-------------|
| [Railway](https://railway.app) | $5/міс кредитів, простий `railway up` |
| [Fly.io](https://fly.io) | Безкоштовний рівень для невеликих застосунків |
| [Render](https://render.com) | Має managed PostgreSQL |

Усі підтримують Docker — `Dockerfile` уже готовий. Постав env-змінні через UI.

### Frontend — статика

| Сервіс | Особливості |
|--------|-------------|
| [Vercel](https://vercel.com) | Авто-білд з GitHub, безкоштовно |
| [Netlify](https://netlify.com) | Те саме |
| [Cloudflare Pages](https://pages.cloudflare.com) | Безкоштовно, найшвидший CDN |

Build command: `npm run build`. Output: `dist`. Env: `VITE_API_BASE_URL=https://<backend>/api`.

### Managed PostgreSQL

- [Neon](https://neon.tech) — безкоштовний tier, serverless
- [Supabase](https://supabase.com) — додає auth+REST зверху
- [DigitalOcean Managed PG](https://www.digitalocean.com/products/managed-databases-postgresql)

> При використанні managed PG — заміни `DB_HOST=db` на URL з провайдера, прибери сервіс `db` з `docker-compose.yml` та не забудь дозволити IP backend-сервера у firewall БД.

---

## 12. Troubleshooting

| Симптом | Причина | Рішення |
|---------|---------|---------|
| `502 Bad Gateway` | API не запущений | `docker compose ps`, `docker compose up -d api` |
| Фронт є, API повертає CORS-помилку | `CORS_ORIGINS` не оновлено | Додай прод-домен у `.env`, `docker compose restart api` |
| Графіки порожні | ETL не запускався | `docker compose run --rm etl_worker` |
| `avg_*_salary_usd: null` | currency_converter не пройшов | `docker compose run --rm etl_worker python src/processor/currency_converter.py` |
| 429 від Groq у логах ETL | Rate limit | Норма, скрипт сам ретраїть |
| `disk full` через `postgres_data` | Не очищено staging | `TRUNCATE staging.raw_*` у SQL після успішного запуску NLP |
| Let's Encrypt не валідується | Порт 80 закритий або DNS не зрезолвлено | `ufw allow 80/tcp`, `dig 503work.example.com` |
| SPA-роути 404 на refresh | Немає `try_files ... /index.html` у nginx | Перевір [п. 4.2](#42-конфіг) |

---

## 13. Швидка пам'ятка

```bash
# Старт
docker compose up db api -d

# Логи
docker compose logs api -f

# Перебудувати backend після git pull
docker compose build api && docker compose up -d api

# Перебудувати фронтенд після git pull
cd frontend && npm ci && npm run build && sudo systemctl reload nginx

# Ручний ETL
docker compose run --rm etl_worker

# Бекап БД
docker exec postgres_db pg_dump -U labor_market core_postgres -Fc > backup.dump

# Підключитись до БД
docker exec -it postgres_db psql -U labor_market -d core_postgres

# Зупинити все
docker compose down

# Зупинити + видалити дані (НЕЗВОРОТНО)
docker compose down -v
```
