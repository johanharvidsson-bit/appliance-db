# Future design note: applicability resolver

Not implemented. Captured from `feature/repairbase-schema-foundation`
(tagged `retired/feature-repairbase-schema-foundation` before archiving -
the reference implementation is still readable via
`git show retired/feature-repairbase-schema-foundation:pipeline/applicability_resolver.py`)
before that branch was retired in favor of migration 019's simpler,
already-proven publication mechanism (see `docs/RETIRED_BRANCHES.md`).

## The problem it solves

A spec, part, or fault code doesn't always apply uniformly across every
model/variant/year of a product line - it can be scoped to a specific engine
generation, a model-year range, a production-date range, a market code, or a
serial-number range (common for outboard motors, where the same nominal
model spans years of running changes). Migration 019's publication mechanism
doesn't attempt this - it's entity-level (a model/guide/article is or isn't
published), not variant-level.

## The design, in brief

- A hierarchy of specificity: `global < category < brand < product_line <
  engine_model < engine_generation < model_variant`.
- Rules are either inclusions or exclusions, each scoped to a target in that
  hierarchy plus optional constraints (model-year range, production-date
  range, market code, serial-number scheme/prefix/range).
- Resolution order: **any matching exclusion wins outright** (most specific
  exclusion, if several match) **and blocks the target regardless of any
  matching inclusion**. Otherwise, the **most specific matching inclusion**
  wins. Two matching inclusions at the same specificity with no exclusion
  between them is treated as a real ambiguity, not silently resolved by
  rule-id order.
- Serial-number matching never guesses: a context with an unparseable serial
  number fails matching explicitly (`serial_unparseable`) rather than being
  treated as "no constraint."

## When this becomes worth building

Not before there's a real site whose catalog actually needs
finer-than-entity-level differentiation - outboard motors (Phase 3) are the
most likely first candidate, given how much running-change/serial-range
variation exists within a single nominal engine model. Revisit once
outboardrepairbase has enough real content that "does this fault code apply
to my specific engine year/serial" becomes a real, not speculative, need.
