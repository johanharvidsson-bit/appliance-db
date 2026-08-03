# Next-site technical readiness

This delivery completes the local platform gates required before beginning a second site's frontend. It does not deploy production, crawl a website, migrate a real URL, or publish real content.

## Delivered gates

1. **Information model and URL preservation** — migrations 015–016 retain entity/URL identity separately and add the normalized v1 knowledge model.
2. **Deterministic profiling** — bounded model/variant candidates remain non-authoritative and idempotent.
3. **Frontend compatibility** — migration 017 exposes only published/verified content through security-barrier `api_public` views. Candidate, evidence, confidence, reviewer and raw source fields are excluded.
4. **Guide reuse** — the local guide pilot stores one reusable procedure, evidence-backed topic relations and explicit reviewed publication. Empty/placeholder content cannot be published.
5. **Worker runtime** — migration 018 and `pipeline.worker_runtime` provide idempotent batches/jobs, dry-run, leasing, retries, dead-letter state, candidate observations, audit events and non-destructive rollback.
6. **Multisite presentation boundary** — migration 019 adds site contracts, active locales, site-scoped entity publication and site-scoped canonical URLs/sitemaps. Knowledge entities remain shared.
7. **Starter contract** — `site_templates/example-next-site.json` defines identity, domain, vertical, locales, routes and minimum design tokens independently of a frontend framework.
8. **End-to-end isolation** — the synthetic pilot publishes a shared model only on the example site; Appliance Repair Base receives no publication or sitemap row. Cross-site canonical assignment is rejected.

## Start gate

Run against only the isolated local database:

```powershell
$env:REPAIRBASE_SECURITY_TEST_DB_URL = 'postgresql://postgres@127.0.0.1:15432/repair_appliance_dev'
python -m pipeline.audit_next_site_readiness `
  --contract site_templates/example-next-site.json `
  --output next-site-readiness.json
```

The next frontend may start only when the audit reports `"ready": true` and the full test suite passes.

## What remains intentionally outside this gate

- selecting the real next-site domain, vertical and visual identity;
- approving its real Site Contract;
- production infrastructure, secrets and deployment;
- real content/source ingestion;
- Search Console or analytics setup;
- real URL inventory, redirects, canonicals or sitemap migration;
- production backfills for model variants or guides.

Those are launch activities, not blockers for beginning implementation of the next frontend.
