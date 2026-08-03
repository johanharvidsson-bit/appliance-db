#!/bin/sh
set -eu

if [ -z "${MARINE_POSTGREST_DB_PASSWORD:-}" ]; then
  echo "MARINE_POSTGREST_DB_PASSWORD is required" >&2
  exit 1
fi

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=postgrest_password="$MARINE_POSTGREST_DB_PASSWORD" <<'SQL'
DO $roles$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
END
$roles$;

SELECT format('CREATE ROLE marine_postgrest LOGIN PASSWORD %L NOINHERIT', :'postgrest_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='marine_postgrest') \gexec
GRANT anon TO marine_postgrest;
SQL
