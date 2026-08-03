# RepairBase Worker Platform — Phase 0 discovery

Date: 2026-08-03

Scope: read-only repository inspection; no database query, crawl, email, deployment, or scheduler activation

Data repository: `C:\Users\Admin\appliance-db` at `19440be`

Frontend repository: `C:\Users\Admin\appliance-theme` at `ed0128a`

## Summary

Phase 0 is complete. Phase 1 should not be delivered as one pull request. The requested runtime, inventory, findings, digest, email, schema, and test work crosses two repositories and introduces several new persistence contracts. Implement it as the three pull requests described below, beginning in `appliance-db` and treating `appliance-theme` as a read-only source of URL/rendering rules until a deliberately scoped frontend change is needed.

No production system was contacted or changed. No external HTTP request or email was made. No secret was read into the report.

## Architecture discovered

### Backend and runtime

- `appliance-db` is a Python batch/scraping repository, not a web API service. Commands are primarily `python -m ...` modules using `argparse`.
- Dependencies include Supabase Python, PostgREST access, psycopg2, requests/httpx, Beautiful Soup, tenacity, Loguru, and pytest.
- `config/settings.py` eagerly loads `.env`, requires `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`, constructs a service-role Supabase client, creates local data/log directories, and configures daily rotating Loguru files.
- Existing orchestration is synchronous CLI/batch (`pipeline.run_all`, `pipeline.overnight_run`). There is no general queue, worker contract, advisory-lock abstraction, cron manifest, or systemd unit in the repository.
- Scrapers already implement pieces worth reusing: bounded retries/rate delay, structured-ish Loguru events, and `scrape_jobs` lifecycle records. `scrape_jobs` is scraper-specific and is not sufficient for cross-worker run metadata.

### Database and migrations

- Database is Supabase Postgres. Most application reads/writes use PostgREST via the service-role client.
- DDL is applied with `db/apply_migration.py` over a direct psycopg2 URL (`SUPABASE_DB_URL`). Migrations are ordered SQL files and recorded in `schema_migrations`.
- The checked-in baseline schema and migration history are currently not perfectly aligned: later tables such as faults/specs live in migrations, and the active working tree outside this discovery worktree contains uncommitted schema/migration work. A worker PR must rebase and reconcile migration numbering before adding tables.
- Public data access is effectively the Supabase/PostgREST schema consumed directly by the frontend. Worker tables should be internal and protected with explicit grants/RLS rather than being accidentally exposed to anonymous clients.

### Frontend and API contracts

- `appliance-theme` is Astro 5 with TypeScript and Tailwind, deployed through the Cloudflare adapter. It is currently on `main`; another worktree exists for multisite foundation work.
- There is no bespoke backend HTTP API. `src/lib/queries.ts` queries Supabase tables directly, so database columns and publication-state conventions are the practical API contract.
- Pages are server-rendered/on-demand. The shared route `/{category}/{brand}/{slug}/` resolves an article first, then a model. Fault guides have a separate `/problems/{slug}/` route. Swedish routes add `/sv/`.
- Sitemap endpoints query the database independently. Model sitemap inclusion is based on model rows joined to active brands; renderability additionally depends on category/brand/slug resolution and runtime query success. Therefore sitemap membership and renderability can differ.
- Page metadata supplies a self canonical for resolved article/model pages, an H1, breadcrumbs, and conditional Product/HowTo/FAQ schema. There is no redirect/alias table or explicit legacy-URL contract in either repository.
- No admin/reporting view was found.

### Logging, guards, tests, and notifications

- Logging uses Loguru with daily rotation and 30-day retention. Scrape errors may be persisted to `scrape_jobs.error_log` with caps.
- Guard patterns are local and inconsistent: several apply scripts default to preview unless `--apply` is supplied, and some explicitly block a retired Supabase host. There is no shared environment enum or production-target guard.
- Tests are pytest-based but sparse (one focused cleanup-model test module in the inspected base). There is no common fixture/fake Supabase layer.
- No SMTP client, transactional email provider, notification abstraction, email templates, or scheduler configuration was found. `.env`/`.env.example` is the existing secret/config pattern. A provider-neutral SMTP adapter is therefore appropriate, with a file transport as default in tests and dry-runs.

## Content architecture and systems of record

| Concept | Current representation | Discovery conclusion |
|---|---|---|
| Brand | `brands` | `id`, `name`, unique `slug`, active/scrape state |
| Category | `categories` plus frontend-observed `category_translations` | English slug is on `categories`; localized routing uses translations |
| Series | `models.series` | Derived by `pipeline.populate_series`; grouping aid, not a separate entity |
| Main model | `models.base_model` | Base identifier is text before `/`; no separate main-model row/aggregate contract |
| Model variant | `models.name`/`product_codes.code`, with suffix and market | Variants are currently capable of being separate model/page rows; this conflicts with the target principle and must be normalized before variant findings are authoritative |
| Fault | `faults`, `fault_translations`, `fault_error_code_map` | Brand/category scoped deterministic entity |
| Error code | `error_codes`, `error_code_product_codes` | Brand/category scoped and related to product codes |
| Repair guide/article | `articles`, `article_translations` | Publication is split between article status and translation status; frontend recognizes locale-specific published states |
| Part | No first-class parts table found | Only spare-parts presentation/links; report as unavailable |
| Specification | Generic `model_specs` in current frontend and pending local migration work | Keyed to a model, JSON specs payload |
| Related model | Same `series` in frontend | No explicit relation table; may over-group |
| Public URL | Derived in Astro from locale/category/brand/entity slug | Not persisted as a single source of truth |
| Canonical URL | Derived from request/site config | Self canonical on successfully resolved pages |
| Sitemap inclusion | Dynamic Astro sitemap query functions | Independent from actual HTTP/render success |
| Publication status | Article and translation status; models lack a publication flag | Model existence plus active brand currently approximates publishability |

The authoritative existence source for models is the `models` table. The stable technical identifier is `models.id`; the human/product identifier is `name`, with `base_model` derived by splitting before `/`. `product_codes` holds market-specific identifiers. Model slugs are stored in `models.slug`; ingestion creates/uses them, while the frontend does not regenerate model slugs. Article slugs are locale-specific in `article_translations`.

There is no verified alias/redirect source. Old variant URLs therefore cannot safely be classified as legacy redirects from repository data alone. The first inventory implementation must label alias state `not_available` and must not infer redirects.

## Existing patterns to reuse

1. Python module CLI and `argparse` conventions.
2. Loguru, but bind a stable structured context (`run_id`, worker, site, environment) and serialize JSON for worker logs.
3. Tenacity/request timeout patterns, after enforcing hard caps centrally.
4. Supabase PostgREST for bounded observation reads and ordinary persistence; psycopg2 only where a transaction/advisory lock is required.
5. SQL migration files plus `schema_migrations` tracking.
6. Existing Astro query functions as the specification for URLs, sitemap inclusion, and publication behavior—not by importing frontend code at runtime.

Do not reuse `scrape_jobs` as `worker_runs`: its target/source/raw-payload shape and retry lifecycle are scraper-specific.

## Design decisions for Phase 1

- Place the new package at `workers/` in `appliance-db`, with a single `python -m workers ...` entry point.
- Fix `site_id` to the configured ApplianceRepairBase identifier for this phase; validate rather than generalize to arbitrary verticals.
- Default to `environment=development`, `dry_run=true`, and external HTTP disabled. Production requires both `--environment production` and an explicit allow variable/flag.
- Separate read-only source access from analyst-table writes. “Read-only” means no mutation of content/publication tables; worker metadata, observations, findings, and delivery records are allowed only through repository classes scoped to those tables.
- Use Postgres advisory locks derived from `(site_id, environment, worker_name)`. Hold a dedicated psycopg2 connection for the full run and always release it in `finally`. A lock conflict exits distinctly and is recorded where possible.
- Use UUID run IDs. Use canonical JSON plus SHA-256 for input, observation, finding, recipient-set, and digest-content hashes.
- Keep detector logic pure and offline-testable. Persistence performs upsert by stable finding identity and lifecycle transitions; ignored/false-positive records are not silently reopened.
- Inventory internal DB rows first. Optional HTTP enriches a bounded batch with a named user agent, concurrency cap, timeout, and retry cap. No full-site crawl.
- Treat sitemap as another bounded input set. Preserve `unknown`/`not_available` instead of manufacturing values.
- Build digest aggregation around a stable report dataclass that already includes future publishing counters as zero/nullable fields.
- Add SMTP only in PR 3. TLS verification remains enabled; no insecure fallback. File transport is the default for dry-run/testing. Delivery deduplication is persisted; resend requires `--force-resend`.

## Proposed database changes

PR 1 should add `worker_runs` and a transactional/advisory-lock helper function only if direct locking cannot be held safely from the CLI connection.

PR 2 should add `site_inventory_observations` and `findings`, including uniqueness/indexes on scope plus hashes and constrained lifecycle/severity values.

PR 3 should add `digest_deliveries`, uniquely scoped by site, environment, report date/period, recipient-set hash, and successful delivery identity. Dry-runs must never create a successful-delivery record.

All tables require comments, timestamps, JSONB defaults, indexes for digest windows, and explicit denial of anonymous/public writes. No existing public table or frontend query contract should change.

## Exact pull-request decomposition

### PR 1 — Worker runtime foundation (`appliance-db` only)

- Rebase after the current schema/migration work is settled; allocate the next migration number.
- Add `workers/context.py`, `result.py`, `runtime.py`, `locks.py`, `repository.py`, `logging.py`, `cli.py`, and `workers/__main__.py`.
- Add `worker_runs`, typed statuses/modes, advisory locking, run finalization, redacted error summaries, timeout/retry helpers, exit codes, dry-run/read-only/production guards.
- Avoid importing `config.settings` at module import in pure/runtime tests; load and validate settings explicitly.
- Add offline tests covering every runtime case listed in the task using fakes and a controllable clock.
- Update `.env.example` and add operator documentation. Do not apply the migration to production.

Acceptance gate: all runtime tests pass offline; two same-scope workers cannot overlap; a thrown exception releases the lock; production is rejected unless explicitly enabled; no content table can be written through the worker repository.

### PR 2 — Inventory and findings (`appliance-db`, frontend read-only reference)

- Add internal entity inventory from Supabase and URL derivation matching Astro routes for EN/SV.
- Add optional bounded sitemap/HTTP probes and HTML metadata parsing.
- Persist immutable/append-or-upsert observations keyed by observation hash and observation time policy.
- Add findings lifecycle and only detectors supported by evidence: initially `sitemap_url_non_200`, `entity_url_non_200`, `canonical_target_non_200`, `missing_canonical`, `missing_h1`, `duplicate_title`, `duplicate_meta_description`, and `missing_breadcrumb` when HTTP is enabled. Entity relation detectors must wait for a clarified main-model/variant contract.
- Document each detector's exact predicate, severity, prerequisites, false positives, and human action.
- Add fixtures for sitemap/HTML/DB pages and all requested lifecycle/isolation tests.

Acceptance gate: no production crawl by default; every network and row count is bounded; reruns are idempotent; absent observations resolve only findings owned by the same detector/scope after a complete bounded evaluation, never after partial failure.

### PR 3 — Daily digest and email (`appliance-db` only)

- Add Europe/Stockholm-aware aggregation with explicit interval overrides and DST tests.
- Add stable report contract, responsive HTML and plain-text renderers, synthetic examples, and truncation.
- Add provider-neutral SMTP and file transports; recipients/from/subject prefix come only from validated configuration.
- Add delivery persistence, content/recipient hashes, idempotent send, explicit force resend, redacted errors, and `completed_with_delivery_error` handling.
- Add inactive example systemd service/timer files (preferred after host verification) or cron documentation. Proposed order: inventory 01:00, findings 02:00, digest 07:00 Europe/Stockholm. Digest reports still-running jobs rather than waiting indefinitely.

Acceptance gate: tests never send real mail; dry-run writes an artifact but no sent marker; identical successful periods are suppressed; critical findings or failed runs add the action-required subject prefix.

## Scheduling proposal

Prefer systemd timers only after confirming the production host uses systemd and documenting its deployment user, working directory, virtual environment, environment-file permissions, and persistent timer behavior. Commit templates with `ConditionPathExists`/explicit environment files, randomized delay if useful, and finite runtime limits. Do not install or enable them as part of these PRs.

## Risks and limitations

- Current variants are not modeled solely beneath a main-model entity; pages can exist per variant row. Rules such as `variant_not_linked_to_main_model`, `duplicate_main_model_candidate`, and legacy variant URL findings would be speculative today.
- Models have no publication status, so inventory must distinguish “entity exists,” “included by sitemap query,” and “HTTP-renderable” rather than collapse them into published/unpublished.
- Direct frontend-to-Supabase access makes grants/RLS on new analyst tables security-critical.
- The eager service-role configuration makes accidental production access too easy for a worker package unless settings are redesigned for explicit loading.
- The baseline schema is moving in the original worktree. New migration numbers must not be chosen until that work lands or is abandoned.
- No alias/redirect registry, admin URL, email provider, scheduler, or production-host runtime was discoverable from the repositories.
- This inspection did not validate live database contents, deployed sitemap output, HTTP behavior, RLS policies, Supabase scheduled jobs, or host services.

## Recommended next PR

Proceed with PR 1 only after reconciling the uncommitted migration/schema changes in the original `appliance-db` worktree. Source Ingestion should later live in `appliance-db` as its own bounded ingestion package feeding structured source/evidence tables; it should not be coupled directly to findings or publishing. Search Console and Index Coverage should likewise enter through versioned observation tables and independent workers. Publication and rollback logs should become additional digest inputs, not email-specific fields or direct worker chains.

## Out of scope and unchanged

No LLM generation, content mutation, public API change, publishing, canonical/title/H1/schema/sitemap change, Search Console credentials, email credentials, real email, crawl, deployment, DNS/Cloudflare operation, production migration, or scheduler activation was performed.
