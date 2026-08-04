# Worker pipeline integration audit

## Gate A status

Repository integration is complete on `integration/worker-pipeline-pilot`, based on `245530e33e29bb5e962f50c3d5482b0e941ef35b`. Database execution is deliberately blocked because no explicit isolated development DSN is configured. No database, network, production, URL, canonical, sitemap, redirect, frontend, or publication operation was performed.

## Linear branch chain

| Delivery | Branch | Commit | Direct parent | Migration | In final branch |
|---|---|---|---|---|---|
| Cube Coverage | `codex/feature/cube-coverage-backlog-worker` | `a5033f44a4b2f2f4ff29e8b1f966f44b84ca7fb5` | `20be19c317f628637da6c4f3918299680f80324f` | 020 | yes |
| Source Discovery | `codex/feature/source-discovery-worker` | `1e9be55afbed0d57932054ae5f5ea043eaab90c3` | `a5033f44…` | 021 | yes |
| Source Ingestion | `codex/feature/source-ingestion-enrichment-worker` | `b636baf2d3ec9df8ef2240d7ebfeb5dd3ca68ad1` | `1e9be55a…` | 022 | yes |
| Knowledge Integration | `codex/feature/knowledge-integration-worker` | `54f4f22866fb15b1b33bf22087cd1eff91aaefc5` | `b636baf2…` | 023 | yes |
| Apply Integration | `codex/feature/apply-integration-worker` | `1c773667955a8ac45b28ef2c29fd52d93cf14a73` | `54f4f228…` | 024 | yes |
| Content Assembly | `codex/feature/content-assembly-worker` | `d7da45d03df02d56f3113bc5892fa718f68601fe` | `1c773667…` | 025 | yes |
| Content Validation | `codex/feature/content-validation-safety-worker` | `245530e33e29bb5e962f50c3d5482b0e941ef35b` | `d7da45d0…` | 026 | yes |

Every local tip equals its remote tip (ahead/behind `0/0`). The chain is direct and linear.

## Migration matrix

Fresh development setup starts with `db/schema.sql`, which creates the legacy baseline and records 002–009. The established migration runner then applies 010–026 in filename order.

| Migration | Purpose / principal objects | Dependency | RLS/grants | Static tests |
|---|---|---|---|---|
| 010 | generic `model_specs` | baseline models | internalized later | yes |
| 011 | revoke internal public access | baseline | explicit revoke | yes |
| 012–014 | public API identity, models and model pages | baseline | public read contracts | yes |
| 015 | URL registry and entity bindings | baseline entities | forced internal RLS | yes |
| 016–017 | information model v1 and compatibility layer | 015 + baseline | forced internal RLS | yes |
| 018 | generic worker runtime | source evidence | forced internal RLS | yes |
| 019 | multisite/publication foundation | entities + URL registry | forced internal RLS | yes |
| 020 | cube snapshots, findings, backlog, worker runs | 019 | forced internal RLS | yes |
| 021 | discovery candidates/cache | 020 | forced internal RLS | yes |
| 022 | fetches, documents, facts, fact evidence | 021 + sources | forced internal RLS | yes |
| 023 | integration proposals, targets, evidence, conflicts | 022 | forced internal RLS | yes |
| 024 | apply attempts and changes | 023 | forced internal RLS | yes |
| 025 | drafts, sections, evidence and issues | 020/022/024 | forced internal RLS | yes |
| 026 | validation runs/results/checks/findings | 025 | forced internal RLS | yes |

There are no duplicate migration numbers. SQL parsing succeeds offline. Runtime DB verification remains Gate B work.

## Integration findings

Two configuration gaps were fixed:

1. workers previously accepted only two hard-coded local development targets, making a separate external development project impossible;
2. migrations read `SUPABASE_DB_URL`, while workers read `REPAIRBASE_SECURITY_TEST_DB_URL`.

External development now requires an exact predeclared host, database, and username. A DSN alone is insufficient. Known production/retired hosts and production database markers remain blocked. The migration runner prefers the same explicit worker DSN and retains the legacy variable only as fallback.

## Known Gate B requirements

The current source/proposal schemas hold reviewer and timestamp data only for proposals. `source_candidates` has no dedicated reviewer columns, and there is no review CLI. Before the persistent pilot, use a reviewed, minimal migration/admin flow or stop and add only that allowed integration capability. Do not mass-approve candidates or proposals.

