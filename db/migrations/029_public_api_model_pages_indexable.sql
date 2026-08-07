-- Migration 029: make every projected model page indexable.
--
-- Migration 014 deliberately made indexability conservative
-- ((model.indexable AND category.indexable), which currently evaluates
-- false for all 43,332 rows since no model-lifecycle review process exists
-- yet to set model.indexable=true). Owner-approved compatibility decision
-- (2026-08-07, mirroring the same decision already made and reapplied here
-- for an equivalent migration on a since-retired branch): every otherwise
-- valid projected page is immediately indexable. This deliberately does not
-- require specs, articles, error codes, manuals, or an internal scrape
-- status - scrape_status is never consulted, same as before.
--
-- api_public.sitemap_entries is intentionally left unchanged - the frontend
-- already has its own dedicated model sitemap endpoints (sitemap-models-*.xml.ts);
-- folding these rows into the Public API snapshot is a separate migration.

DO $drop_model_pages_projection$
DECLARE
    relation_kind "char";
BEGIN
    SELECT c.relkind INTO relation_kind
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'api_public' AND c.relname = 'model_pages';
    IF relation_kind = 'v' THEN
        EXECUTE 'DROP VIEW api_public.model_pages';
    ELSIF relation_kind = 'm' THEN
        EXECUTE 'DROP MATERIALIZED VIEW api_public.model_pages';
    END IF;
END
$drop_model_pages_projection$;

CREATE MATERIALIZED VIEW api_public.model_pages AS
WITH page_rows AS MATERIALIZED (
    SELECT model.model_id,
           model.brand_key,
           model.category_key,
           category.locale,
           category.slug::text AS category_slug,
           model.slug::text AS model_slug,
           concat(
               rtrim(category.canonical_path, '/'), '/',
               brand.slug, '/', model.slug, '/'
           )::text COLLATE "C" AS canonical_path,
           true AS indexable,
           NULL::timestamptz AS published_at,
           greatest(model.updated_at, category.updated_at, brand.updated_at)
               AS updated_at
    FROM api_public.models AS model
    JOIN api_public.brands AS brand
      ON brand.brand_key = model.brand_key
    JOIN api_public.category_pages AS category
      ON category.category_key = model.category_key
)
SELECT uuid_generate_v5(
           uuid_ns_url(),
           concat('repairbase:v1:model_page:', page.model_id::text, ':', page.locale)
       ) AS model_page_id,
       page.model_id,
       page.brand_key,
       page.category_key,
       page.locale::text COLLATE "C" AS locale,
       page.category_slug,
       page.model_slug,
       page.canonical_path,
       jsonb_object_agg(page.locale, page.canonical_path)
           OVER (PARTITION BY page.model_id) AS hreflang,
       page.indexable,
       page.published_at,
       page.updated_at
FROM page_rows AS page;

ALTER MATERIALIZED VIEW api_public.model_pages OWNER TO api_public_owner;
REVOKE ALL ON api_public.model_pages FROM PUBLIC, anon, authenticated;
GRANT SELECT ON api_public.model_pages TO anon, authenticated;

CREATE UNIQUE INDEX api_public_model_pages_id_uidx
    ON api_public.model_pages (model_page_id);
CREATE UNIQUE INDEX api_public_model_pages_model_locale_uidx
    ON api_public.model_pages (model_id, locale);
CREATE UNIQUE INDEX api_public_model_pages_path_uidx
    ON api_public.model_pages (canonical_path COLLATE "C");
CREATE INDEX api_public_model_pages_order_idx
    ON api_public.model_pages (canonical_path COLLATE "C", model_page_id);
CREATE INDEX api_public_model_pages_locale_order_idx
    ON api_public.model_pages
       (locale COLLATE "C", canonical_path COLLATE "C", model_page_id);
CREATE INDEX api_public_model_pages_indexable_order_idx
    ON api_public.model_pages
       (indexable, canonical_path COLLATE "C", model_page_id);

ANALYZE api_public.model_pages;

INSERT INTO public.schema_migrations (version, filename)
VALUES ('029', '029_public_api_model_pages_indexable.sql')
ON CONFLICT (version) DO NOTHING;
NOTIFY pgrst, 'reload schema';
