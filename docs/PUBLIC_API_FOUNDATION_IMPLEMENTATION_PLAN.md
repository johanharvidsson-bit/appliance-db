# Public API foundation implementation plan

Planning document only. This change does not implement `api_public`.

## Proposed branch and scope

Use a new branch such as `security/public-api-foundation-v1` after the API
contract and migration 011 are reviewed. Keep the first implementation PR to:

- an `api_public` schema and constrained `api_public_owner`;
- `brands` and a localized category projection;
- `sitemap_entries`;
- stable public identities;
- keyset pagination and required indexes;
- contract/RLS tests and `EXPLAIN (ANALYZE, BUFFERS)` measurements.

## Role and privilege model

Create `api_public_owner` as `NOLOGIN`, `NOSUPERUSER`, `NOCREATEDB`,
`NOCREATEROLE`, `NOREPLICATION`, and `NOBYPASSRLS`. It must not own source
tables, inherit `service_role`, receive schema-wide privileges, create objects
outside `api_public`, or read unrelated raw tables. Grant only the minimum
source-column/table access needed by reviewed views. Grant `USAGE` on
`api_public` and `SELECT` on approved views to `anon` and `authenticated`; never
grant those roles direct write access.

## Sources, views, and public fields

Initial sources are `public.brands`, `public.categories`, and
`public.category_translations`. The first views should expose:

- `api_public.brands`: stable public ID, name, slug, logo URL, active state;
- a localized category projection: stable public ID, locale, localized name and
  slug, with an explicit fallback rule;
- `api_public.sitemap_entries`: canonical URL identity, locale, route kind,
  change timestamp and alternate relationship required by the contract.

Public IDs must be stable, opaque to storage changes, unique, immutable after
publication, and tested against accidental numeric primary-key exposure. Decide
their generation and migration before defining the views.

## Query and index design

Use deterministic keyset ordering, for example `(normalized_name, public_id)`
for brands/categories and `(route_kind, canonical_path, public_id)` for sitemap
entries. Cursor values must include every ordering key; no offset pagination.
Add only indexes supported by measured plans, likely source indexes covering
active-state/slug and translation locale/category lookups. Capture baseline and
post-index `EXPLAIN (ANALYZE, BUFFERS)` on representative dev cardinalities.

## Blocking validation

- contract tests for exact columns, types, nullability and forbidden fields;
- privilege tests proving `anon`/`authenticated` can read approved views only;
- tests proving `api_public_owner` cannot write source tables, bypass RLS,
  create roles/databases, or read unrelated internal tables;
- locale fallback, unique identity and keyset boundary tests;
- sitemap consistency tests against route identity and alternates;
- plans demonstrating bounded scans and no unplanned sequential scan;
- row parity checks between approved source sets and projections;
- secret scan, migration syntax check, clean rollback rehearsal in disposable
  dev state, and all existing offline/security tests.

## Rollback

Use a dedicated rollback that revokes consumer grants, drops only the new views
and `api_public` schema objects, then drops `api_public_owner` after dependent
grants are removed. It must not change source rows or restore broad raw-table
access. Record pre/post grants and object definitions in the PR evidence.

## Explicitly out of scope

- `article_pages`, `model_pages`, `fault_pages`, and `error_codes`;
- model-spec normalization or sanitizer implementation;
- frontend migration;
- Cloudflare, production deployment, credentials, or runtime changes;
- Marine or any other niche database;
- changes to the database-per-niche architecture.
