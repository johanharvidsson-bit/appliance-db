#!/bin/sh
set -eu

if [ -z "${OUTBOARD_DB_APP_PASSWORD:-}" ]; then
  echo "OUTBOARD_DB_APP_PASSWORD is required" >&2
  exit 1
fi

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$OUTBOARD_DB_APP_PASSWORD" <<'SQL'
CREATE ROLE outboard_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
SQL
