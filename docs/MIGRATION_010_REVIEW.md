# Migration 010 consistency review

> **Production activation gate:** `pipeline/scrape_specs.py` requires the
> `model_specs` table. Do not run it against any database where migration 010
> is absent. Production migration status is currently unknown and must be
> established through a separately approved read-only status check. Applying
> migration 010 requires separate approval and a documented backup/rollback
> plan.

## Conclusions

1. `db/schema.sql` does **not** represent a fresh database after migration 010. It consolidates migrations 002–009, creates `washing_machine_specs`, and records 002–009 as applied. A fresh installation still needs migration 010 to create and backfill `model_specs`.
2. Migration 010 is safe to retry through `db.apply_migration` after version `010` has been recorded. The SQL file is not intrinsically fully idempotent: table/index creation and backfill are guarded, but `CREATE POLICY "public read model_specs"` has no duplicate-policy guard.
3. `pipeline/scrape_specs.py` requires `model_specs`. It queries that relation and upserts JSONB specifications into it.
4. Without migration 010, specification runs fail when PostgREST cannot resolve `model_specs`; no specification rows can be read or written. Existing `washing_machine_specs` data remains present but the recovered pipeline no longer targets it.
5. File presence on the VPS does not prove that migration 010 was applied. Production migration status remains an explicit approval gate.

## Migration sequence

- `schema.sql` includes the effects of migrations 002–009 and inserts their tracking rows.
- Migration 008 creates the typed `washing_machine_specs` table.
- Migration 010 creates generic `model_specs`, copies existing typed values into JSONB, retains the typed table for rollback, enables RLS, grants reads, and records version 010.

The backfill uses `ON CONFLICT (model_id) DO NOTHING`, so rerunning it does not overwrite an existing generic row. This is conservative but means a partial earlier backfill is not refreshed automatically.

## Later read-only verification

Run these only after separate approval against the intended database:

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

Do not run `scrape_specs.py` until both the table and migration state have been reconciled.
