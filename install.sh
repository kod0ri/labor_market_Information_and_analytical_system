#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# install.sh — деплой-інструмент 503Work (production-grade self-hosted).
#
# Один CLI на весь життєвий цикл розгортання на сервері замовника:
#
#   ./install.sh deploy     перший/повторний розгортання (за замовчуванням)
#   ./install.sh update     оновлення версії (rebuild + рестарт + перевірка)
#   ./install.sh verify     smoke-перевірка живого стека
#   ./install.sh backup     резервна копія БД (обгортка backup.sh)
#   ./install.sh status     стан сервісів
#   ./install.sh logs [svc] журнали (Ctrl+C — вийти)
#   ./install.sh help
#
# Принципи production:
#   • fail-fast — не стартує з плейсхолдерами/слабкими секретами у .env;
#   • машинні секрети (JWT_SECRET, пароль БД) генеруються автоматично;
#   • людські секрети (ключі LLM, пароль адміна) — обов'язкові, інакше стоп;
#   • ідемпотентність — deploy/update безпечно повторювати;
#   • прод-оверрайд compose (БД не публікується назовні).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

readonly ENV_FILE=".env"
readonly EXAMPLE_FILE=".env.example"
readonly PROXY_NET="homelab"          # зовнішня мережа reverse-proxy (compose: external)
readonly API_HEALTH="http://127.0.0.1:8000/health"
COMPOSE="docker compose"

# ── лог ──────────────────────────────────────────────────────────────────────
if [ -t 1 ]; then C_OK=$'\033[32m'; C_ERR=$'\033[31m'; C_WRN=$'\033[33m'; C_INF=$'\033[36m'; C_N=$'\033[0m'
else C_OK=''; C_ERR=''; C_WRN=''; C_INF=''; C_N=''; fi
log()  { printf '%s▸ %s%s\n' "$C_INF" "$*" "$C_N"; }
ok()   { printf '%s✔ %s%s\n' "$C_OK" "$*" "$C_N"; }
warn() { printf '%s⚠ %s%s\n' "$C_WRN" "$*" "$C_N" >&2; }
die()  { printf '%s✘ %s%s\n' "$C_ERR" "$*" "$C_N" >&2; exit 1; }
trap 'die "Збій на рядку $LINENO. Деплой перервано."' ERR

# ── утиліти .env ─────────────────────────────────────────────────────────────
get_env() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -n1 | cut -d= -f2- | sed 's/[[:space:]]*$//'; }

set_env() { # KEY VALUE   (значення — лише hex/безпечні символи)
  local key="$1" val="$2"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}

is_placeholder() { # VALUE → 0, якщо порожнє/шаблонне
  local v="${1:-}"
  [[ -z "$v" || "$v" == *REPLACE_WITH* || "$v" == *REPLACE* \
     || "$v" == "your_strong_password" || "$v" == "your_pgadmin_password" \
     || "$v" == "changeme" ]]
}

gen_secret() { openssl rand -hex "${1:-32}"; }   # лише [0-9a-f] — безпечно для sed/shell

db_volume_exists() { docker volume ls --format '{{.Name}}' 2>/dev/null | grep -q 'postgres_data$'; }

require_compose_prod() {
  local cf; cf="$(get_env COMPOSE_FILE)"
  case "$cf" in
    *docker-compose.prod.yml*) : ;;
    *) warn "COMPOSE_FILE без prod-оверрайду — БД може публікуватися назовні. Рекомендовано: COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml" ;;
  esac
}

# ── 1. вимоги до оточення ────────────────────────────────────────────────────
check_requirements() {
  log "Перевірка вимог оточення"
  command -v docker >/dev/null   || die "Docker не встановлено (потрібен Engine 24+)."
  docker info >/dev/null 2>&1    || die "Docker-демон недоступний (права/сервіс)."
  $COMPOSE version >/dev/null 2>&1 || die "Docker Compose v2 не знайдено."
  command -v openssl >/dev/null  || die "Потрібен openssl (генерація секретів)."

  local cv; cv="$($COMPOSE version --short 2>/dev/null || echo 0)"
  printf '%s\n%s\n' "2.24.4" "$cv" | sort -V -C \
    || die "Docker Compose $cv застарий — потрібен ≥ 2.24.4 (тег !override у prod)."
  ok "Docker + Compose $cv"

  if ! docker network inspect "$PROXY_NET" >/dev/null 2>&1; then
    docker network create "$PROXY_NET" >/dev/null
    ok "Створено зовнішню мережу '$PROXY_NET'"
  else
    ok "Мережа '$PROXY_NET' існує"
  fi
}

# ── 2. конфігурація і валідація секретів ─────────────────────────────────────
configure() {
  log "Конфігурація та перевірка секретів"
  [ -f "$EXAMPLE_FILE" ] || die "Немає $EXAMPLE_FILE — запускайте з кореня проєкту."
  if [ ! -f "$ENV_FILE" ]; then
    cp "$EXAMPLE_FILE" "$ENV_FILE"; ok "Створено $ENV_FILE із шаблону"
  fi
  require_compose_prod

  # 2.1 машинні секрети — генеруємо автоматично, якщо ще шаблонні
  if is_placeholder "$(get_env JWT_SECRET)"; then
    set_env JWT_SECRET "$(gen_secret 32)"; ok "Згенеровано JWT_SECRET"
  fi
  if is_placeholder "$(get_env DB_PASSWORD)"; then
    if db_volume_exists; then
      die "DB_PASSWORD ще шаблонний, але том БД уже існує. Впишіть реальний пароль у $ENV_FILE вручну (інакше БД буде недоступна)."
    fi
    set_env DB_PASSWORD "$(gen_secret 24)"; ok "Згенеровано пароль БД"
  fi

  # 2.2 людські секрети — обов'язкові, fail-fast
  local errs=0
  is_placeholder "$(get_env ADMIN_USERNAME)" && { warn "ADMIN_USERNAME не задано (≠ changeme)"; errs=1; }
  local apw; apw="$(get_env ADMIN_PASSWORD)"
  if is_placeholder "$apw"; then warn "ADMIN_PASSWORD не задано"; errs=1
  elif [ "${#apw}" -lt 8 ]; then warn "ADMIN_PASSWORD закороткий (мін. 8)"; errs=1; fi

  local has_llm=0 k
  for k in CEREBRAS_API_KEY GROQ_API_KEY GEMINI_API_KEY MISTRAL_API_KEY; do
    is_placeholder "$(get_env "$k")" || has_llm=1
  done
  [ "$has_llm" -eq 1 ] || { warn "Жодного валідного ключа LLM (Cerebras/Groq/Gemini/Mistral)"; errs=1; }

  case "$(get_env CORS_ORIGINS)" in
    *localhost*|*127.0.0.1*) warn "CORS_ORIGINS містить localhost — у проді залиште лише домен" ;;
  esac

  [ "$errs" -eq 0 ] || die "Заповніть обов'язкові секрети в $ENV_FILE і повторіть."
  ok "Секрети валідні"
}

# ── 3. збірка та запуск ──────────────────────────────────────────────────────
build_and_up() {
  log "Збірка образів і запуск стека"
  $COMPOSE build --pull
  $COMPOSE up -d --remove-orphans
  ok "Стек запущено (db, api, frontend)"
}

# ── 4. перевірка живого стека ────────────────────────────────────────────────
wait_db() {
  log "Очікування готовності PostgreSQL"
  local u d; u="$(get_env DB_USER)"; d="$(get_env DB_NAME)"
  local i
  for i in $(seq 1 30); do
    $COMPOSE exec -T db pg_isready -U "$u" -d "$d" >/dev/null 2>&1 && { ok "PostgreSQL готовий"; return 0; }
    sleep 2
  done
  die "PostgreSQL не піднявся за 60с — $COMPOSE logs db"
}

verify() {
  log "Smoke-перевірка"
  $COMPOSE config -q && ok "compose-конфіг валідний"

  local i healthy=0
  for i in $(seq 1 30); do
    $COMPOSE ps api 2>/dev/null | grep -qi healthy && { healthy=1; break; }
    sleep 2
  done
  [ "$healthy" -eq 1 ] && ok "api: healthy" || warn "api ще не healthy ($COMPOSE logs api)"

  if $COMPOSE exec -T api python3 -c \
       "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('$API_HEALTH').status==200 else 1)" \
       >/dev/null 2>&1; then
    ok "GET /health → 200"
  else
    warn "/health не відповів 200"
  fi

  local u d cnt; u="$(get_env DB_USER)"; d="$(get_env DB_NAME)"
  cnt="$($COMPOSE exec -T db psql -U "$u" -d "$d" -tAc \
        "SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('staging','core','analytics','auth');" \
        2>/dev/null | tr -d '[:space:]' || echo 0)"
  [ "${cnt:-0}" -gt 0 ] && ok "Схема БД застосована ($cnt таблиць)" || warn "Схему БД не знайдено"
}

# ── звіт ─────────────────────────────────────────────────────────────────────
report() {
  local dom; dom="$(get_env CORS_ORIGINS | cut -d, -f1)"
  printf '\n%s═══ 503Work розгорнуто ═══%s\n' "$C_OK" "$C_N"
  echo "  • Публічний дашборд:  ${dom:-<ваш домен через reverse-proxy>}"
  echo "  • API health:         $API_HEALTH"
  echo "  • Перший збір даних:  $COMPOSE run --rm etl_worker"
  echo "  • Бекап:              ./install.sh backup   (cron: 0 3 * * *)"
}

# ── команди ──────────────────────────────────────────────────────────────────
cmd_deploy() { check_requirements; configure; build_and_up; wait_db; verify; report; }

cmd_update() {
  log "Оновлення версії (спершу зробіть бекап!)"
  [ -x ./backup.sh ] && { ./backup.sh || warn "backup.sh завершився з помилкою"; }
  configure
  $COMPOSE build --pull
  $COMPOSE up -d --remove-orphans
  wait_db; verify
  ok "Оновлення завершено"
}

cmd_backup() { [ -x ./backup.sh ] || die "backup.sh не знайдено/не виконуваний."; ./backup.sh; }
cmd_status() { $COMPOSE ps; }
cmd_logs()   { $COMPOSE logs -f "${1:-}"; }
cmd_help()   { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; }

case "${1:-deploy}" in
  deploy) cmd_deploy ;;
  update) cmd_update ;;
  verify) check_requirements >/dev/null 2>&1 || true; verify ;;
  backup) cmd_backup ;;
  status) cmd_status ;;
  logs)   shift || true; cmd_logs "${1:-}" ;;
  help|-h|--help) cmd_help ;;
  *) die "Невідома команда: $1 (deploy|update|verify|backup|status|logs|help)" ;;
esac
