# PR 2 — additive information-model v1 foundation

Migration `016_information_model_v1_foundation.sql` implements the remaining Spec 0 v1 database foundation. It is additive, transactional, performs no business-data backfill, and changes no public URL, canonical, sitemap, redirect, or frontend behavior.

## Added foundation

- structured model variants and legacy-model mapping/audit tables;
- model, error-code, fault, and guide localization/publication fields;
- reusable guides and candidate/verified relation tables;
- immutable source identity and field-level evidence;
- model-level applicability overrides;
- separately approved URL redirects;
- variant/guide URL bindings and nullable product-code variant mapping;
- shared server-authoritative `updated_at` trigger;
- cross-scope, publication, evidence, and redirect activation constraints;
- forced RLS with no `anon` or `authenticated` base-table access.

The migration creates no variants, mappings, guides, relations, evidence, redirects, or classifications. Candidate generation and reviewed backfill belong to later PRs.

## Local verification

Use only the isolated loopback database:

```powershell
$env:REPAIRBASE_SECURITY_TEST_DB_URL = 'postgresql://postgres@127.0.0.1:15432/repair_appliance_dev'
python -m pytest -q tests/test_information_model_v1_foundation.py
```

The integration suite validates schema shape, forced RLS, grants, retained-table alterations, server timestamps, deferred cross-scope constraints, guide publication rules, evidence immutability, extended URL bindings, and fail-closed redirect activation.

## Rollback

Do not reverse an applied production migration with ad-hoc destructive SQL. Before any reviewed follow-up migration, export audit/history tables and prove that no later migration or candidate data references the v1 foundation. URL registry and binding history must be preserved.
