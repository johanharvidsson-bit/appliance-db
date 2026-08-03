# Source Ingestion & Enrichment Worker (PR 2B)

This worker fetches only manually `accepted` source candidates attached to active-cube backlog. It archives a content-addressed source version, parses supported documents, and emits unverified candidate facts with exact evidence locators. It never writes canonical entities, relations, translations, URLs, redirects, or publication state.

## Lifecycle and boundaries

`accepted → fetched → parsed → candidate_facts_available → needs_entity_resolution`

Failure states are `blocked`, `unsupported`, `failed`, `too_large`, and `invalid_content`. A failure never changes the manual source-candidate decision and never completes backlog work. PR 2C owns entity resolution and relation proposals.

Supported v1 inputs are HTML, PDF, plain text, and small JSON responses. Video, audio, archives, executable/unknown binary files, authenticated pages, CAPTCHA, paywalls, and browser-rendered pages are unsupported. Forum facts remain candidates and are never promoted here. No LLM is used.

## Network policy

The user agent is `RepairBaseSourceIngestion/1.0 (+https://repairbase.example/source-policy)`. Default rate is one request per second, with bounded retries, redirects, timeout, and a 15 MB decompressed size limit. HTTP(S) is required. URL credentials, localhost, non-public/reserved/link-local IP addresses, and metadata hosts are blocked before every request and redirect. TLS verification remains enabled. Only safe response headers (`Content-Type`, `Content-Length`, `ETag`, `Last-Modified`) are stored; cookies and authorization data are not.

Robots exclusions are respected. Authentication, CAPTCHA, paywall, or robots restrictions produce an unavailable/blocked result; the worker does not bypass them.

## Storage and retention

- Raw HTML/PDF/text: private, content-addressed `data/source-ingestion/<hash-prefix>/<sha256>.<ext>`; gitignored and never public.
- Normalized text and parser metadata: `source_documents`.
- Fetch metadata/hashes/cache validators: `source_fetches` and immutable `sources` versions.
- Bounded excerpts (maximum 500 characters) and locators: `candidate_fact_evidence`.
- Facts and conflict metadata: `candidate_facts`.

Raw files are retained while a document or fact references their storage reference. There is no automated deletion in PR 2B. Operational backup/access policy must treat the storage directory as private. Credentials must never be placed in candidate URLs or raw storage.

## Deterministic extraction and confidence

The extractor reads explicit HTML/PDF/JSON/text labels and patterns only. It does not generate prose or infer missing facts. Confidence is an integer: `55% × source trust + 20` for structured labeled fields, or `55% × source trust + 10` for explicit unstructured patterns, plus 10 parser-certainty points, clamped to 0–100. Confidence is not verification.

Facts sharing subject hint, type, predicate, and locale but containing different values are all retained as `conflicted`; no winner is selected.

## Idempotency

Content SHA-256, ETag, Last-Modified, parser version, extractor version, and fact input hashes provide idempotency. A 304 creates no document. Identical content is not processed unless `--reprocess` is explicit. New content hashes create versions. Rejected facts are not reactivated by an ordinary rerun because inserts are deduplicated by document/extractor/input hash.

## CLI

```powershell
python -m workers source-ingestion --site appliance-repair-base --environment development --dry-run
```

Filters and controls: `--batch-size`, `--timeout`, `--retries`, `--rate-limit`, `--source-candidate-id`, `--backlog-id`, `--source-type`, `--max-document-bytes`, and `--reprocess`. Production is fail-closed. Fixture mode is always dry-run and never performs database or network writes.

Offline acceptance run:

```powershell
python -m workers source-ingestion --site appliance-repair-base --fixture tests/fixtures/source_ingestion.json
```

JSON and Markdown reports are written to `reports/source-ingestion/` and exclude raw document text.
