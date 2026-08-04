#!/bin/sh
set -eu

base=${OUTBOARD_BASE:-/opt/outboardrepairbase}
compose_file="$base/current/outboard-web/compose.staging.yaml"
env_file="$base/.env"
backup_dir=${OUTBOARD_BACKUP_DIR:-$base/backups}
backup=${1:-$(find "$backup_dir" -type f -name 'outboard-*.dump' -printf '%T@ %p\n' | sort -nr | sed -n '1s/^[^ ]* //p')}
test_db="outboard_restore_check_$(date -u +%Y%m%d%H%M%S)_$$"

test -n "$backup"
test -s "$backup"

compose() {
  docker compose --project-name outboardrepairbase --env-file "$env_file" -f "$compose_file" "$@"
}

cleanup() {
  compose exec -T postgres sh -c \
    'dropdb -U "$POSTGRES_USER" --if-exists --force "$1"' sh "$test_db" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

compose exec -T postgres sh -c \
  'createdb -U "$POSTGRES_USER" "$1"' sh "$test_db"
compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$1" --exit-on-error --no-owner --no-acl' sh "$test_db" \
  < "$backup"

result=$(compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$1" -Atc "SELECT (SELECT count(*) FROM rb_engine_models),(SELECT count(*) FROM rb_pages),(SELECT count(*) FROM schema_migrations WHERE version IN ('"'"'011'"'"','"'"'012'"'"','"'"'013'"'"'));"' \
  sh "$test_db")

models=$(printf '%s' "$result" | cut -d '|' -f 1)
pages=$(printf '%s' "$result" | cut -d '|' -f 2)
migrations=$(printf '%s' "$result" | cut -d '|' -f 3)
test "$models" -ge 1
test "$pages" -ge 1
test "$migrations" -eq 3
printf 'restore-check ok: models=%s pages=%s migrations=%s\n' "$models" "$pages" "$migrations"
