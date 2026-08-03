# Internal table access review

Date: 2026-08-02. Scope: the isolated `repair_appliance_dev` database and the
backend/frontend source trees on the VPS. Production was not contacted.

## Observed database boundary

PostgreSQL 16.14 runs in `repairbase-dev-postgres` on ARM64. The database is
`repair_appliance_dev`; `public` is owned by `pg_database_owner`, and all 24
tables are owned by `postgres`. RLS is enabled (not forced) on every table.
Before migration 011 every table had explicit `SELECT` grants to `anon` and
`authenticated`, plus one permissive `FOR SELECT TO public USING (true)` policy.
`service_role` has separate table privileges and `BYPASSRLS`. Neither candidate
is referenced by a view or function, and the inspected roles have no inherited
role memberships.

Frontend evidence is from `/opt/repairbase/appliance-theme/src`, principally
`src/lib/queries.ts` plus routes and sitemaps. Backend evidence is from `db/`,
`pipeline/`, and `scrapers/`. “No” means no source reference was found in that
scan; it does not claim knowledge of undocumented external consumers.

## Classification

The pre-migration privilege/policy shorthand below is `anon SELECT; authenticated
SELECT; RLS on; public SELECT policy true` for all rows.

| Table | Frontend reference found / evidence | Backend/service use | Worker/pipeline use | Current anon privilege | Current authenticated privilege | Current RLS/policy | Classification | Confidence | Immediate action | Target state after api_public | Rollback impact | Open dependency |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| article_translations | yes — `src/lib/queries.ts`, index and sitemap routes | no direct backend runtime dependency found | yes — article production/audit pipelines | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | projected article pages only | current frontend fails if revoked now | sanitizer and projection design |
| articles | yes — `src/lib/queries.ts` | no direct service dependency found | yes — article pipelines | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | projected article pages only | article/fault routes fail | public field set pending |
| authors | no | schema relation from articles | no source use found | SELECT | SELECT | on / public read true | unknown_dependency | medium | defer | expose only projected attribution if needed | possible attribution/embed break | confirm intended author UI |
| brands | yes — `src/lib/queries.ts`, brand routes and sitemaps | no direct service dependency found | yes — most pipelines | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | `api_public.brands` | navigation/build fails | none for current scope |
| categories | yes — `src/lib/queries.ts` and routes | no direct service dependency found | yes — pipelines | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | localized category projection | routing/build fails | stable public identity design |
| category_translations | yes — `src/lib/queries.ts`, routes and sitemaps | no direct service dependency found | yes — translation pipelines | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | localized category projection | localized routes fail | locale fallback contract |
| error_code_parts | no | schema junction | scraper/article payloads may describe parts but no confirmed public query | SELECT | SELECT | on / public read true | unknown_dependency | medium | defer | omit or constrained projection | possible undocumented relation embed break | confirm external embeds |
| error_code_product_codes | no direct frontend query | schema junction | yes — `scrapers/pdf_extractor.py` writes it | SELECT | SELECT | on / public read true | server_only | high | defer | omit from public API unless proven | scraper unaffected with service role; external risk unknown | check undocumented consumers |
| error_code_symptoms | no | schema junction | no confirmed runtime use | SELECT | SELECT | on / public read true | unknown_dependency | medium | defer | constrained projection if needed | possible relation embed break | confirm intended symptom API |
| error_codes | yes — `src/lib/queries.ts` | no direct service dependency found | yes — extraction/enrichment pipelines | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | later error-code projection | error-code pages fail | explicitly outside foundation PR |
| fault_error_code_map | yes — `src/lib/queries.ts` | no direct service dependency found | yes — mapping/audit pipelines | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | later fault/error projection | related-code UI fails | explicitly outside foundation PR |
| fault_translations | yes — fault page queries | no direct service dependency found | yes — fault/article pipelines | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | later fault projection | localized fault pages fail | explicitly outside foundation PR |
| faults | yes — `src/lib/queries.ts` | no direct service dependency found | yes — fault/article pipelines | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | later fault projection | fault routes and sitemap fail | explicitly outside foundation PR |
| locales | no; frontend locales are code-defined | schema foreign-key reference | pipelines store locale codes | SELECT | SELECT | on / public read true | unknown_dependency | medium | defer | omit or expose constrained active locales | possible undocumented lookup break | decide canonical locale source |
| model_specs | yes — `src/lib/queries.ts` | no direct service dependency found | yes — `pipeline/scrape_specs.py` | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | later model-page projection | model specs disappear | normalization outside foundation PR |
| models | yes — `src/lib/queries.ts` and routes | no direct service dependency found | yes — scrapers/pipelines | SELECT | SELECT | on / public read true | frontend_required_now | high | keep | later model-page projection | model routes/build fail | explicitly outside foundation PR |
| parts | no | schema entity | parts scrapers/payloads exist, but no confirmed public read | SELECT | SELECT | on / public read true | unknown_dependency | medium | defer | constrained commerce projection if required | possible undocumented parts consumer break | verify planned parts surface |
| product_codes | no direct frontend query | no server endpoint found | yes — `pipeline/run_all.py`, several scrapers | SELECT | SELECT | on / public read true | server_only | high | defer | omit from initial public API | workers retain service access; unknown external impact | check undocumented consumers |
| product_lines | no | schema/model relation | populated by backend workflows | SELECT | SELECT | on / public read true | server_only | medium | defer | expose only via later model projection | possible model relation embed break | confirm embed usage |
| schema_migrations | no | yes — `db/apply_migration.py` via privileged direct DB connection | migration runner only | SELECT | SELECT | on / public read true | server_only | high | revoke | no public exposure | public migration metadata reads fail; intended | none found |
| scrape_jobs | no | worker bookkeeping | yes — `scrapers/base_scraper.py` via server client | SELECT | SELECT | on / public read true | server_only | high | revoke | no public exposure | anonymous job inspection fails; intended | none found |
| symptom_translations | no | schema entity | no confirmed runtime use | SELECT | SELECT | on / public read true | unknown_dependency | medium | defer | later constrained symptom projection | possible undocumented symptom consumer break | verify planned symptom surface |
| symptoms | no | schema entity | no confirmed runtime use | SELECT | SELECT | on / public read true | unknown_dependency | medium | defer | later constrained symptom projection | possible undocumented symptom consumer break | verify planned symptom surface |
| washing_machine_specs | no; comment in `src/lib/queries.ts` says superseded | migration 010 backfill source only | current scraper targets `model_specs` | SELECT | SELECT | on / public read true | unused_or_legacy | high | defer | no public exposure after retirement decision | legacy consumers may break | establish retention/drop gate |

## Migration 011 decision

Only `scrape_jobs` and `schema_migrations` meet the high-confidence bar. Both are
internal, absent from frontend routes/sitemaps/queries, have privileged internal
callers, and have no referencing view/function. Migration 011 drops exactly:

- `public read scrape_jobs`
- `public read schema_migrations`

It revokes `SELECT` on both tables from `anon` and `authenticated`. Ownership and
all existing `service_role` privileges remain unchanged. No additional table is
changed; all other candidates are deferred.

## Rollback (do not run during forward validation)

This restores only the state observed immediately before migration 011:

```sql
BEGIN;
GRANT SELECT ON TABLE public.scrape_jobs TO anon, authenticated;
GRANT SELECT ON TABLE public.schema_migrations TO anon, authenticated;
CREATE POLICY "public read scrape_jobs"
  ON public.scrape_jobs FOR SELECT TO public USING (true);
CREATE POLICY "public read schema_migrations"
  ON public.schema_migrations FOR SELECT TO public USING (true);
DELETE FROM public.schema_migrations WHERE version = '011';
COMMIT;
```

The rollback reopens the original exposure and should require a separate,
explicitly targeted change. It was documented but not executed.

## Dev validation after migration 011

Target Guard accepted the loopback write target only after it resolved to
`repair_appliance_dev`. Migration syntax was first executed inside a transaction
and rolled back, then applied atomically to that dev database. Catalog checks
showed no remaining policy on either internal table; `has_table_privilege`
returned false for `anon` and `authenticated` and true for `service_role`.

PostgREST returned denial statuses for both tables (401 for anonymous and 403
for an authenticated-role JWT). Anonymous control reads returned 200 for
`brands`, `categories`, `category_translations`, `models`, `articles`, and
`article_translations`. Direct-role integration tests produced the same result.

All application-table counts were identical before and after. In particular,
`scrape_jobs` remained 248,308 rows. `schema_migrations` changed from 9 to 10
rows solely because migration 011 recorded its own `(011,
011_revoke_internal_public_access.sql)` history entry; no other row count or
table structure changed.

## Next possible revoke candidates

`error_code_product_codes`, `product_codes`, and possibly `product_lines` are
likely server-only. `washing_machine_specs` is legacy. None belongs in this PR:
external PostgREST dependencies have not been disproved and focused regression
coverage is absent. All therefore remain `defer`.
