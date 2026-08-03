# Operational artifacts

The `data/` tree contains several different artifact classes. Reviewed
proposals, final audit reports, and stable reproducibility fixtures may be
tracked after inspection. Raw rollback backups, secrets, logs, and generated
runtime output must remain outside Git.

## Storage contract

Maintain an external, access-controlled artifact archive with the same relative layout expected by the tools:

```text
data/
  article_reviews/
  backups/
    article_reviews/
    p1/
    p2/
  manuals/
  reports/
```

Record SHA-256, byte size, relative path, semantic classification, purpose,
consumer, and creation timestamp for every archived artifact. Verify hashes
after every transfer and before use. Backups may contain complete production
records and must not be committed, printed, or placed in a public object store.

For local reconciliation, use a dated archive outside the Git clone, following
the pattern `repairbase-artifacts/appliance-db/YYYY-MM-DD-purpose/`. A
machine-specific absolute path may be recorded in that archive's own manifest,
but must not become the permanent production storage design.

> **Migration 010 gate:** `pipeline/scrape_specs.py` requires `model_specs`.
> Production migration status is currently unknown. Do not activate that
> pipeline until a separately approved read-only migration-status check has
> succeeded. Applying migration 010 requires separate approval and a backup
> and rollback plan.

## Required runtime inputs

- `data/article_reviews/*.json`: inspected reviewed proposals consumed by `apply_article_review.py`, `apply_article_review_batch.py`, `apply_p1_error_code_articles.py`, `apply_p2_symptom_clusters.py`, proposal validators, and invariant checks. Stable, secret-free reviewed proposals may be tracked for auditability.
- `data/backups/article_reviews/batch-001-...-before.json` through `batch-045-...-before.json`: exact baselines read by deterministic P0 builders 001–045.
- `data/backups/article_reviews/remediation-samsung-faq-brand-before.json`: baseline for the Samsung FAQ remediation builder.
- A caller-supplied proposal and before-state JSON: required by `verify_article_review_invariants.py`.

The deterministic builder chain also contains internal Python imports. Preserve all builders 001–045 together; later builders reuse functions from builders 002, 003, 031, 037, 040, and 041.

## Provenance-only backups

Timestamped `*-before-<timestamp>.json` exports under `data/backups/` are rollback and audit evidence. They are not active application configuration. Keep them immutable in the external archive according to the retention policy.

Exact non-timestamped baselines under `data/backups/article_reviews/` are also
raw production snapshots even when deterministic builders read them. Keep them
in the external archive, restore them only for a controlled reproduction, and
never commit them.

## Trackable evidence

After checksum and secret-pattern inspection, Git may contain:

- approved proposal JSON under `data/article_reviews/`;
- final completion and coverage/invariant reports;
- stable selection inventories and canonical symptom libraries needed to
  explain or reproduce the reviewed delivery.

Do not replace reviewed artifacts with a later regenerated approximation.

## Generated artifacts

The following can be regenerated when the required credentials, database access, source code, and baseline artifacts are available:

- intermediate proposal drafts written by deterministic builders;
- non-final CSV/JSON audit output;
- `STATUS.md`;
- downloaded manuals and transient scraper output, subject to upstream availability.

Exact pre-write backups and historical reviewed proposals cannot be recreated reliably after database content changes. Preserve them even when a deterministic builder can regenerate a similar proposal.

## Restore procedure

1. Clone the source repository without creating or copying an environment file.
2. Obtain the approved artifact manifest and archive through the protected transfer channel.
3. Restore only missing external paths such as `data/backups/`; do not overwrite tracked reviewed proposals or final audits without checksum review, and never restore logs as active logs.
4. Verify every restored artifact against the manifest SHA-256 and size.
5. Confirm ownership and least-privilege access without exposing contents.
6. Run proposal validation in read-only mode before authorizing any writer.
7. Treat missing baselines as a blocker; do not fabricate replacement backup data.

Secrets remain in environment/secret management and are never part of the artifact archive manifest contents.
