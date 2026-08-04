# Content Assembly Worker (PR 3A)

`content-assembly` converts already integrated, evidenced facts into internal structured drafts. Apply Integration owns approved atomic domain writes; this worker only reads those results. Content Validation & Safety (PR 3B) will validate claims, evidence completeness, language, duplication, and safety. PR 3A never validates finally, approves, publishes, changes URLs, resolves entities, or completes backlog.

## Supported drafts and templates

Templates are versioned code contracts, not a general CMS:

| Template | Draft | Required input |
|---|---|---|
| `model_overview_v1` | model overview | model name |
| `error_code_description_v1` | Error Code | code, meaning |
| `fault_summary_v1` | Fault | symptom |
| `troubleshooting_guide_v1` | Guide | title, at least two ordered steps |
| `translation_v1` | translation | source/target locales, source hash, translated sections |
| `faq_candidate_v1` | FAQ candidate | directly evidenced question/answer items |

Templates define stable section order, required and optional facts, forbidden claims, output shape, and base safety classification. They do not depend on Product Line or Series. Empty optional sections are omitted—there are no placeholders, empty headings, “coming soon,” or generic filler.

Model drafts may contain only explicit identity, description, specification, variant, source, and integrated relation data. Error Code drafts require a meaning but not a Guide; safe first checks require evidence. Fault causes remain explicitly possible and full procedures are not duplicated. Guide steps preserve source order and are never invented or merged across conflicts. FAQ candidates require direct evidence and user value, not SEO coverage.

## Facts, claims, and evidence

Assembly is deterministic: `integrated facts → structured JSON sections`. No LLM is present. Each assembled factual section carries candidate-fact, source-evidence, or source-document provenance and its locator. A section with content but no evidence is blocked. Formatting may group explicit specifications or order explicit steps, but it cannot diagnose, infer compatibility, recommend parts, invent costs/time/lifespan, or label faults “common” without evidence.

Candidate-only, rejected, needs-resolution, conflicted, and out-of-scope input is not normal assembly input. Any residual integrated conflict blocks the draft and retains all evidence.

## Missing data and comparisons

Missing required facts produce `blocked` or `partial`, plus a precise issue. Optional absent data produces `omitted_no_data`, not a placeholder. Draft and section issues include missing facts/evidence, conflicts, insufficient procedures, missing locale source, unsupported claims, invalid template input, and required safety review.

Existing content comparisons are `new_draft`, `fills_missing_section`, `updates_existing_draft`, `same_as_existing`, `conflicts_with_existing`, `would_remove_information`, or `translation_stale`. Same input is deduplicated. Published content is never overwritten or removed.

## Translation and safety

Translations require source locale, target locale, immutable source-content hash, and explicit translated sections. Identifiers, safety meaning, applicability, and uncertainty markers are carried as structured input; PR 3A adds no facts. Translation drafts remain unreviewed and require later validation.

Risk is independent of confidence. Electrical mains/230 V, live measurement, gas, refrigerant, panels/dismantling, heat, pressure, sharp/chemical/heavy components, and water/electricity combinations are flagged `safety_review`. PR 3A flags risk; PR 3B decides pass/review/fail.

## Persistence, lifecycle, and idempotency

Internal tables are `content_drafts`, `content_draft_sections`, `content_draft_evidence`, and `content_draft_issues`. Forced RLS denies anonymous/authenticated access; service role has select/insert/update but no delete. Historical foreign keys use RESTRICT/SET NULL.

Identity includes backlog, entity, locale, draft/template/version, source-input hash, and assembler version. Identical runs deduplicate. Changed facts/templates/assembler versions create a new draft. Only an unreviewed predecessor may be superseded; rejected or approved history is never silently reopened or overwritten. Advisory locks cover worker scope and the exact backlog/entity/locale/draft tuple.

Backlog processing may become `content_draft_created`, `content_draft_partial`, `content_draft_blocked`, or `needs_content_validation`. The backlog is never completed and findings are never resolved here.

## CLI

```powershell
python -m workers content-assembly --site appliance-repair-base --environment development --dry-run
```

Filters: `--batch-size`, `--backlog-id`, `--entity-type`, `--entity-id`, `--locale`, `--draft-type`, `--template-id`, `--risk-level`, and explicit `--reassemble`. Production is fail-closed. Fixture mode is offline and always dry-run. Exit codes are 0 when at least one complete draft exists, 2 for partial-only batches, and 3 for blocked-only batches.

JSON/Markdown reports under gitignored `reports/content-assembly/` include counts and metadata, not source documents, credentials, headers, or large console payloads.

## PR 3B contract

PR 3B should consume assembled/partial drafts and independently validate every claim against `content_draft_evidence`, detect unsupported or removed information, verify locale/source hashes and identifier preservation, check placeholders and duplication, and perform safety rules. It may set validation results but must not publish. Editorial review and controlled publication remain later stages.
