# Public error codes API

`api_public.error_codes` exposes stable UUID identity, semantic brand/category
keys, diagnostic text, severity, DIY suitability, and reviewed lifecycle data.
The identity is frozen from the original brand/category/code tuple. Mutable
descriptions never affect it.

Rows require active brand/category and a non-empty code. `published` is true
only when a verification timestamp and short description both exist;
`scrape_status` is neither read nor exposed. This ordinary view is immediately
fresh. Public roles receive SELECT only, and numeric IDs, raw source URLs,
scrape state, and creation timestamps remain internal.
