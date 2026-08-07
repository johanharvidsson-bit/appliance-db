# Retired branches

26 branches audited and retired during the 2026-08 platform reconciliation.
Every one was tagged (`retired/<branch-name>`) before deletion, so nothing is
actually lost - `git show retired/<name>:<path>` still works on any of them.
Two branches were reviewed and deliberately *not* retired; see the bottom.

## Individual worker branches, fully merged (11)

`codex/feature/apply-integration-worker`, `content-assembly-worker`,
`content-validation-safety-worker`, `cube-coverage-backlog-worker`,
`knowledge-integration-worker`, `source-discovery-worker`,
`source-ingestion-enrichment-worker`, `codex/information-model-v1-foundation`,
`codex/model-variant-profiler-pilot`, `codex/next-site-readiness`,
`codex/url-baseline-entity-bindings`

Each one built a single worker or foundation piece and was merged into
`integration/worker-pipeline-pilot` in the normal course of development -
confirmed via `git merge-base --is-ancestor` before deletion. Ordinary
merged-feature-branch cleanup, not part of the design sprawl.

## Superseded/duplicate content (5)

- `codex/article-content-expansion` - the real content (article batches,
  apply script) already landed via different commits; only stale
  intermediate backup/tracker files were unique to this branch.
- `codex/information-model-v1` - single doc commit, byte-identical to
  `docs/information-model-v1.md` already on the canonical branch.
- `codex/worker-platform-discovery` - a "Phase 0" planning doc proposing
  table names (`worker_runs`, `site_inventory_observations`) that don't match
  what actually shipped (`worker_batches`, `worker_jobs`, migrations
  018-027) - superseded by the real implementation, not by intent.
- `feature/public-api-foundation`, `security/revoke-internal-public-access` -
  each is the literal source commit of migrations 012 and 011 respectively;
  diffed tree-identical against the canonical branch, contribute nothing
  beyond what's already there.

## The abandoned "Platform v1" design (8)

`feature/public-api-fault-pages`, `public-api-error-codes`,
`public-api-article-pages`, `public-api-model-specs`, `feature/public-api-models`,
`feature/marine-dev-pilot`, `audit/platform-v1-exit`,
`design/public-api-contract-v1`

A full alternate multisite architecture built 2026-08-03, the same day the
canonical branch independently built its own (migration 019's
`sites`/`site_entity_publications`/`api_public.*` views) and went a different
direction. This stack's own exit-audit doc (`platform-v1-exit`) calls it
"code-complete but not runtime-certified" - never applied against a real
database. `marine-dev-pilot` validated the pattern with 50 synthetic
"Marine Pilot Model" rows, not real content. `public-api-contract-v1`'s
design ideas were manually read and hand-implemented into migrations
011/012, then the architecture moved on past its roadmap. Retired as a
coherent unit; nothing here disagrees with anything currently live.

## Confirmed fully-merged, no further content (2)

`reconciliation/backend-source-recovery`, `stabilization/settings-and-target-guard`

## Deliberately NOT retired

- **`feature/public-api-model-pages`** - one real, small (~30 line),
  well-documented unmerged decision: flip `api_public.model_pages.indexable`
  from conditional to unconditionally `true`, affecting ~43,000 pages'
  search-indexability. Needs a product decision, not deletion.
- **`codex/feature/outboard-staging-runtime`** - real, currently-running
  infrastructure behind outboardrepairbase.com (a standalone Node.js app +
  its own `rb_`-prefixed Postgres schema). Not part of this reconciliation;
  see Phase 3 (bootstrap outboardrepairbase on the standard platform schema)
  for its resolution path.

## The other half of the sprawl: frontend

A separate, unmerged 7-branch stack in what is now `web/` (previously the
`appliance-theme` repo) built a competing, more complete site-registry design
(`siteRegistry`/`resolveSite()`, a pluggable data-provider abstraction). Its
`SESSION_HANDOFF.md` explicitly flagged it as a stop-gate pending four
unanswered questions, then it was committed and pushed the next day anyway.
Not retired outright - its fail-closed resolution pattern was reimplemented
cleanly against the current site config (see `web/site.config.ts`'s
`resolveSiteConfig`/`resolveSiteFromHostname`) rather than merged as-is, since
it conflicts with changes the canonical branch made after the stack
diverged. The branches themselves remain on the `appliance-theme` GitHub
repo's remote, unretired, pending a decision on whether their fuller
`SiteConfig` type/data-provider redesign is worth adopting later.
