#!/bin/sh
set -eu

base=${OUTBOARD_BASE:-/opt/outboardrepairbase}
compose_file="$base/current/outboard-web/compose.staging.yaml"
env_file="$base/.env"

compose() {
  docker compose --project-name outboardrepairbase --env-file "$env_file" -f "$compose_file" "$@"
}

for service in postgres web caddy; do
  container=$(compose ps -q "$service")
  test -n "$container"
  running=$(docker inspect --format '{{.State.Running}}' "$container")
  test "$running" = true
done

web_container=$(compose ps -q web)
postgres_container=$(compose ps -q postgres)
test "$(docker inspect --format '{{.State.Health.Status}}' "$web_container")" = healthy
test "$(docker inspect --format '{{.State.Health.Status}}' "$postgres_container")" = healthy

response=$(curl --fail --silent --show-error --insecure \
  --resolve outboardrepairbase.com:443:127.0.0.1 \
  https://outboardrepairbase.com/api/health)
printf '%s' "$response" | grep -q '"status":"ok"'
printf '%s' "$response" | grep -q '"dataSource":"postgresql"'
printf 'healthcheck ok\n'
