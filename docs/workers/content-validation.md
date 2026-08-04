# Content Validation & Safety Worker

`content-validation` is a deterministic, fail-closed gate between immutable PR 3A drafts and later editorial work. It validates structure, evidence chains, claim strength, identifiers, translations, information loss, duplication, and safety signals. It does not rewrite a draft, generate content, resolve entities, approve editorial quality, publish, alter URLs, or crawl sources.

## Outcomes

- `pass`: eligible for a later editorial review step; never means published.
- `needs_review`: a human must resolve uncertainty, duplication, staleness, or safety review.
- `fail`: a hard invariant is broken, such as missing evidence, an identifier mismatch, missing safety warning, invalid structure, or changed procedure order.

The versioned `RULE_CATALOG` records each rule's predicate, severity, scope, effect, false-positive risk, and remediation. Validation identity hashes include the immutable content hash, evidence hash, validator/ruleset versions, template version, and entity id. Re-running identical input therefore creates no duplicate history. Changed input creates a new historical result.

## Persistence boundary

Migration 026 creates append-only validation runs, results, claim checks, safety findings, and duplication findings. The worker may only update `content_drafts.validation_state` and `content_backlog.content_validation_state`; it cannot update sections, rendered content, evidence, review state, publication state, entities, or URLs. RLS denies anonymous/authenticated access and service-role deletion.

## CLI

```powershell
python -m workers content-validation --site appliance-repair-base --environment development --dry-run
python -m workers content-validation --site appliance-repair-base --environment development --draft-id 123
python -m workers content-validation --site fixture-site --fixture tests/fixtures/content_validation.json
```

Filters include draft/backlog id, entity type, locale, draft type, risk level, and result. `--include-blocked` is diagnostic only. Production execution is disabled. Fixture execution always implies dry-run. Exit code 0 means all evaluated drafts passed, 2 means review is required, 3 means at least one failure, and 4 means lock-blocked work.

Reports are written as JSON and Markdown under the gitignored `reports/content-validation/` directory. They contain aggregate outcomes and reason codes, never source documents or credentials.

## Operational order

Apply migration 026 in an isolated development database, run dry-run validation, inspect the report, then run a small persistent batch. Safety findings always require human review. Publication and URL migration remain separate later operations.
