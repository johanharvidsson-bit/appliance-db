# Public fault pages API

`api_public.fault_pages` is a localized ordinary view. Stable UUID identities
are frozen per source fault from brand key, category key, and the original
route slug; translated text does not affect identity. Only active brand/category
rows with an exact locale translation and valid route slug project. There is no
locale fallback.

The source has no reviewed public lifecycle gate, so pages are deliberately
`indexable=false`, with null public timestamps. The view exposes no numeric IDs
or scrape state. `anon` and `authenticated` receive SELECT only; the owner gets
only the source columns required by the projection. Ordinary-view freshness is
immediate and avoids a refresh owner or refresh cost.
