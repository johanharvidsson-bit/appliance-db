#!/bin/sh
set -eu

: "${POSTGRES_MIGRATION_PASSWORD:?POSTGRES_MIGRATION_PASSWORD is required}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=migration_password="$POSTGRES_MIGRATION_PASSWORD" \
  --set=app_password="$POSTGRES_APP_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE repairbase_migrator LOGIN PASSWORD %L', :'migration_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'repairbase_migrator')
\gexec

SELECT format('CREATE ROLE repairbase_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'repairbase_app')
\gexec

SELECT format('GRANT CONNECT, CREATE ON DATABASE %I TO repairbase_migrator', current_database())
\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO repairbase_app', current_database())
\gexec

GRANT USAGE, CREATE ON SCHEMA public TO repairbase_migrator;
GRANT USAGE ON SCHEMA public TO repairbase_app;

ALTER DEFAULT PRIVILEGES FOR ROLE repairbase_migrator IN SCHEMA public
  GRANT SELECT ON TABLES TO repairbase_app;
ALTER DEFAULT PRIVILEGES FOR ROLE repairbase_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO repairbase_app;
SQL
