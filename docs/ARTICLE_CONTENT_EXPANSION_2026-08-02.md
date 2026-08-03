# Article content expansion — 2026-08-02

## Production execution

The article-content session used the live VPS PostgREST endpoint
`http://localhost:8080`. The work is complete and authoritative production
activity. Reconciliation must not replay, roll back, or reapply it.

No frontend change and no database migration formed part of this content
delivery.

## Original/P0 scope

- 259 original repair articles updated across 45 reviewed batches.
- 259 English translations published.
- 259 Swedish translations created with `pending` status.
- 518 translation records verified by database read-back.
- The final completion audit reports 259 articles, 518 translations, complete
  backup coverage, no source issues, no failures, and `passed: true`.

## P1 scope

- 50 verified Samsung error-code articles created from the approved P1
  proposals.
- 50 English translations published and 50 Swedish translations left pending.
- 67 unverified or invalid candidates intentionally remained unpublished.
- The preserved final coverage report records 150 Samsung error codes, 83 with
  articles, and 67 remaining candidates: 47 dishwasher, 14 washing-machine,
  and 6 dryer codes.

## P2 scope

- 20 Samsung symptom faults created.
- 40 fault translations and 40 article translations created.
- 19 supported error-code mappings created.
- English translations are published; Swedish translations are pending.
- Final invariants report no duplicate slugs and no orphan fault IDs.
- The article-content handover reports that all 20 English P2 pages returned
  HTTP 200 in live verification. The HTTP response log itself is not present
  in recovery commit `19440be`; this claim is therefore handover-confirmed but
  not independently re-derived during source reconciliation.

## Safety and audit process

Publication used reviewed file-backed proposals, dry-run-first apply tools,
pre-write JSON backups, constrained writes, and post-write read-back checks.
The apply jobs must not be rerun during reconciliation.

The relationship between artifacts is:

1. deterministic/P1/P2 builders produce proposal documents;
2. reviewed proposals are inputs to apply and validation tools;
3. apply tools create raw before-state rollback backups;
4. invariant and coverage audits verify the resulting state;
5. final audit reports preserve compact delivery evidence without embedding
   full prior production article bodies.

## Preserved evidence

Git-trackable evidence is limited to inspected approved proposals, final audit
reports, and stable reproducibility fixtures. Raw production backups remain in
the protected external archive.

Current reconciliation archive:

- Pattern: `repairbase-artifacts/appliance-db/YYYY-MM-DD-purpose/`
- Reconciliation instance: `2026-08-02-source-reconciliation/`
- Payloads: 49 approved proposal copies and 97 raw production backups.
- Payload bytes: 15,896,856.
- Manifest: `MANIFEST.json`.
- Manifest SHA-256 at reconciliation: `D3BBF632AC1DD1031524E15417525034572E84AF49CF56CC1C3AE26420AE7063`.

The manifest records an individual SHA-256 and size for every archived
payload. It contains no credentials or secret values.

## Evidence assessment

### Directly evidenced facts

The preserved final audits directly evidence the P0 counts and status totals,
the resulting production state for all 45 batches at audit time, the remaining
P1 inventory, and the P2 coverage and invariants stated above. Backup coverage
must be assessed separately from production-state read-back.

### Indirectly corroborated handover claims

The production handover states that 50 P1 articles were applied and read back,
and that all 20 English P2 pages returned HTTP 200. The surviving proposals,
inventory, and final coverage reports corroborate those claims, but the exact
read-back and HTTP verification reports described below do not survive.

### Known missing evidence

**Exact batch-045 proposal payload and execution evidence.**

Recovery commit `19440be` contains reviewed batch proposals 001–044 but not
`data/article_reviews/batch-045-p0-core-final-proposal.json`. The final audit's
live read-back verifies that batch 045's resulting production state matched the
proposal available to the audit at that time. That is evidence of the final
production state, not proof of the exact execution path.

The exact applied proposal file does not survive, and no timestamped apply-time
backup survives. The deterministic batch-045 builder and exact before-state
baseline are preserved, but the exact apply mechanism and complete rollback
provenance cannot be independently reconstructed. Reconstructed artifacts must
not be presented as originals, and production work must not be replayed to fill
this evidence gap.

**P2 HTTP verification report.** No archived HTTP verification report survives
for the 20 English P2 pages. The HTTP 200 result is therefore a handover claim,
not independently re-derived reconciliation evidence.

**Complete P1 production read-back report.** No complete archived 50-row P1
production read-back report survives. The applied/read-back result is
handover-confirmed and corroborated by the preserved final inventory, but not
directly evidenced by a surviving row-level report.

Production work is complete and must not be replayed to fill any evidence gap.
