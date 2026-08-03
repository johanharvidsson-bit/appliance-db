# VPS development environment

## Status

This document describes the isolated development workspace beside the live
ApplianceRepairBase installation. It is not a deployment guide and does not
authorize production access, database writes, migrations, scrapers, scheduled
jobs, or service startup.

Prepared on 2026-08-02:

- Development owner: `repairbase` (UID/GID 1000), no sudo or Docker-group membership.
- Development root: `/opt/repairbase` (`0750`, owned by `repairbase`).
- Backend: cloned from GitHub branch `reconciliation/backend-source-recovery`.
- Frontend: cloned from GitHub `main` at the approved baseline SHA.
- Production paths `/root/appliance-db` and `/root/appliance-db-stack` were not changed.
- No development service has been created or started.

## Directory layout

Target layout:

```text
/opt/repairbase/
  appliance-db/
    .env                 # mode 0600; development-only, never commit
    .venv/               # isolated Python environment
    docs/
  appliance-theme/       # frontend main; development-only .env
  dev-stack/             # isolated PostgreSQL/PostgREST Compose project
  secrets-archive/       # root-only inactive credential archive
```

The repositories must remain independent Git checkouts. Production remains
under `/root`; no development command should use a `/root/appliance-db*` path.

## Capacity and software

Observed host: Ubuntu Linux on ARM64, 38 GB root disk, approximately 7.6 GB
available after backend setup, 3.7 GiB RAM, no swap. Docker build cache was
about 15 GB, of which about 11 GB was reported reclaimable. Do not prune it
without separate approval; expand the disk if routine development repeatedly
leaves less than 3 GB free.

Available software:

- Git 2.43
- Node.js 22.23 and npm 10.9
- Python 3.12
- Tesseract 5.3
- Docker and Docker Compose (production-owned; `repairbase` has no access yet)

Backend requirements are installed only in
`/opt/repairbase/appliance-db/.venv`. Frontend dependencies must be installed
with `npm ci` after the private repository can be cloned.

## Environment variables

Backend variable names currently present in the sealed `.env` copy:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `ANTHROPIC_API_KEY`
- `SERPER_API_KEY`
- `TESSERACT_CMD`
- `DOWNLOAD_MANUALS`
- `LOG_DIR`
- `LOG_LEVEL`
- `MANUAL_DOWNLOAD_DIR`
- `MAX_RETRIES`
- `REQUEST_DELAY_SECONDS`

The repository example also documents `SUPABASE_DB_URL` and
`SCRAPE_DO_API_KEY`; these were not present in the copied production file.

Frontend variable names:

- `PUBLIC_SUPABASE_URL`
- `PUBLIC_SUPABASE_ANON_KEY`
- `ACTIVE_SITE`

Never print, commit, rotate, or casually source secret values. Active backend
and frontend `.env` files contain development-only values. The former
production-derived backend environment is inactive in the root-owned
`secrets-archive`. The central target guard blocks development access to
Appliance production, Marine production, the retired Supabase endpoint,
malformed targets and unknown targets.

## Validation commands

Backend offline validation:

```bash
cd /opt/repairbase/appliance-db
source .venv/bin/activate
python -c "from pathlib import Path; files=[p for p in Path('.').rglob('*.py') if '.venv' not in p.parts]; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in files]; print(f'{len(files)} Python files compiled')"
python -c "import anthropic, bs4, httpx, loguru, lxml, pdfplumber, PIL, playwright, psycopg2, pytesseract, requests, rich, supabase"
git status -sb
deactivate
```

Do not use `pytest` as a default smoke test until its import path is proven not
to initialize production configuration.

Frontend validation after cloning:

```bash
cd /opt/repairbase/appliance-theme
npm ci
npm run check
npm run build
git status -sb
```

The current frontend repository has known baseline ESLint/Prettier failures;
record them separately from build success. A successful Marine configuration
build is not deployment approval.

## Development database recommendation

The workspace uses **B: a cloned development database**.

A long-lived development workspace must not use the live database, even with a
nominally read-only workflow, because backend service credentials are capable
of writes and application behavior can change. Create a sanitized/controlled
database copy only under separate approval, with development-only roles and
credentials. Until then, offline compilation and builds are permitted, but
database-connected execution is blocked.

## Proposed service architecture

The dedicated Compose project is `repairbase-dev` under
`/opt/repairbase/dev-stack`, with pinned images, its own network, volume,
container names, environment, credentials and Appliance database clone.

Recommended localhost-only bindings:

| Component | Development binding | Production conflict avoided |
|---|---|---|
| PostgreSQL | `127.0.0.1:15432` | production `127.0.0.1:5432` |
| PostgREST | `127.0.0.1:18080` | production PostgREST is internal; nginx publishes 80/8080 |
| Development nginx | `127.0.0.1:18081` | production ports 80/8080 |
| Astro dev server | `127.0.0.1:14321` | other services on 5173 |

Prefer SSH port forwarding instead of public firewall exposure. Development
nginx is optional initially; direct localhost PostgREST and Astro access is
simpler. Do not reuse production Docker volumes, networks, container names,
ports, `.env`, or Compose project name.

Proposed lifecycle after approval:

```bash
# Start only the future development compose project
cd /opt/repairbase/dev-stack
docker compose -p repairbase-dev up -d

# Stop only the future development compose project
docker compose -p repairbase-dev down
```

Never use `down --volumes` unless deletion of the development database has
been separately approved.

## Git workflow and daily development

Connect directly as the unprivileged development user:

```bash
ssh repairbase@204.168.147.249
```

Backend daily workflow:

```bash
cd /opt/repairbase/appliance-db
git status -sb
git fetch origin
git switch reconciliation/backend-source-recovery
git pull --ff-only
git switch -c feature/<backend-change>
source .venv/bin/activate
# edit and run offline validation only
git diff --check
git status -sb
```

Frontend bootstrap after repository access is granted:

```bash
cd /opt/repairbase
git clone --branch main --single-branch \
  git@github.com:johanharvidsson-bit/appliance-theme.git appliance-theme
cd appliance-theme
npm ci
npm run check
npm run build
git status -sb
```

Frontend daily workflow after bootstrap:

```bash
cd /opt/repairbase/appliance-theme
git status -sb
git fetch origin
git switch main
git pull --ff-only
git switch -c feature/<frontend-change>
npm run check
npm run build
```

Never work directly on `main`, never force-push shared history, and never use
the production checkout as a development worktree.

## Remaining blockers

1. Review the settings and target-safety stabilization branch.
2. Fix broad anonymous API access in its separately approved security phase.
3. Keep Docker administration root-controlled until narrowly scoped access is approved.
4. Rotate the compromised Marine credential in a production-change window.
5. Decide whether to expand disk or approve selective build-cache cleanup if
   free space approaches 3 GB.
6. Consider adding swap or increasing RAM before concurrent Docker builds; no
   swap is currently configured.

## Separate-database architecture

Future niches share source, schema definitions, migrations, renderer and
tooling, but each niche has its own PostgreSQL database, PostgREST instance,
credentials, backup, restore and runtime configuration. Do not add a shared
`vertical_id` to Appliance tables. This dev stack contains only Appliance.

## Resource stop rules

Stop if free disk falls below 5 GB, available RAM remains below 500 MB, a dev
service targets production, an active dev config contains production
credentials, another stack creates sustained severe pressure, or a production
container becomes unhealthy. Never prune Docker automatically.

## Production relationship

Production remains authoritative and independent. Development must not restart,
stop, upgrade, mount, or modify production containers, volumes, cron jobs,
configuration, logs, database, nginx, PostgREST, or filesystem paths. Moving
daily coding to `/opt/repairbase` does not deploy any code.
