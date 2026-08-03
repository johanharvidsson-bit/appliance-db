# Source Discovery Worker (PR 2A)

## Responsibility

`source-discovery` reads queued `content_backlog` items and proposes source
URLs. It records candidates only. It never opens result pages, parses HTML/PDF,
extracts facts, creates content, resolves entities or publishes data.

The Source Ingestion Worker is deliberately a later PR.

## Search and priority

The initial provider uses Serper's JSON search API. Queries contain only the
existing brand/entity/locale/action context. Candidate pages are not fetched.

Deterministic tiers:

1. Manufacturer/support/manual: 90–95.
2. Official/recognizable parts source: 80.
3. Service manual: 60–70.
4. Verifiable major retailer: 45.
5. Forum: 25, candidate only.
6. Other result: 35.

Confidence is a source-likelihood heuristic, not a truth or content-quality
score. Discovery never automatically accepts a candidate.

## Persistence and lifecycle

`source_candidates` is unique by site, environment, backlog item and normalized
URL. A no-result search creates one stable `not_found` record. Repeated runs
update `last_seen_at`; they do not duplicate rows. Candidate rediscovery may
refresh candidate metadata but never overwrites `accepted` or `rejected`
decisions. All FKs use `ON DELETE RESTRICT`.

`source_discovery_cache` stores JSON search results by provider/query hash with
a seven-day default TTL. It does not store fetched documents because this
worker never fetches documents.

## Runtime safeguards

- development is default and production is disabled;
- advisory lock per site/environment;
- bounded batches, timeout, bounded exponential retry and rate limit;
- only queued backlog is scanned;
- existing entity joins supply brand/model/error/fault/guide context;
- no new brand, category, locale or model is possible;
- source tables are forced-RLS internal tables with no anonymous access;
- dry-run and fixture runs write reports only.

## CLI

```powershell
$env:SERPER_API_KEY = '<local secret>'
python -m workers source-discovery `
  --site appliance-repair-base `
  --environment development `
  --dry-run `
  --batch-size 25 `
  --timeout 10 `
  --retries 2 `
  --rate-limit 1
```

Filters: `--locale`, `--action-type`, and `--entity-type`.

Offline verification:

```powershell
python -m workers source-discovery --site appliance-repair-base `
  --fixture tests/fixtures/source_discovery.json
```

Reports are written to `reports/source-discovery/<run-id>.json|md` and are
gitignored. They contain backlog scanned, candidate count, accepted, rejected,
not-found and per-item query/candidates. Accepted/rejected remain zero until a
separate review workflow changes those statuses.

## Explicit exclusions

No scraping, HTML/PDF parsing, document download, facts, translations, LLM,
entity resolution, relation creation, publication, URL migration, scheduler,
email, deployment or production access.
