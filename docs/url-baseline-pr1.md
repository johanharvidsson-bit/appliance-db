# PR 1 — URL baseline and entity bindings

This PR adds internal persistence and an offline-first inventory command. It does not change public URLs, redirects, canonicals, sitemap behavior, frontend behavior, or production.

## Manual offline inventory

Input is a JSON array. Each row contains `url`, `page_type`, and optionally a matching `entity_type` plus integer `entity_id`. Optional precomputed fields are `sitemap_present` and `internal_incoming_links`.

```powershell
python -m pipeline.url_inventory `
  --input data/url-candidates.json `
  --output data/url-baseline.jsonl `
  --environment development `
  --max-urls 500
```

HTTP checks are disabled by default. `--check-http` uses the repository target-safety guard, a fixed user agent, a maximum 30-second timeout, a 2 MB response cap, deduplication, and a hard 5,000-URL cap. It does not classify URLs or write the database.

The artifact always starts with `classification=unclassified`. Search metrics remain absent/NULL unless supplied by a later approved process; missing metrics never mean zero.

## Guarded local persistence

Persistence is optional and restricted to `development`. The DSN must pass the repository target guard, which for PostgreSQL means loopback port `15432` and database `repair_appliance_dev`.

```powershell
$env:REPAIRBASE_URL_REGISTRY_DB_URL = 'postgresql://postgres@127.0.0.1:15432/repair_appliance_dev'
python -m pipeline.url_inventory `
  --input data/url-candidates.json `
  --output data/url-baseline.jsonl `
  --environment development `
  --persist
```

Registry upserts are idempotent by site, environment, and normalized URL. Re-observation preserves an existing human classification and its reason. Current entity bindings are idempotent and remain `candidate`; persistence never marks them verified. The artifact is written before persistence so a failed transaction remains inspectable.

## Database persistence

Migration 015 creates `url_registry` and the current-entity phase of `entity_url_bindings`. It performs no backfill. PR 2 adds binding columns for v1 entities that do not exist yet (`model_variants` and `guides`).

Both tables force RLS, revoke public/anon/authenticated access, and grant the service role only SELECT/INSERT/UPDATE. There is no DELETE grant. A later explicitly guarded persistence command may upsert reviewed artifacts; this PR deliberately stops at generation and schema foundation.

## Rollback

Before any later rollback, export both tables. Because they preserve URL/migration history, automated rollback must not drop them. Removing migration 015 from an unapplied development database is safe; reversing an applied environment requires a reviewed follow-up migration rather than destructive ad-hoc SQL.
