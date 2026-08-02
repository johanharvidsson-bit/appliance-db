# Migration 010 consistency review

**Status: `MIGRATION_010_CONFIRMED_APPLIED`**

Production was verified read-only on 2026-08-02. The recorded migration
identifier is version `010`, filename `010_model_specs_generic.sql`.

> **Operational activation gate:** Migration 010 is already applied; no further
> migration execution is required. `pipeline/scrape_specs.py` has not been run
> after the migration. Activating it remains a separate operational decision
> requiring ordinary runtime, credential, scraper, and backup validation.

## Read-only production verification

The 2026-08-02 verification used `psql` inside the existing PostgreSQL 16
container. It ran inside `BEGIN TRANSACTION READ ONLY`, used catalog and
read-only `SELECT` statements, confirmed `transaction_read_only = on`, and
ended with `ROLLBACK`.

Verified findings:

- `public.schema_migrations` contains
  `('010', '010_model_specs_generic.sql')`.
- `public.model_specs` exists with `model_id`, `specs`, `scraped_at`, and
  `created_at` in the expected types and nullability.
- The expected primary key, cascading foreign key, B-tree index, and JSONB GIN
  index exist.
- Row-level security is enabled and policy `public read model_specs` permits
  `SELECT`.
- Roles `anon` and `authenticated` have `SELECT`, without
  `INSERT`/`UPDATE`/`DELETE` grants.
- `washing_machine_specs` contains 419 rows.
- All 419 corresponding rows exist in `model_specs`; zero typed rows are
  missing, zero `specs` values are null, and all 419 JSONB values exactly match
  the migration's backfill shape.

## Conclusions

1. `db/schema.sql` does **not** represent a fresh database after migration 010. It consolidates migrations 002–009, creates `washing_machine_specs`, and records 002–009 as applied. A fresh installation still needs migration 010 to create and backfill `model_specs`.
2. Migration 010 must not be rerun. The SQL file is not intrinsically fully idempotent: table/index creation and backfill are guarded, but `CREATE POLICY "public read model_specs"` has no duplicate-policy guard.
3. `pipeline/scrape_specs.py` requires `model_specs`. It queries that relation and upserts JSONB specifications into it.
4. Without migration 010, specification runs fail when PostgREST cannot resolve `model_specs`; no specification rows can be read or written. Existing `washing_machine_specs` data remains present but the recovered pipeline no longer targets it.
5. Production migration status is confirmed by the tracking row, catalog
   shape, security configuration, grants, and complete 419-row backfill.

## Migration sequence

- `schema.sql` includes the effects of migrations 002–009 and inserts their tracking rows.
- Migration 008 creates the typed `washing_machine_specs` table.
- Migration 010 creates generic `model_specs`, copies existing typed values into JSONB, retains the typed table for rollback, enables RLS, grants reads, and records version 010.

The backfill uses `ON CONFLICT (model_id) DO NOTHING`, so rerunning it does not overwrite an existing generic row. This is conservative but means a partial earlier backfill is not refreshed automatically.

## Verification query pattern

The completed verification included these catalog checks:

```sql
SELECT
  to_regclass('public.schema_migrations') AS migration_table,
  to_regclass('public.washing_machine_specs') AS typed_specs_table,
  to_regclass('public.model_specs') AS generic_specs_table;
```

If `schema_migrations` exists:

```sql
SELECT version, filename, applied_at
FROM public.schema_migrations
WHERE version = '010';
```

Optionally verify shape without reading application rows:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'model_specs'
ORDER BY ordinal_position;
```

Migration application is no longer a blocker for `scrape_specs.py`. Do not run
the scraper until its separate operational validation and execution are
explicitly approved.
