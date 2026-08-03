# Cube Coverage & Backlog Worker

## Purpose

`cube-coverage` is the read-only coordinator for later content workers. It
freezes the current Brand × Category × Locale cube, measures explicit coverage
and records deterministic findings and proposed actions. It does not fill gaps.

## Scope snapshot

An active snapshot contains IDs/slugs for active brands and categories plus the
site's active locales. Product Line and Series are deliberately excluded. A
snapshot never expands automatically; `--scope new` is the explicit mechanism
for a later version. Only one snapshot is active per site/environment and old
snapshots are retained.

## Data and availability

The repository reads existing model, variant, product-code, translation,
fault, guide, relation, publication and evidence tables. Optional unavailable
sources are reported as `not_available`; they do not produce invented zeroes or
findings. `unknown` means the source exists but cannot establish the answer.
`not_applicable` means the rule has no valid denominator, for example a cube
cell with no expected pages.

## Coverage denominators

- Model overview: published meaningful overview divided by models with an
  explicit site publication for that locale.
- Model specs: meaningful, non-empty JSON specs divided by those same expected
  model pages. The initial policy expects specs only for public models.
- Empty cells have `not_applicable`, not 0%.
- Locale values are never inferred from another locale.

Each persisted metric stores numerator, denominator, percentage, definition,
availability, observation time and scope snapshot.

## Finding catalogue

The first detector version supports model overview/spec/placeholder defects,
explicit unresolved variant candidates, broken product-code identity,
error-code translation/description/placeholder defects, fault translation and
placeholder defects, guide translation/procedure/topic/placeholder defects,
exact duplicate procedure candidates, explicit relation conflicts and missing
evidence on verified evidence-required relations.

Absence is not automatically a defect. No variant, model-specific guide or
unique error code is required without an explicit applicability/publication
signal. Placeholder matching is deterministic: `coming soon`, `placeholder`,
`to be added`, `tbd`, and `lorem ipsum`.

Finding identity is SHA-256 over detector/version/type/entity/locale/predicate
version. Repeated observations update `last_seen_at`. Missing observations
resolve open/acknowledged findings. Resolved findings reopen when observed
again. Ignored and false-positive findings do not reopen automatically; a new
detector version creates a new identity and preserves history.

## Backlog and priority

A finding is an observation; backlog is a proposed action. Only mapped findings
create actions and at most one active finding/action pair exists. Conflicts are
blocked. Priority is transparent: critical=P0/100, high=P1/80,
medium=P2/55, low=P3/25. Risk is stored separately. Resolved findings defer
queued/blocked work rather than falsely completing it; reopened findings queue
that deferred work again. Completed work is never reopened automatically.

Supported actions are `create_model_overview`, `enrich_model_specs`,
`translate_error_code`, `describe_error_code`, `translate_fault`,
`create_or_enrich_guide`, `resolve_variant_mapping`,
`resolve_relation_conflict`, `add_source_evidence`, and
`remove_public_placeholder`. Additional specified actions are introduced only
when a concrete deterministic detector exists.

## Safety and idempotency

Content scanning runs in a PostgreSQL read-only transaction. Writes are limited
to `worker_runs`, `cube_scope_snapshots`, `cube_coverage_observations`,
`findings`, and `content_backlog`. These tables use forced RLS, are hidden from
anonymous/authenticated roles, forbid delete for service role and retain FK
history. A session advisory lock prevents concurrent runs for the same
site/environment/snapshot. Production is disabled. The package imports no HTTP,
LLM, Search Console, crawler or email client.

## CLI

```powershell
python -m workers cube-coverage --site appliance-repair-base --environment development --scope active --dry-run
python -m workers cube-coverage --site appliance-repair-base --brand bosch --category washing-machines --locale en --finding-type missing_model_overview --dry-run
python -m workers cube-coverage --site appliance-repair-base --fixture tests/fixtures/cube_coverage.json --output-dir reports/cube-coverage
```

Filters bound the analysis. `--rebuild-backlog` reconciles idempotently and
never deletes history. Reports are runtime artifacts under
`reports/cube-coverage/<run-id>.json|md` and are gitignored.

## Reports and consumers

JSON contains run/scope/timing/status, entity and cell counts, metrics,
findings, backlog, availability, warnings and errors. Markdown summarizes the
same run for humans. The future Source Discovery Worker reads queued/blocked
backlog rather than rescanning for loosely defined opportunities. A future
Daily Digest reads the same persisted runs/findings/backlog; this worker sends
no email and schedules nothing.

## Extending rules

Add a deterministic predicate to `CoverageEngine`, declare severity/action/risk
in `RULES`, increment detector version when semantics change, document the exact
required inputs and false-positive risk, and add offline plus integration
tests. Never add semantic AI comparison to this worker.

## Explicit exclusions

No internet, scraping, LLM, translation, content creation, entity discovery,
model grouping, publication status, URL/canonical/sitemap/redirect changes,
deployment, production access, scheduler or email.
