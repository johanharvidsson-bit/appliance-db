# Gate B five-item pilot

This runbook is restricted to the isolated `repair_appliance_dev` database on
loopback. It does not authorize production access, crawling, publication, or
URL changes.

## Prepared state

- PostgreSQL: `127.0.0.1:15432`
- PostgREST: `127.0.0.1:18080`
- PostgREST schemas: `public,api_public`
- Seed: `db/seeds/gate_b_five_item_pilot.sql`
- Site: `appliance-repair-base`
- Environment: `development`
- Frozen scope: Samsung x washing_machine x en

The seed preserves earlier integration-test records but makes them inactive.
It creates two pilot models and two pilot error codes. One model already has
specifications. Cube Coverage must therefore produce exactly:

- 2 `create_model_overview`
- 1 `enrich_model_specs`
- 2 `describe_error_code`

## Quality gate

Set the loopback-only test variables without printing secrets, then run:

```text
python -m pytest -q
```

Required result: zero failures and zero skips. Deprecation warnings from
third-party dependencies are non-blocking but must remain visible.

## Manual source review

Review is one candidate at a time and append-only:

```text
python -m workers source-review --site appliance-repair-base list
python -m workers source-review --site appliance-repair-base show --source-candidate-id ID
python -m workers source-review --site appliance-repair-base decide --source-candidate-id ID --decision accepted --reviewer REVIEWER --reason REASON --confirm
```

`decide` requires candidate ID, reviewer, reason, and explicit `--confirm`.
Use `--dry-run` instead of `--confirm` to preview a decision.

## Execution order

Run Cube Coverage first. Source Discovery requires a development-only
`SERPER_API_KEY`. If it is absent, stop; do not substitute fixtures or invented
URLs for a real pilot.

After discovery, review each candidate manually before continuing:

```text
Cube Coverage
-> Source Discovery
-> Source Review
-> Source Ingestion
-> Knowledge Integration
-> Proposal Review
-> Apply Integration
-> Content Assembly
-> Content Validation
```

No downstream stage may interpret an unreviewed candidate as accepted.
