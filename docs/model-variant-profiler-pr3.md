# PR 3 — deterministic model/variant profiler pilot

PR 3 adds an offline-first profiler for one bounded brand/category scope. It does not perform global backfill, modify public URLs, redirects, canonicals, sitemap membership, frontend behavior, or production data.

## Conservative decision rules

- Every input model receives exactly one traceable decision.
- Input containing more than one brand/category is rejected.
- A unique bare model whose normalized name equals the family is the only automatic main identity.
- Only an exact slash-delimited suffix such as `WM100/EN` can become a variant candidate automatically.
- Ambiguous families remain self-mapped for the report, create only non-authoritative candidates, and emit a manual stop-gate.
- A singleton with no safe group remains unchanged.
- Product Line and Series are not inputs.

Normalization is tested from the same language-neutral JSON fixture in Python and JavaScript.

## Execution

Dry-run is the default:

```powershell
python -m pipeline.model_variant_profiler `
  --input tests/fixtures/model_variant_pilot.json `
  --output model-variant-pilot.json
```

Candidate persistence is separately guarded and only accepts the isolated development database:

```powershell
$env:REPAIRBASE_MODEL_PROFILE_DB_URL = 'postgresql://postgres@127.0.0.1:15432/repair_appliance_dev'
python -m pipeline.model_variant_profiler `
  --input tests/fixtures/model_variant_pilot.json `
  --output model-variant-pilot.json `
  --persist-candidates `
  --rollback-output model-variant-pilot-rollback.json
```

Persistence may create only `candidate` model variants and `candidate` legacy mapping alternatives. It never writes `legacy_model_mapping`, never verifies a variant, and preserves accepted/rejected candidate review state. Repeated execution is idempotent.

## Synthetic pilot result

The checked-in six-model fixture produced:

- 6 traceable decisions;
- 2 exact variant candidates (`EN`, `US`);
- 2 ambiguous non-authoritative mapping alternatives;
- 1 manual-review stop-gate;
- 0 authoritative mappings;
- 0 URL changes.

The first local persistence run created 2 candidate variants and 4 candidate mapping rows. The second run created no rows and only touched the same identities. The generated rollback manifest lists only rows created by that execution and requires candidates to be removed before their candidate variants.

## Pilot boundary

This PR proves mechanics with synthetic data only. Selecting and running a real brand/category pilot requires a separate explicit instruction and a reviewed data-access plan. Missing or ambiguous evidence must never be converted into an authoritative mapping.
