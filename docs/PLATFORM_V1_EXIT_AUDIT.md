# RepairBase Platform v1 exit audit

Audit date: 2026-08-03. Scope is code and local build validation only. No
production system, DNS, Cloudflare configuration, or deployed database was
changed.

| Exit criterion | Result | Evidence |
| --- | --- | --- |
| New site registration without copied application code | Pass | Marine is a registry entry using shared frontend/provider code. |
| Separate database and PostgREST per site | Code-complete, runtime pending | Marine Compose defines its own database, volume, PostgREST, and loopback ports. It was config-validated but not started. |
| Frontend uses provider interface | Pass | Foundation routes and sitemaps use `RepairBaseDataProvider`; contract tests prevent raw foundation access. |
| New verticals use only `api_public` | Pass in configuration | Marine selects `PublicApiDataProvider`; PostgREST exposes only `api_public`. |
| Appliance legacy is isolated | Pass | Legacy client rejects every non-Appliance site; remaining consumers are inventoried. |
| Unknown sites and hosts fail closed | Pass | Registry and request-host tests cover unknown keys/hosts and site/build mismatch. |
| API targets validate per site | Pass | Target identity/hostname, exact schema, and cache namespace are validated. |
| Cache is site-isolated | Pass | Keys include site, namespace, locale, resource, path, and normalized query; responses vary on Host. |
| Robots, canonical, sitemap are site-aware | Pass | Production indexing is explicit; Marine/dev is noindex; foundation pages use Public API canonical data. |
| Foundation contract and privilege tests | Runtime execution pending | Resources 015–018 now have dev-integration suites for exact contracts, identity, relations, publication, privileges, PostgREST pagination/filtering, and query plans. All SQL 011–018 parses successfully offline, but the new suites have not run against an approved dev DSN/PostgREST. |
| Appliance has no SEO/routing regression | Pass at build/test level | Provider, foundation, multisite, raw-access tests and Appliance build are green. No browser/deployed smoke test was run. |
| Small new vertical renders from own dev data | Build pass, live proof pending | Marine build is green and seed is exactly 3 categories/5 brands/50 models. Live rendering requires approved dev credentials and starting the isolated stack. |

## Release decision

Platform v1 is **not yet runtime-certified**. The implementation and isolated
pilot artifacts are complete, but two operational proofs remain intentionally
unperformed because this work was not authorized to create credentials or
deploy/start infrastructure:

1. supply approved Marine dev credential values, apply migrations 011–018 to the isolated Marine dev database, and run all
   Postgres/PostgREST privilege, contract, pagination, and performance tests;
2. run the Marine frontend against that PostgREST instance and smoke-test
   representative category, brand, model, canonical, sitemap, robots, unknown
   host, and cross-site cache cases.

These are release gates, not code TODOs. After an operator supplies approved
development-only credentials, execute the commands documented in
`pilots/marine/README.md`; do not use production credentials or targets.

The Compose manifest has been rendered successfully without starting services.
Its initialization order now bootstraps non-login API roles and a dedicated
`marine_postgrest` login before schema creation. The repository contains no
credential values.

## Canonical branch stacks

Backend:

```text
origin/main
 -> feature/public-api-fault-pages
 -> feature/public-api-error-codes
 -> feature/public-api-article-pages
 -> feature/public-api-model-specs
 -> feature/marine-dev-pilot
 -> audit/platform-v1-exit
```

Frontend:

```text
feature/frontend-data-provider-foundation
 -> feature/frontend-foundation-resource-migration
 -> feature/frontend-multisite-runtime
 -> security/frontend-raw-access-audit
 -> feature/frontend-marine-dev-pilot
```

Keep PRs in this order. Do not merge a child before its base or retarget it to
skip unmerged dependencies.
