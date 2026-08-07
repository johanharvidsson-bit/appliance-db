# Setting up a new site on the platform

The platform is one shared codebase (this repo) with a separate database per
site - no site shares tables or rows with another. `db/migrations/` (as it
exists today, applied in full) is the standard schema template for a new
site's database; there is no separate template file to maintain (an earlier
attempt at one, `db/schema_template.sql`, was an orphaned, unwired duplicate
of what these migrations already do, and was removed).

## What's genuinely generic vs. what needs editing per site

Auditing the current migration chain (`001` through `027`) found it's mostly
schema DDL with no hardcoded appliance data, with three exceptions:

- **`015_url_registry_and_entity_bindings.sql`** and **`018_worker_platform.sql`**
  both default/constrain a `site_id` column to the literal string
  `'appliance-repair-base'` (a `DEFAULT` and, in 015, a `CHECK` that only
  allows that exact value). Before applying to a new site's database,
  replace that literal with the new site's own id (e.g.
  `'outboard-repair-base'`) in both files.
- **`019_multisite_publication_foundation.sql`** `INSERT`s one row into
  `public.sites` with appliancerepairbase's actual name/domain/vertical_key.
  Replace that `INSERT` with the new site's own values before applying.
- **`012_public_api_foundation.sql`** maps category slugs to a singular
  `public_key` (`'washing-machines' -> 'washing_machine'`, etc.) with an
  `ELSE replace(slug_en, '-', '_')` fallback - this is *not* a blocker, a new
  site's own categories just get the auto-generated form unless you add
  explicit `WHEN` cases for nicer names.

Everything else - `sites`/`site_locales`/`site_entity_publications`/
`api_public.*` views (019), the information model (016), frontend
compatibility layer (017), worker platform (018), and the 8-worker content
pipeline's own tables (020-027) - is already generic and needs no per-site
edits.

## Procedure

1. Provision a new self-hosted Postgres 16 + PostgREST instance for the site
   (see `docs/postgresql-vps.md` for the pattern already used in production -
   same Docker Compose approach, new container/volume/DSN).
2. Copy `db/migrations/` for the new site, apply the three edits above.
3. Apply the migrations against the new database:
   `python -m db.apply_migration --all` with `REPAIRBASE_SECURITY_TEST_DB_URL`
   pointed at the new instance (same 2-factor production-write approval as
   any other migration run).
4. Point the worker pipeline at the new DSN and run cube-coverage through
   content-validation (same `python -m workers <stage> --site <new-site-id>
   --environment production --production-token ...` invocations already used
   for appliancerepairbase, just a different DSN and `--site` value) to
   produce real, evidenced content.
5. Add the site's frontend config under `web/src/config/sites/*.ts` and
   register it in `web/site.config.ts`'s `configs` map.
6. Create a new Cloudflare Pages project pointed at this repo, root directory
   `web`, with `ACTIVE_SITE`, `PUBLIC_SUPABASE_URL`, and
   `PUBLIC_SUPABASE_ANON_KEY` set for the new site, and its custom domain
   attached.

This is the exact procedure Phase 3 (outboardrepairbase) follows to prove the
pattern generalizes beyond the original site.
