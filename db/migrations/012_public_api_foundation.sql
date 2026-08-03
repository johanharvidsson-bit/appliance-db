-- Migration 012: first constrained api_public foundation.
--
-- Decisions:
-- * Public keys are frozen in an internal mapping, independent of mutable slugs.
-- * Brand publication means active with at least one model.
-- * Category publication means active with an explicit translation row; there
--   is no locale fallback and the current schema has no separate approval or
--   indexability state. The compatibility rule is therefore indexable=true.
-- * Source creation/scrape timestamps are not public lifecycle timestamps, so
--   updated_at is NULL until a reviewed public lifecycle field exists.
-- * Sitemap scope is brand and category only. It is a materialized snapshot;
--   every refresh generates one fixed projection_revision for all rows.

DO $role$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'api_public_owner') THEN
        CREATE ROLE api_public_owner
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
END
$role$;

ALTER ROLE api_public_owner
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOINHERIT NOREPLICATION NOBYPASSRLS;

CREATE TABLE IF NOT EXISTS public.api_public_identities (
    resource_type text NOT NULL CHECK (resource_type IN ('brand', 'category')),
    source_id integer NOT NULL,
    public_key text NOT NULL CHECK (public_key ~ '^[a-z][a-z0-9_]*$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (resource_type, source_id),
    UNIQUE (resource_type, public_key)
);

ALTER TABLE public.api_public_identities ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.api_public_identities FROM PUBLIC, anon, authenticated;
DROP POLICY IF EXISTS "api public owner read identities"
    ON public.api_public_identities;
CREATE POLICY "api public owner read identities"
    ON public.api_public_identities
    FOR SELECT TO api_public_owner
    USING (true);

INSERT INTO public.api_public_identities (resource_type, source_id, public_key)
SELECT 'brand', id, replace(slug, '-', '_')
FROM public.brands
ON CONFLICT (resource_type, source_id) DO NOTHING;

INSERT INTO public.api_public_identities (resource_type, source_id, public_key)
SELECT 'category', id,
       CASE slug_en
           WHEN 'washing-machines' THEN 'washing_machine'
           WHEN 'dryers' THEN 'dryer'
           WHEN 'dishwashers' THEN 'dishwasher'
           WHEN 'refrigerators' THEN 'refrigerator'
           WHEN 'freezers' THEN 'freezer'
           WHEN 'ovens' THEN 'oven'
           WHEN 'microwaves' THEN 'microwave'
           ELSE replace(slug_en, '-', '_')
       END
FROM public.categories
ON CONFLICT (resource_type, source_id) DO NOTHING;

REVOKE ALL ON SCHEMA public FROM api_public_owner;
GRANT USAGE ON SCHEMA public TO api_public_owner;
REVOKE CREATE ON SCHEMA public FROM api_public_owner;

REVOKE SELECT (resource_type, source_id, public_key, created_at)
    ON public.api_public_identities FROM api_public_owner;
REVOKE SELECT (id, name, slug, logo_url, is_active)
    ON public.brands FROM api_public_owner;
REVOKE SELECT (brand_id, category_id)
    ON public.models FROM api_public_owner;
REVOKE SELECT (id, slug_en, icon_url, sort_order, is_active)
    ON public.categories FROM api_public_owner;
REVOKE SELECT (category_id, locale, name, slug)
    ON public.category_translations FROM api_public_owner;

GRANT SELECT (resource_type, source_id, public_key)
    ON public.api_public_identities TO api_public_owner;
GRANT SELECT (id, name, slug, logo_url, is_active)
    ON public.brands TO api_public_owner;
GRANT SELECT (brand_id)
    ON public.models TO api_public_owner;
GRANT SELECT (id, sort_order, is_active)
    ON public.categories TO api_public_owner;
GRANT SELECT (category_id, locale, name, slug)
    ON public.category_translations TO api_public_owner;

CREATE SCHEMA IF NOT EXISTS api_public AUTHORIZATION postgres;
ALTER SCHEMA api_public OWNER TO postgres;
REVOKE ALL ON SCHEMA api_public FROM PUBLIC, anon, authenticated, api_public_owner;
GRANT USAGE ON SCHEMA api_public TO anon, authenticated, api_public_owner;
REVOKE CREATE ON SCHEMA api_public FROM anon, authenticated, api_public_owner;

DROP MATERIALIZED VIEW IF EXISTS api_public.sitemap_entries;
DROP VIEW IF EXISTS api_public.category_pages;
DROP VIEW IF EXISTS api_public.brands;

CREATE VIEW api_public.brands AS
SELECT identity.public_key::text AS brand_key,
       brand.slug::text AS slug,
       brand.name::text COLLATE "C" AS name,
       brand.logo_url::text AS logo_url,
       ('/brands/' || brand.slug || '/')::text AS canonical_path,
       NULL::timestamptz AS updated_at
FROM public.brands AS brand
JOIN public.api_public_identities AS identity
  ON identity.resource_type = 'brand' AND identity.source_id = brand.id
WHERE brand.is_active
  AND EXISTS (SELECT 1 FROM public.models AS model WHERE model.brand_id = brand.id);

ALTER VIEW api_public.brands OWNER TO api_public_owner;

CREATE VIEW api_public.category_pages AS
SELECT identity.public_key::text AS category_key,
       translation.locale::text COLLATE "C" AS locale,
       translation.slug::text AS slug,
       translation.name::text COLLATE "C" AS name,
       NULL::text AS icon_key,
       category.sort_order::integer AS sort_order,
       CASE WHEN translation.locale = 'en'
            THEN ('/' || translation.slug || '/')::text
            ELSE ('/' || translation.locale || '/' || translation.slug || '/')::text
       END AS canonical_path,
       true AS indexable,
       NULL::timestamptz AS updated_at
FROM public.categories AS category
JOIN public.api_public_identities AS identity
  ON identity.resource_type = 'category' AND identity.source_id = category.id
JOIN public.category_translations AS translation
  ON translation.category_id = category.id
WHERE category.is_active
  AND translation.locale ~ '^[a-z]{2}(-[A-Z]{2})?$'
  AND translation.slug <> ''
  AND translation.name <> '';

ALTER VIEW api_public.category_pages OWNER TO api_public_owner;

CREATE MATERIALIZED VIEW api_public.sitemap_entries AS
WITH revision AS (
    SELECT uuid_generate_v4() AS projection_revision
), brand_locales(locale) AS (
    VALUES ('en'::text), ('sv'::text)
), brand_entries AS (
    SELECT uuid_generate_v5(uuid_ns_url(),
               'repairbase:v1:brand:' || brand.brand_key || ':' || locale.locale) AS sitemap_entry_id,
           'brand'::text AS content_type,
           brand.brand_key AS public_content_id,
           locale.locale COLLATE "C" AS locale,
           CASE WHEN locale.locale = 'en'
                THEN brand.canonical_path
                ELSE '/sv/brands/' || brand.slug || '/'
           END::text COLLATE "C" AS canonical_path,
           brand.updated_at,
           true AS indexable,
           jsonb_build_object(
               'en', brand.canonical_path,
               'sv', '/sv/brands/' || brand.slug || '/'
           ) AS hreflang
    FROM api_public.brands AS brand CROSS JOIN brand_locales AS locale
), category_entries AS (
    SELECT uuid_generate_v5(uuid_ns_url(),
               'repairbase:v1:category:' || page.category_key || ':' || page.locale) AS sitemap_entry_id,
           'category'::text AS content_type,
           page.category_key AS public_content_id,
           page.locale,
           page.canonical_path::text COLLATE "C" AS canonical_path,
           page.updated_at,
           page.indexable,
           (SELECT jsonb_object_agg(alternate.locale, alternate.canonical_path ORDER BY alternate.locale)
              FROM api_public.category_pages AS alternate
             WHERE alternate.category_key = page.category_key) AS hreflang
    FROM api_public.category_pages AS page
)
SELECT entry.sitemap_entry_id, entry.content_type, entry.public_content_id,
       entry.locale, entry.canonical_path, entry.updated_at, entry.indexable,
       entry.hreflang, revision.projection_revision
FROM (
    SELECT * FROM brand_entries
    UNION ALL
    SELECT * FROM category_entries
) AS entry
CROSS JOIN revision
WHERE entry.indexable
  AND entry.canonical_path LIKE '/%'
  AND entry.canonical_path NOT LIKE '%?%'
  AND entry.canonical_path NOT LIKE '%#%';

ALTER MATERIALIZED VIEW api_public.sitemap_entries OWNER TO api_public_owner;

CREATE UNIQUE INDEX api_public_sitemap_entries_id_uidx
    ON api_public.sitemap_entries (sitemap_entry_id);
CREATE UNIQUE INDEX api_public_sitemap_entries_revision_path_uidx
    ON api_public.sitemap_entries
       (projection_revision, canonical_path COLLATE "C", locale COLLATE "C", sitemap_entry_id);

REVOKE ALL ON ALL TABLES IN SCHEMA api_public FROM PUBLIC, anon, authenticated;
GRANT SELECT ON api_public.brands TO anon, authenticated;
GRANT SELECT ON api_public.category_pages TO anon, authenticated;
GRANT SELECT ON api_public.sitemap_entries TO anon, authenticated;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA api_public
    REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE api_public_owner IN SCHEMA api_public
    REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;

INSERT INTO public.schema_migrations (version, filename)
VALUES ('012', '012_public_api_foundation.sql')
ON CONFLICT (version) DO NOTHING;
