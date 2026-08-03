# Knowledge Integration Worker (PR 2C)

The Knowledge Integration Worker turns unverified candidate facts from Source Ingestion into reviewable, atomic integration proposals. It reads canonical RepairBase data for comparison, but it never modifies that data. A later Apply Integration worker (PR 2D) must validate and apply separately approved proposals.

## Responsibility boundary

Source Discovery finds candidate URLs. Source Ingestion fetches and parses accepted sources and emits evidenced candidate facts. Knowledge Integration resolves those facts against existing entities and creates proposals. Apply Integration will own approved writes, transactions, reconciliation, and rollback. PR 2C performs no content assembly, translation, publication, URL work, scheduling, external HTTP, Search Console, or LLM work.

The only write targets are worker runs, the four `integration_*` tables, and `candidate_facts.integration_state`. Canonical entities, content, applicability, URLs, redirects, canonical tags, sitemap, and publication status are outside the boundary.

## Selection and lifecycle

Only `candidate`, `needs_review`, and `conflicted` facts attached to backlog in the active site/environment cube are selected. Rejected facts are skipped. Unless `--reprocess` is explicit, only `unprocessed` facts are selected. Backlog rows are never completed.

Processing states are `integration_proposal_created`, `needs_review`, `blocked_by_conflict`, `no_matching_entity`, `same_as_existing`, and `out_of_scope`. Conflicted input can only produce blocked proposals. Manual proposal decisions are preserved by insert-only proposal identity and conflict-safe upserts.

## Entity resolution hierarchy

1. Exact backlog entity ID within Brand and Category scope.
2. Exact Product Code, model, variant, Error Code, Fault, or Guide identifier.
3. Normalized exact identifier (uppercase alphanumeric comparison). Normalization does not prove that two technical variants are identical.
4. Verified alias or legacy identity where available. Candidate legacy mappings are not treated as verified.
5. Brand, Category, Locale, document, and backlog context.
6. Fuzzy matching only as a non-preferred `needs_review` candidate.

No match crosses Brand or Category. The canonical hierarchy remains Model → Model Variant → Product Code. Missing or uncertain variants become `propose_variant_mapping`; variants are never created directly. A Product Code conflict never moves a code automatically. Error Codes resolve by Brand + Category + normalized code. Fault fuzzy matching is review-only. Guide matching requires an explicit identifier or stable procedure hash; a shared topic alone does not establish a shared procedure.

Match types are `exact`, `normalized_exact`, `alias`, `product_code`, `variant_code`, `contextual`, `candidate`, `conflict`, and `none`.

## Confidence model

Scores are transparent and stored with components in `reason_json`:

- exact backlog entity or Product Code: 100;
- scoped Error Code or exact Guide procedure: 98;
- normalized model, variant, or Fault identifier: 95;
- verified alias: 85;
- unique main-model context for a missing variant/Product Code: 80;
- fuzzy contextual candidates: their deterministic similarity score;
- ambiguous or missing target: 20–50.

Thresholds are 95–100 deterministic proposal candidate, 80–94 strong but reviewable, 60–79 needs review, and below 60 blocked/unresolved. Confidence is never verification and cannot produce `approved` or `applied`.

## Proposal and delta contract

`integration_proposals` contains the initiating backlog/fact, proposed target, locale, status, confidence, risk, difference classification, current value, atomic proposed value, reason components, stable input hash, and expected apply operation. Targets preserve alternatives and at most one preferred match. Evidence links back to the exact candidate-fact evidence and source document. Conflicts preserve all candidates and values without selecting a winner.

Examples of atomic deltas include one model specification field, one overview source field, one Error Code description/translation, one identifier mapping, or one Guide candidate. A proposal never contains a vague “improve page” instruction or generated public prose.

The schema supports the bounded proposal catalogue required by PR 2C. The initial resolver emits deterministic model/spec/overview, variant, Product Code, Error Code, Fault, Guide, and source-evidence proposals. Relation proposal types remain review contracts and must only be emitted when future deterministic extractors provide explicit relation evidence.

Difference classes are `new_information`, `same_as_existing`, `more_specific`, `conflicts_with_existing`, `fills_missing_value`, `translation_gap`, `relation_gap`, `out_of_scope`, and `insufficient_evidence`. Same-as-existing facts produce no active proposal.

## Conflict and risk policy

Multiple targets, wrong scope, Product Code/model disagreement, source-fact conflicts, and disagreement with existing values create blocked proposals and open conflict rows. Existing values are not changed.

Risk is independent of confidence:

- `low`: exact identity, evidence, or simple missing specification;
- `medium`: variant/Product Code mapping, overview input, relations, Guide candidate;
- `high`: ambiguous identity, conflict with existing verified data, model/Product Code disagreement;
- `safety_review`: electrical, gas, refrigerant, dismantling, or otherwise hazardous procedures.

## Idempotency and review safety

Proposal identity hashes candidate fact, proposal type, target type/ID, proposed value, and detector version. Identical reruns do not duplicate. Changed source facts or resolver versions create new identities. Existing rejected, approved, or applied proposals are never reopened or overwritten by this worker. Advisory locks cover site/environment/worker and each candidate fact. Historical foreign keys use RESTRICT or SET NULL; service role cannot delete proposal history.

## CLI

```powershell
python -m workers knowledge-integration --site appliance-repair-base --environment development --dry-run
```

Filters: `--batch-size`, `--candidate-fact-id`, `--backlog-id`, `--fact-type`, `--proposal-type`, `--locale`, `--brand`, `--category`, `--min-confidence`, and explicit `--reprocess`. Production is fail-closed. Fixture mode is offline and always dry-run.

Reports are JSON and Markdown under the gitignored `reports/knowledge-integration/`. Logs and reports contain proposal metadata and locators, not full documents, credentials, headers, cookies, environments, or large excerpts.

## RLS and future PR 2D

All proposal tables have forced RLS, no anonymous/authenticated access, service-role read/insert/update only, and no service-role delete. A future review/admin backend may receive explicit policies separately.

PR 2D should consume only manually `approved` proposals. It must validate target existence and scope again, enforce optimistic concurrency against `current_value_json`, apply exactly `expected_apply_operation` transactionally, attach source evidence, mark the proposal `applied` only after reconciliation, preserve rollback data, and never combine unrelated proposals implicitly.
