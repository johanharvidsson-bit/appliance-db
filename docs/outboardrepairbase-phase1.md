# OutboardRepairBase phase 1

This implementation adds the shared RepairBase foundation alongside the
legacy ApplianceRepairBase schema. New tables use the `rb_` prefix so existing
`brands`, `models`, articles, scrapers, and local work in progress remain
untouched.

## Implemented migrations

Numbered 028-030, not 011-013: the `codex/feature/*-worker` branch chain
(merged via `integration/worker-pipeline-pilot`) independently claimed
011-027 for the ApplianceRepairBase worker platform. Both lines started
counting from 010 on their own branch; renumbering this line avoids a
collision when the two are eventually merged. See
`docs/workers/worker-pipeline-integration.md` for the other chain's
migration matrix.

1. `028_repairbase_catalog_applicability.sql`
   - sites, languages, categories, manufacturers, and brands
   - model, technical generation, commercial variant, and model year
   - FK-safe aliases and serial-number schemes
   - applicability sets, inclusion/exclusion rules, and ancestry validation
2. `029_repairbase_evidence_specifications.sql`
   - sources and immutable source revisions
   - typed technical assertions and evidence links
   - units, operating conditions, and specifications
   - manuals and manual applicability
   - immutable source revisions and published technical assertions
   - deferred evidence/review publication gate
3. `030_repairbase_localization_publication.sql`
   - per-entity translations for the phase-1 domains
   - explicit site language, category, and brand isolation
   - FK-safe page subjects, hreflang clusters, and routes
   - page revisions, redirects, publication gates, and audit events

## Applicability semantics

- Inclusion rules in one set form a union.
- Refinements inside a rule are combined with AND.
- Matching exclusions are subtracted after inclusions.
- The winning inclusion is the most specific match:
  variant, generation, model, product line, brand, category, global.
- Overlapping inclusion rules at the same highest specificity fail safely as
  `ambiguous_same_specificity`; no rule-ID tie breaker silently picks a winner.

`pipeline/applicability_resolver.py` is the executable reference behavior for
the resolver. Database queries may optimize candidate selection but must return
the same result and explanation.

## Constraint ownership

| Requirement | Enforcement |
| --- | --- |
| Model/product-line brand and category agree | Composite foreign key |
| Variant belongs to selected generation | Composite foreign key |
| One applicability target per rule | Check constraint |
| Year and date range order | Check constraint |
| Serial scheme belongs to target brand | Database trigger |
| One generation-wide model-year row | Partial unique index |
| Hosted manual has explicit permission | Check constraint |
| Published assertion has evidence and review | Deferred constraint trigger |
| Exclusion set contains an inclusion | Deferred database trigger |
| Exclusion is a semantic subset of an inclusion | Deferred resolver validation |
| Equal-specificity assertion conflict | Deferred repository/service validation |
| Hreflang site and subject identity | Database trigger and unique index |
| Published page revision belongs to page | Composite foreign key |
| Published assertion/page changes | Immutability rules and audit triggers |

## Intentional deferrals and limitations

- Assertion conflict grouping and precedence are deferred to the repository
  layer. Rows are retained and never overwritten silently, but conflicting
  assertions are not yet automatically classified.
- Serial parsing and normalization are scheme-specific preprocessing concerns.
  The resolver compares only normalized values from the same scheme and prefix;
  missing or unparsable values fail closed.
- Semantic proof that every exclusion is a subset of an inclusion is deferred.
  The database does reject exclusion-only sets.
- Manual pages whose applicability spans several sites require repository-level
  eligibility validation beyond the current page subject checks.
- Diagnostic, maintenance, repair, parts, procedure, and FAQ domains are not in
  migrations 028-030.

## Offline checks

From the repository root:

```text
python -m pytest tests/test_applicability_resolver.py tests/test_repairbase_migration_contract.py tests/test_migration_runner.py
python -m db.apply_migration --list
git diff --check
```

`--list` does not apply migrations. `--check`, `--all`, and
`--verify-repairbase` require an explicitly configured PostgreSQL connection
and are reserved for the separate isolated-validation milestone.

## Integration fixture

`tests/fixtures/repairbase_phase1.sql` exercises Yamaha F150 and Mercury 150
FourStroke identities with deliberately synthetic generation keys. It runs in
a transaction and always rolls back, so fixture identities can never be
mistaken for sourced production facts. Migrations 028-030 and this fixture
must pass against a disposable or staging PostgreSQL database before rollout.

No live or persistent database has been migrated. The next milestone is an
isolated PostgreSQL 16 validation on the VPS: create a disposable database,
apply the supported baseline plus migrations 028-030, run the rollback-only
fixture and destructive constraint tests, then remove the disposable database.
