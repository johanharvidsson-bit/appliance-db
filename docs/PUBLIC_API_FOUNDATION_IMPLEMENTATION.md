# Public API foundation implementation

Status: implemented and verified in the isolated VPS development database on
2026-08-03. This branch is stacked on `security/revoke-internal-public-access`.
The normative v1 contract remains in the separate Draft branch
`design/public-api-contract-v1` and was read directly from that Git ref.

## Implemented resources

Migration `012_public_api_foundation.sql` creates exactly:

- `api_public.brands`
- `api_public.category_pages`
- `api_public.sitemap_entries`

An internal `public.api_public_identities` mapping freezes semantic string keys
without changing source rows. Brand keys initially match the existing slug;
category keys are language-independent singular keys. Slug edits do not update
an existing mapping. Raw integer IDs never cross the public boundary.

## Publication and routes

Brands require `is_active` and at least one model. Their v1 canonical path is
the verified English brand hub `/brands/{slug}/`. Categories require an active
source row and an explicit nonempty translation; missing locales produce no
row and no fallback. English category paths are `/{slug}/`; other locales are
`/{locale}/{slug}/`, matching the current Astro routes.

The source schema has no separate category translation approval, public
indexability state, or public lifecycle timestamp. The compatibility rule is
therefore `indexable=true` for present translations and `updated_at=NULL`.
Source creation and scrape timestamps are deliberately not repurposed.
`icon_key` is NULL because `icon_url` is not an approved stable asset key.

## Ownership and privileges

`api_public_owner` is NOLOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE,
NOINHERIT, NOREPLICATION and NOBYPASSRLS. PostgreSQL owns the schema;
`api_public_owner` owns projection objects but has no schema CREATE privilege.
It owns no source table and receives only column-level SELECT on the identity
mapping, brands, categories, category translations, and the model relation
columns required by the brand publication predicate.

`anon` and `authenticated` receive schema USAGE and explicit SELECT on the
three resources only. They receive no new source grants or writes. Default
privileges do not expose future objects. Existing raw reads required by the
unmigrated frontend are unchanged. Migration 011 denials remain in force.

The source tables retain RLS. Their existing transition policy applies to the
constrained view owner, which does not bypass RLS. The sitemap is materialized,
so request roles read only its snapshot and never execute source joins.

## Identity, keyset, and collation

- Brands: `name COLLATE "C" ASC, brand_key ASC`.
- Category pages: `sort_order ASC, category_key ASC, locale COLLATE "C" ASC`.
- Sitemap: `canonical_path COLLATE "C" ASC, locale COLLATE "C" ASC,
  sitemap_entry_id ASC`, always filtered to one `projection_revision`.

All tie-breakers are immutable. Null sort keys are absent. Public display values
retain source Unicode; fixed C collation supplies bytewise, case- and
accent-sensitive ordering. The views do not imply order—clients must request it.

## Sitemap snapshot

The materialized view contains only foundation brand/category paths. Stable
UUIDv5 entry IDs derive from content type, frozen public key and locale;
canonical paths may change without changing identity. Each refresh creates one
UUID revision shared by the entire snapshot. Consumers capture that revision
and use the documented keyset until export completion. Hreflang is JSONB and
contains only currently projected locale paths. A unique identity index and a
revision/path/locale/ID index prevent duplicates and support scanning.

Refresh is an explicit privileged operation:

```sql
REFRESH MATERIALIZED VIEW api_public.sitemap_entries;
```

This PR does not add event-driven refreshes or scheduled jobs.

## PostgREST development exposure

PostgREST must expose both `public` (temporary frontend compatibility) and
`api_public`. The checked-in `config/postgrest.dev.env.example` contains only
nonsecret settings. The isolated dev stack was configured with
`PGRST_DB_SCHEMAS=public,api_public` and `PGRST_DB_MAX_ROWS=1000`, then only its
PostgREST container was recreated. No database or production service restarted.
Clients select `api_public` through the PostgREST profile header.

## Rollback

Do not execute against production. In a controlled dev transaction:

```sql
BEGIN;
REVOKE ALL ON api_public.sitemap_entries FROM anon, authenticated;
REVOKE ALL ON api_public.category_pages FROM anon, authenticated;
REVOKE ALL ON api_public.brands FROM anon, authenticated;
DROP MATERIALIZED VIEW api_public.sitemap_entries;
DROP VIEW api_public.category_pages;
DROP VIEW api_public.brands;
DROP TABLE public.api_public_identities;
DROP SCHEMA api_public;
DELETE FROM public.schema_migrations WHERE version='012';
DROP OWNED BY api_public_owner;
DROP ROLE api_public_owner;
ROLLBACK;
```

The rollback is validation guidance. It neither changes migration 011 nor
reopens `scrape_jobs` or `schema_migrations`.

## Development validation and performance

The final dev projection contains 5 active published brands, 14 explicit
category/locale rows and 24 sitemap entries in one revision. Source counts were
unchanged: brands 12, categories 7, category translations 14 and models 47,541.
Migration history contains both 011 and 012. The documented rollback completed
inside a transaction and was rolled back, leaving the final dev state intact.

All measurements below are functional dev measurements, not load tests. The
dataset is deliberately tiny at the public foundation layer:

| Query | Rows | Execution time | Plan notes |
|---|---:|---:|---|
| Brand list | 5 | 0.111 ms | identity bitmap index; model index-only scan; 25 kB quicksort |
| Brand-key lookup | 1 | 0.083 ms | unique identity index; model index-only scan |
| Brand slug lookup | 1 | 0.050 ms | 12-row source seq scan; model/identity indexes |
| Brand next keyset page | 2 | 0.109 ms | deterministic 25 kB quicksort |
| Swedish category list | 7 | 0.095 ms | tiny 7/14-row source scans; identity PK |
| Category-key/locale lookup | 1 | 0.046 ms | unique identity index |
| Category slug/locale lookup | 1 | 0.061 ms | tiny 14-row translation scan |
| Category next keyset page | 4 | 0.138 ms | 25 kB quicksort |
| Sitemap first batch | 10 | 0.046 ms | 24-row snapshot seq scan/top-N heapsort |
| Sitemap next batch | 10 | 0.050 ms | 24-row snapshot seq scan/quicksort |
| Full foundation export | 24 | 0.098 ms | 29 kB quicksort |
| Sitemap refresh | 24 | 20.732–23.034 ms | full materialized refresh |

All buffers were shared hits; no reads were reported in the measured warm run.
PostgreSQL correctly prefers sequential scans over the sitemap keyset index at
24 rows. The unique identity and revision/keyset indexes remain required for
integrity and larger snapshots. No speculative source index was added.
Both sitemap indexes occupy 16 kB in the measured dev database.

PostgREST dev exposes `public,api_public` with a 1000-row cap. Read checks
returned 200 for all three resources for `anon` and `authenticated`; anonymous
writes are not permitted. INSERT attempts against the two ordinary read-only
views currently return PostgreSQL/PostgREST 500 “view not automatically
updatable” responses before a clean 401/403 mapping. They expose no credentials,
DSN, token, raw query or stack trace, but error normalization remains a blocker
for a polished public gateway and is explicitly outside this foundation PR.

## Not implemented

Models, model pages, articles, article pages, article translations, faults,
error codes, model specs, sanitizer, frontend migration, Cloudflare, Marine,
other niche databases, production configuration and deployment are not
implemented.

## Open decisions and next PR

Before frontend migration, add an explicit publication/indexability lifecycle
and public updated timestamp, decide a governed icon-key registry, automate a
privileged sitemap refresh/export process, and merge or retarget the separate
contract PR. The recommended next PR is a frontend adapter limited to these
three resources only after the stacked security and contract reviews land.
