# Apply Integration Worker

## Responsibility and boundary

`apply-integration` turns one manually approved integration proposal into one
allowlisted domain mutation. Knowledge Integration creates proposals; a human
approves them; this worker applies them; a later reconciliation worker may mark
the proposal applied and close backlog work. Content Assembly and Publication
are separate later stages. This worker never approves proposals, writes public
URLs, publishes content, resolves findings, or completes backlog items.

## Supported operations

| Proposal type | Exact operation | Target | Risk |
|---|---|---|---|
| `propose_model_spec_update` | `upsert_model_spec_field` | `model_specs` | low |
| `propose_model_overview_update` | `update_model_content_field` | `model_content_translations` | low |
| `propose_error_code_description` | `update_error_code_content` | `error_code_translations` | low |
| `propose_error_code_translation` | `update_error_code_content` | `error_code_translations` | low |
| `propose_fault_translation` | `upsert_draft_fault_translation` | `fault_translations` | low |
| `propose_variant_mapping` | `create_candidate_model_variant` | `model_variants` | medium |

Unknown types and mismatched operation names are blocked. Product-code moves,
merges, URL/canonical work, deletions, publication, guide creation, and other
operations without a complete deterministic PR 2C contract are intentionally
unsupported in this first package.

## Approval, scope, and risk

Selection is restricted to `status = approved`. The worker reloads and locks
the proposal and requires reviewer identity/time, risk, expected operation,
current and proposed values, one preferred target, evidence, and no open
high/safety conflict. Database foreign keys, locale constraints, and the
information model's scope triggers remain the final scope boundary. High and
`safety_review` risk are always blocked; `--max-risk` can only narrow the low or
medium worker policy. Placeholder and empty text are rejected.

## Concurrency and transaction lifecycle

Each proposal runs in its own transaction. A transaction-scoped advisory lock
and `FOR UPDATE` proposal lock prevent parallel application of the same
proposal. Relevant target rows are read with `FOR UPDATE`. The worker compares
that value to `current_value_json`; a mismatch is `stale_proposal` and writes no
domain data. It then creates an attempt, performs one mutation, reads the target
back, verifies it, stores the change, and marks the attempt successful. Any
exception rolls the transaction back, preserving the original exception.

Independent proposals can run concurrently. Proposals for the same target and
field serialize on the target row or detect a stale baseline. A unique partial
index permits only one successful attempt per proposal.

## Evidence and audit

Application requires the proposal evidence chain created by PR 2C. That chain
preserves proposal → candidate fact → candidate fact evidence → source document
and upstream discovery/backlog provenance. PR 2D does not synthesize a legacy
`sources` row from a `source_document`, so it does not create a domain
`source_evidence` row unless a later explicit mapping contract is introduced.
Missing proposal evidence blocks application.

`integration_apply_attempts` records technical execution and
`integration_apply_changes` records internal operation/table names, keys,
before/after values, a stable change hash, and rollback data. Both are internal,
forced-RLS tables without anonymous grants or cascade deletion.

## Status and backlog lifecycle

A successful technical apply is represented by a `succeeded` attempt. The
proposal deliberately remains `approved`; its candidate fact remains in
`integration_proposal_created`. Reconciliation, not this worker, later decides
whether to mark the proposal `applied`, resolve the finding, and complete the
backlog item.

## Idempotency and retries

The proposal ID, input hash, exact operation, preferred target, and proposed
value define the plan. A prior successful attempt returns success without a
second mutation. Failed/stale attempts are excluded by default. `--retry-failed`
only permits reconsideration; all approval, risk, baseline, target, evidence,
and operation checks still run. Stale proposals require new integration/review.

## Rollback

Every successful change stores `expected_current`, the prior value, and the
operation. This is sufficient for a guarded scalar, JSONB-field, inserted-row,
or relation rollback implementation. Automated rollback execution is deferred
to a separate PR: it must lock the target, require an explicit attempt ID and
confirmation, refuse if current state differs from `after_json`, and append its
own audit record. No rollback may alter backlog or finding state.

## CLI

Dry-run (safe default for fixtures and inspection):

```bash
python -m workers apply-integration --site appliance-repair-base \
  --environment development --proposal-id 123 --dry-run
```

Confirmed development apply:

```bash
python -m workers apply-integration --site appliance-repair-base \
  --environment development --proposal-id 123 --max-risk low --confirm
```

Other filters are `--batch-size`, `--proposal-type`, `--risk-level`, and
`--reviewed-by`. `--retry-failed` is explicit. Initial operation should use one
proposal per command. Production is disabled and no scheduler is installed.
Reports are written as JSON and Markdown under `reports/apply-integration/`
(runtime artifacts, not source control). Exit codes are 0 success, 2 blocked,
3 stale, and 4 failed; invalid configuration exits through argparse/SystemExit.

## Security and publication safeguards

The audit tables grant only service-role select/insert/update access, with no
delete. Repository writes use a fixed table and field allowlist; proposal data
cannot select a table. Translation mutations remain `draft`. The writable set
excludes URL registry/bindings/redirects, canonical and sitemap data. The worker
makes no HTTP, LLM, Search Console, frontend, deployment, or production calls.

## Later workers

Reconciliation consumes successful attempts plus verified domain state to
advance proposal/finding/backlog lifecycle. Content Assembly creates complete
editorial drafts from structured facts; it is not an apply operation.
Publication performs editorial and public-readiness checks and is likewise out
of scope here.
