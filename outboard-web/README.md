# OutboardRepairBase staging runtime

This package serves the first OutboardRepairBase vertical slice from a dedicated
PostgreSQL database. It includes the web/API process, PostgreSQL 16, a read-only
runtime database role, synthetic outboard test data, and a Caddy TLS edge.

The staging site is deliberately `noindex`. Its records are demonstration data
and must not be used for repair decisions. No Supabase service is used.

## Local fixture URL

```powershell
npm ci
npm test
npm run dev
```

Open <http://localhost:4323>. With no database environment variables, the
server reads `data/models.json` and labels the source as a local fixture.

## VPS staging deployment

Requirements:

- Docker Engine with Compose v2
- DNS A/AAAA record for the staging hostname
- inbound TCP 443 (port 80 may remain owned by an existing reverse proxy)
- two independently generated database passwords

Copy this repository to the VPS, then:

```bash
cd outboard-web
cp .env.example .env
# Fill every blank secret and replace the example hostname.
docker compose --env-file .env -f compose.staging.yaml config
docker compose --env-file .env -f compose.staging.yaml up -d --build
docker compose --env-file .env -f compose.staging.yaml ps
curl --fail https://your-staging-host/api/health
```

Caddy listens publicly on 443 and uses the TLS-ALPN ACME challenge. Its HTTP
port defaults to 18081 so this stack can coexist with an existing port-80
reverse proxy on the VPS. `www` redirects permanently to the apex hostname.

On the first start, PostgreSQL applies the isolated `rb_*` RepairBase migrations
011–013, the staging seed, and the least-privilege runtime grants. The legacy
Appliance schema is deliberately not loaded into this database. Init scripts
do not rerun against an existing volume. Later schema changes therefore need an
explicit migration command; do not recreate the volume to migrate real data.

The app connects as `outboard_app`, which only has `SELECT` on the six `rb_*`
tables used by the public catalogue query. PostgreSQL has no published host
port. Only Caddy exposes 80/443. The web container is read-only, drops Linux
capabilities, and cannot write domain data.

## Verification

```bash
docker compose --env-file .env -f compose.staging.yaml exec -T postgres \
  psql -U "$OUTBOARD_DB_ADMIN_USER" -d "$OUTBOARD_DB_NAME" \
  -c "select site_key, publication_state from rb_sites;"

docker compose --env-file .env -f compose.staging.yaml exec -T postgres \
  psql -U "$OUTBOARD_DB_ADMIN_USER" -d "$OUTBOARD_DB_NAME" \
  -c "select has_table_privilege('outboard_app','rb_pages','SELECT'), has_table_privilege('outboard_app','rb_pages','INSERT');"
```

Expected privilege result: `true, false`. The seeded pages are published only
inside this isolated staging catalogue and remain `noindex/editorial_hold`.

## Production operations

The staging Compose file bounds every container's Docker JSON log to three
10 MB files and keeps `restart: unless-stopped`. Docker itself must be enabled
at boot (`systemctl enable docker`).

Install the dedicated systemd timers after deploying a release:

```bash
chmod 0755 ops/*.sh
sudo ops/install-systemd.sh
```

The timers provide:

- a daily custom-format PostgreSQL backup at 02:15 UTC;
- retention of 14 days under `/opt/outboardrepairbase/backups`;
- an internal health check every five minutes;
- a weekly restore into a disposable database, followed by catalogue and
  migration checks. The disposable database is always dropped afterward.

Run and inspect them manually with:

```bash
sudo systemctl start outboard-backup.service
sudo systemctl start outboard-restore-check.service
sudo systemctl start outboard-health.service
sudo systemctl status outboard-backup.service outboard-restore-check.service outboard-health.service
sudo journalctl -u 'outboard-*' --since today
```

Backups are stored locally on the VPS. An off-site copy is still required
before the service contains irreplaceable production data.

## Deployment and rollback

Deploy immutable releases below `/opt/outboardrepairbase/releases/<git-sha>`.
Keep `/opt/outboardrepairbase/.env`, `backups/`, and Docker volumes outside the
release directories. Before changing a running release:

1. run `ops/backup.sh` and `ops/restore-check.sh`;
2. extract the new release and validate `docker compose config --quiet`;
3. build the web image;
4. atomically repoint `/opt/outboardrepairbase/current` to the new release;
5. run `docker compose up -d` and `ops/healthcheck.sh`.

For an application-only rollback, repoint `current` to the preceding release,
run its Compose file with `up -d --build`, and execute its health check. Do not
roll back application code across an incompatible database migration.

For a database rollback, stop writers, retain a safety backup of the current
database, restore the selected dump into a new database, validate it, and only
then switch the application connection. Never overwrite the only database copy
in place. The supplied `restore-check.sh` intentionally verifies a disposable
database and is not a production replacement command.

## Boundaries

This delivery does not merge the separate PR 2A–2D worker migration line,
publish production content, configure production DNS, run a scheduler, or add
error-code/guide authoring. Reconciling the overlapping migration histories is
a separate prerequisite before workers can write into the shared `rb_*` model.
