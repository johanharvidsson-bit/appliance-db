# Public model pages API implementation

Migration `014_public_api_model_pages.sql` adds only
`api_public.model_pages`, the localized routing companion to the
language-independent `api_public.models` catalog.

## Contract

The exact columns are `model_page_id`, `model_id`, `brand_key`, `category_key`,
`locale`, `category_slug`, `model_slug`, `canonical_path`, `hreflang`,
`indexable`, `published_at`, and `updated_at`. The composite domain identity is
`model_id + locale`; `model_page_id` is its stable transport UUID. Model name,
series, specifications, manuals, and other language-independent data remain in
their own resources rather than being duplicated here.

## Sources, identity, and locale

The projection reads only existing approved API objects:

- `api_public.models` for stable model identity, route slug and indexability;
- `api_public.brands` for the current brand route slug;
- `api_public.category_pages` for an explicit locale row, localized category
  slug, category canonical prefix and category indexability.

No new raw-table grants are required. Page UUIDs use namespace
`repairbase:v1:model_page` and UUIDv5 input `model_id:locale`. They therefore do
not change when a model name, localized label, slug, or canonical path changes.
Different locales and models cannot collide. Missing category translations
produce no page row and there is no implicit locale fallback.

## Routes, publication, and sitemap

Canonical paths extend the already-reviewed category canonical prefix:

- English: `/{category_slug}/{brand_slug}/{model_slug}/`;
- Swedish: `/sv/{category_slug}/{brand_slug}/{model_slug}/`.

Every current page has its exact locale/path pair in `hreflang`. Model rows are
projected for navigation when their parent `api_public.models` row and exact
category-locale row exist. `indexable` is the conjunction of the model and
category decisions. Because the source lacks an approved model lifecycle, all
current model pages remain `indexable=false` and `published_at=NULL`;
`scrape_status` is never consulted. `updated_at` is the latest available public
lifecycle timestamp from the model, category page, or brand, currently NULL.

`api_public.sitemap_entries` is intentionally unchanged. Its contract admits
only indexable pages, so adding 43,332 known-false model-page rows would add no
sitemap entries while coupling two refresh lifecycles. Sitemap integration is
deferred until a reviewed model indexability gate can produce true rows.

## Materialization, privileges, and refresh

The measured ordinary projection took about 641 ms for the first ordered page
and 0.74 ms for a targeted model/locale lookup. The full enumeration cost
justifies a materialized projection. `api_public_owner` owns it; `anon` and
`authenticated` receive SELECT only; no public role can refresh or write it.

Refresh must follow its dependency order after source changes:

```sql
REFRESH MATERIALIZED VIEW api_public.models;
REFRESH MATERIALIZED VIEW api_public.model_pages;
```

Indexes enforce unique page UUID, unique model/locale, and unique canonical
path, and serve page-ID lookup, model/locale lookup, locale filtering,
indexability filtering, and canonical-path keyset scans.

## Rollback

In controlled development, revoke consumer SELECT, drop
`api_public.model_pages` (which removes its indexes), and delete migration
record `014`. Existing models, identities, foundation resources, raw source
tables, and migration-011 security revocations remain unchanged.

## Validation record

Target Guard accepted only the loopback `repair_appliance_dev` write target.
Migration 014 completed in an intentionally aborted transaction and left no
object or migration record, then applied atomically. The final projection has
43,332 rows, 43,332 unique page UUIDs, 43,332 unique model/locale pairs, and no
indexable rows. PostgREST exposes the exact contract through the `api_public`
profile and respects its configured 1,000-row cap.

Focused model-page, model, foundation, privilege, PostgREST, Target Guard, and
migration-011 regression tests pass in dev. The local offline suite also passes;
integration cases skip unless explicit loopback environment variables exist.

Warm final `EXPLAIN (ANALYZE, BUFFERS)` measurements:

| Query | Rows | Execution | Plan |
|---|---:|---:|---|
| Page UUID lookup | 1 | 0.132 ms | page-ID unique index |
| Model ID + locale lookup | 1 | 0.040 ms | model/locale unique index |
| Swedish locale page | 100 | 0.453 ms | locale/order index |
| Non-indexable page | 100 | 0.135 ms | indexability/order index |
| First ordered page | 100 | 0.117 ms | canonical order index |
| Next keyset page | 100 | 0.604 ms | canonical order index |
| Full refresh | 43,332 | 1,283.891 ms | ordered dependency refresh |

The ordinary-view first-page baseline was 640.643 ms with an external merge
sort; its targeted model/locale lookup was 0.741 ms. Materialization therefore
removes the catalog-scale join/sort from public requests at the cost of an
explicit roughly 1.3-second refresh after the models snapshot changes.
