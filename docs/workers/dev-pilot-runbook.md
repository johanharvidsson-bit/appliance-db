# Five-item development pilot runbook

## Gate B prerequisites

Create a completely separate PostgreSQL development project. Do not clone or reuse production credentials. Put secrets in `.env` (ignored by Git), never `.env.example`.

Required values:

```text
APP_ENV=development
REPAIRBASE_SECURITY_TEST_DB_URL=<secret development DSN>
REPAIRBASE_DEV_DB_HOST=<exact DSN hostname, no credentials>
REPAIRBASE_DEV_DB_NAME=<exact database name>
REPAIRBASE_DEV_DB_USER=<exact database username/project role>
SITE_ID=appliance-repair-base
SERPER_API_KEY=<local secret>
```

Before proceeding, report only host, database/project reference, role and current migration version. Never print the DSN or key. Confirm that host, database, user, project, storage and credentials are distinct from production.

## Bootstrap and migration

1. Load `db/schema.sql` into the empty development database using the provider's SQL console or a guarded bootstrap command.
2. Run `python -m db.apply_migration --list`.
3. Run `python -m db.apply_migration --all`; stop at the first error.
4. Verify versions 002–026 in `schema_migrations`.
5. Run the full test suite with the explicit development DSN.
6. Verify PK/FK/index/UNIQUE/CHECK, forced RLS and grants for every worker table listed in the task.
7. Verify anonymous denial and permitted service/backend writes with dedicated test roles.

## Sanitized seed contract

Seed only one existing brand, one existing category and one existing locale plus the minimal referenced model/error-code records. Preferred scope is LG × Washing Machines × English only if those records exist. No production dump is authorized. Required tables are `sites`, `site_locales`, `brands`, `categories`, `locales`, `models`, `product_codes`, `error_codes` and the minimum publication/content rows needed by coverage checks.

## Pilot sequence

Use batch size five and record every run/object id:

```text
python -m workers cube-coverage --site <site> --environment development --dry-run --batch-size 5
python -m workers cube-coverage --site <site> --environment development --scope new --batch-size 5
python -m workers source-discovery --site <site> --environment development --dry-run --batch-size 5
python -m workers source-discovery --site <site> --environment development --batch-size 5 --rate-limit 1
```

Manually review each source; record candidate id, reviewer, decision, reason and timestamp. Then run ingestion only for accepted IDs. Run knowledge integration, manually review every proposal, dry-run each approved low-risk proposal, apply with `--confirm`, assemble, and validate. Stop after validation.

Select exactly five low-risk backlog items, preferably two model overviews, one model specification and two error-code descriptions. Exclude guides/procedures, merges, product-code moves, negative applicability and all URL/publication operations.

## Rerun and failure test

Repeat the same pipeline and compare counts/identity hashes. Only new worker-run rows may be added. Then inject one controlled failure before persistence in ingestion, integration or assembly; verify failure recording, lock release, successful resume, no partial domain mutation and no duplicates.

## Hard stops

Stop immediately for a production-like target, missing identity declaration, migration error, cross-scope source, wrong model/brand/category, unresolved high-risk proposal, URL/publication mutation, or required architecture change.

