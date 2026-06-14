#!/usr/bin/env bash
# Бекап БД: pg_dump через контейнер db → gzip → тримає KEEP останніх дампів.
# Запуск вручну або з cron: 0 3 * * * /data/503work/backup.sh >> /data/backups/backup.log 2>&1
# Відновлення:
#   gunzip -c <дамп>.sql.gz | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
set -euo pipefail

cd "$(dirname "$0")"

BACKUP_DIR="${BACKUP_DIR:-/data/backups}"
KEEP="${KEEP:-14}"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/503work_${TS}.sql.gz"

mkdir -p "$BACKUP_DIR"

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$OUT"

# прибираємо все, крім KEEP найсвіжіших
ls -1t "$BACKUP_DIR"/503work_*.sql.gz | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "$(date -Is) backup OK: ${OUT} ($(du -h "$OUT" | cut -f1))"
