#!/bin/sh
set -eu

base=${OUTBOARD_BASE:-/opt/outboardrepairbase}
compose_file="$base/current/outboard-web/compose.staging.yaml"
env_file="$base/.env"
backup_dir=${OUTBOARD_BACKUP_DIR:-$base/backups}
retention_days=${OUTBOARD_BACKUP_RETENTION_DAYS:-14}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$backup_dir/outboard-$stamp.dump"
temporary="$target.partial"

umask 077
mkdir -p "$backup_dir"
trap 'rm -f "$temporary"' EXIT HUP INT TERM

docker compose --project-name outboardrepairbase --env-file "$env_file" \
  -f "$compose_file" exec -T postgres sh -c \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
  > "$temporary"

test -s "$temporary"
docker compose --project-name outboardrepairbase --env-file "$env_file" \
  -f "$compose_file" exec -T postgres pg_restore --list < "$temporary" >/dev/null
mv "$temporary" "$target"
trap - EXIT HUP INT TERM

find "$backup_dir" -type f -name 'outboard-*.dump' -mtime "+$retention_days" -delete
printf '%s\n' "$target"
