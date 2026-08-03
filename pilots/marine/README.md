# Marine isolated development pilot

This opt-in stack defines a dedicated `marine_repair_dev` PostgreSQL database,
dedicated PostgREST process, loopback-only ports, persistent volume, and
`api_public`-only exposure. It shares no Appliance storage, API target,
credentials, or cache namespace.

The seed is intentionally small: three categories, five brands, and fifty
models. No scraping runs. Platform migrations create the public contracts used
by the shared frontend.

Credential values are deliberately absent. An operator must supply an approved
database-admin password, a distinct Marine PostgREST password/URI for the fixed
`marine_postgrest` login, and a JWT secret in an untracked `.env`. The bootstrap
creates only the database roles after those values are supplied; this branch
does not generate, store, or deploy credential values. Start only after Target
Guard/operator approval:

```text
docker compose --env-file pilots/marine/.env -f pilots/marine/compose.dev.yml config
docker compose --env-file pilots/marine/.env -f pilots/marine/compose.dev.yml up -d
```

Use `SITE_KEY=marine`, `API_TARGET_SITE_KEY=marine`,
`PUBLIC_API_SCHEMA=api_public`, and `CACHE_NAMESPACE=marine-dev` in a dedicated
frontend dev runtime. Production, DNS, Cloudflare, and deployment are outside
this pilot.
