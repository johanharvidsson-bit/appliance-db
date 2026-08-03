# Public models API implementation

Migration `013_public_api_models.sql` adds only the language-independent
`api_public.models` resource. Model pages, canonical paths, locale, hreflang,
model specs, and frontend changes remain out of scope.

## Contract and sources

The projection joins `models` to active `brands` and `categories`, their frozen
rows in `api_public_identities`, and an optional matching `product_lines`
identity. It exposes the v1 contract fields in this exact order:

`model_id`, `brand_key`, `category_key`, `product_line_key`, `name`, `slug`,
`series`, `release_year`, `manual_url`, `indexable`, `updated_at`.

Internal numeric IDs, `base_model`, PDF paths/URLs, scrape state/timestamps, and
creation timestamps never cross the boundary. Default client ordering is
`name COLLATE "C" ASC, model_id ASC`; clients must request it explicitly.

## Identity

The existing `public.api_public_identities` mapping gains the `model` and
`product_line` namespaces plus a nullable UUID identity column. Initial model
identity is UUIDv5 over the frozen natural route tuple
`brand_key:category_key:slug`; the mapping is keyed by `(resource_type,
source_id)` and never updates on conflict. Consequently a later slug or name
change does not change `model_id`. Product-line keys are similarly frozen from
their initial brand/category/slug tuple. Raw source IDs are never exposed.

## Publication compatibility and safety

The current source schema has no reviewed model-publication flag, approved URL
state, model indexability decision, or public lifecycle timestamp. Migration
013 therefore does not reinterpret pipeline `scrape_status` as publication.
It projects only rows with active brand/category parents, a nonempty name, and
a lowercase route-safe slug. It fails closed for unresolved fields:

- `manual_url = NULL` until URL approval exists;
- `indexable = false` until model SEO eligibility is approved;
- `updated_at = NULL` until a public lifecycle timestamp exists.

## Privileges and indexes

`api_public_owner` owns the projection and receives only the source columns required
by the projection. It receives no model URL, local path, scrape, or timestamp
columns. `anon` and `authenticated` receive SELECT on the projection only and no
write privilege. Migration 011 denials and existing raw compatibility grants
are unchanged.

Measured ordinary-view plans joined tens of thousands of source/identity rows
for every request, so `models` is a materialized catalog projection. Six direct
projection indexes enforce UUID and route uniqueness and support deterministic
unfiltered, brand, category, combined-filter, and public-ID access. A unique
partial identity-map index also prevents UUID reuse. Refresh is an explicit
privileged operation after model/parent/identity changes:

```sql
REFRESH MATERIALIZED VIEW api_public.models;
```

## Rollback

In controlled development only, revoke public SELECT and drop
`api_public.models` (which removes its indexes); remove
`model` and `product_line` identity rows; drop the public-ID index and column;
restore the identity resource-type check to `brand` and `category`; revoke the
new model/product-line column grants; and remove migration record `013`.
Migration 012 resources and migration 011 security revocations remain intact.

## Validation record

Target Guard classified only the loopback `repair_appliance_dev` target as
development. Migration 013 first completed inside an intentionally aborted
transaction, proving rollback, and was then applied atomically. The final
projection contains 21,666 rows and 21,666 distinct model IDs. PostgREST exposes
it through the `api_public` profile with its configured 1,000-row cap.

Focused contract, identity, privilege, PostgREST, foundation, and migration-011
security tests pass in dev. The full offline suite also passes; integration
tests skip unless their explicit loopback environment variables are present.

Warm `EXPLAIN (ANALYZE, BUFFERS)` measurements on the final 21,666-row snapshot:

| Query | Rows | Execution | Plan |
|---|---:|---:|---|
| First ordered page | 100 | 0.275 ms | `api_public_models_order_idx` |
| Brand-filtered page | 100 | 0.186 ms | `api_public_models_brand_order_idx` |
| Category-filtered page | 100 | 0.135 ms | `api_public_models_category_order_idx` |
| Public UUID lookup | 1 | 0.037 ms | `api_public_models_id_uidx` |
| Next keyset page | 100 | 0.363 ms | ordered index scan |
| Full projection refresh | 21,666 | 597.208 ms | explicit privileged refresh |

All measured query buffers were shared hits except four initial index-page
reads across the filtered warm-up queries. The ordinary-view baseline was
390 ms for the first page and 733 ms for the measured next-page shape, which is
why the materialized projection is evidence-based rather than speculative.
