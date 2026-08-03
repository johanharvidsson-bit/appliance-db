# Public model specifications API

`api_public.model_specs` is keyed by the existing stable public `model_id` and
adds semantic brand/category keys plus a JSON specification document. Only
non-empty JSON objects belonging to a currently public model project.

The source has scrape and creation timestamps but no reviewed public lifecycle
timestamp, so `updated_at` is deliberately null and neither internal timestamp
is exposed. A projected non-empty document is marked `published=true`.

The ordinary view is immediately fresh. The owner receives only `model_id` and
`specs`; public roles receive SELECT on the projection and no write privileges.
