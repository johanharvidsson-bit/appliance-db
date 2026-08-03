-- Migration 013: language-independent public model catalog.
--
-- Publication compatibility rule:
-- * both brand and category are active;
-- * model name and route slug are non-empty and the slug is route-safe;
-- * the source row has frozen public identity mappings.
--
-- The source schema does not yet have reviewed model publication, URL approval,
-- indexability, or public lifecycle timestamps. The projection therefore fails
-- closed for those fields: manual_url and updated_at are NULL and indexable is
-- false. scrape_status is deliberately not treated as publication state.

ALTER TABLE public.api_public_identities
    DROP CONSTRAINT IF EXISTS api_public_identities_resource_type_check;
ALTER TABLE public.api_public_identities
    ADD CONSTRAINT api_public_identities_resource_type_check
    CHECK (resource_type IN ('brand', 'category', 'model', 'product_line'));

ALTER TABLE public.api_public_identities
    ADD COLUMN IF NOT EXISTS public_id uuid;

CREATE UNIQUE INDEX IF NOT EXISTS api_public_identities_resource_public_id_uidx
    ON public.api_public_identities (resource_type, public_id)
    WHERE public_id IS NOT NULL;

INSERT INTO public.api_public_identities
    (resource_type, source_id, public_key, public_id)
SELECT 'product_line', product_line.id,
       'product_line_' || md5(
           brand_identity.public_key || ':' ||
           category_identity.public_key || ':' || product_line.slug
       ),
       uuid_generate_v5(
           uuid_ns_url(),
           'repairbase:v1:product_line:' || brand_identity.public_key || ':' ||
           category_identity.public_key || ':' || product_line.slug
       )
FROM public.product_lines AS product_line
JOIN public.api_public_identities AS brand_identity
  ON brand_identity.resource_type = 'brand'
 AND brand_identity.source_id = product_line.brand_id
JOIN public.api_public_identities AS category_identity
  ON category_identity.resource_type = 'category'
 AND category_identity.source_id = product_line.category_id
ON CONFLICT (resource_type, source_id) DO NOTHING;

INSERT INTO public.api_public_identities
    (resource_type, source_id, public_key, public_id)
SELECT 'model', model.id,
       'model_' || md5(
           brand_identity.public_key || ':' ||
           category_identity.public_key || ':' || model.slug
       ),
       uuid_generate_v5(
           uuid_ns_url(),
           'repairbase:v1:model:' || brand_identity.public_key || ':' ||
           category_identity.public_key || ':' || model.slug
       )
FROM public.models AS model
JOIN public.api_public_identities AS brand_identity
  ON brand_identity.resource_type = 'brand'
 AND brand_identity.source_id = model.brand_id
JOIN public.api_public_identities AS category_identity
  ON category_identity.resource_type = 'category'
 AND category_identity.source_id = model.category_id
ON CONFLICT (resource_type, source_id) DO NOTHING;

REVOKE SELECT (resource_type, source_id, public_key, public_id)
    ON public.api_public_identities FROM api_public_owner;
REVOKE SELECT (id, brand_id, category_id, product_line_id, name, slug,
               series, release_year)
    ON public.models FROM api_public_owner;
REVOKE SELECT (id, brand_id, category_id, slug)
    ON public.product_lines FROM api_public_owner;

GRANT SELECT (resource_type, source_id, public_key, public_id)
    ON public.api_public_identities TO api_public_owner;
GRANT SELECT (id, brand_id, category_id, product_line_id, name, slug,
              series, release_year)
    ON public.models TO api_public_owner;
GRANT SELECT (id, brand_id, category_id, slug)
    ON public.product_lines TO api_public_owner;

DO $drop_models_projection$
DECLARE
    relation_kind "char";
BEGIN
    SELECT c.relkind INTO relation_kind
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'api_public' AND c.relname = 'models';
    IF relation_kind = 'v' THEN
        EXECUTE 'DROP VIEW api_public.models';
    ELSIF relation_kind = 'm' THEN
        EXECUTE 'DROP MATERIALIZED VIEW api_public.models';
    END IF;
END
$drop_models_projection$;

CREATE MATERIALIZED VIEW api_public.models AS
SELECT model_identity.public_id AS model_id,
       brand_identity.public_key::text AS brand_key,
       category_identity.public_key::text AS category_key,
       product_line_identity.public_key::text AS product_line_key,
       model.name::text COLLATE "C" AS name,
       model.slug::text AS slug,
       NULLIF(btrim(model.series), '')::text COLLATE "C" AS series,
       CASE WHEN model.release_year BETWEEN 1900 AND
                 EXTRACT(YEAR FROM CURRENT_DATE)::integer + 1
            THEN model.release_year::integer
            ELSE NULL::integer
       END AS release_year,
       NULL::text AS manual_url,
       false AS indexable,
       NULL::timestamptz AS updated_at
FROM public.models AS model
JOIN public.brands AS brand
  ON brand.id = model.brand_id
JOIN public.categories AS category
  ON category.id = model.category_id
JOIN public.api_public_identities AS model_identity
  ON model_identity.resource_type = 'model'
 AND model_identity.source_id = model.id
 AND model_identity.public_id IS NOT NULL
JOIN public.api_public_identities AS brand_identity
  ON brand_identity.resource_type = 'brand'
 AND brand_identity.source_id = model.brand_id
JOIN public.api_public_identities AS category_identity
  ON category_identity.resource_type = 'category'
 AND category_identity.source_id = model.category_id
LEFT JOIN public.product_lines AS product_line
  ON product_line.id = model.product_line_id
 AND product_line.brand_id = model.brand_id
 AND product_line.category_id = model.category_id
LEFT JOIN public.api_public_identities AS product_line_identity
  ON product_line_identity.resource_type = 'product_line'
 AND product_line_identity.source_id = product_line.id
WHERE brand.is_active
  AND category.is_active
  AND btrim(model.name) <> ''
  AND model.slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$';

ALTER MATERIALIZED VIEW api_public.models OWNER TO api_public_owner;
REVOKE ALL ON api_public.models FROM PUBLIC, anon, authenticated;
GRANT SELECT ON api_public.models TO anon, authenticated;

DROP INDEX IF EXISTS public.idx_models_public_brand_order;
DROP INDEX IF EXISTS public.idx_models_public_category_order;
DROP INDEX IF EXISTS public.idx_models_public_brand_category_order;

CREATE UNIQUE INDEX api_public_models_id_uidx
    ON api_public.models (model_id);
CREATE UNIQUE INDEX api_public_models_route_uidx
    ON api_public.models (brand_key, category_key, slug);
CREATE INDEX api_public_models_order_idx
    ON api_public.models (name COLLATE "C", model_id);
CREATE INDEX api_public_models_brand_order_idx
    ON api_public.models (brand_key, name COLLATE "C", model_id);
CREATE INDEX api_public_models_category_order_idx
    ON api_public.models (category_key, name COLLATE "C", model_id);
CREATE INDEX api_public_models_brand_category_order_idx
    ON api_public.models
       (brand_key, category_key, name COLLATE "C", model_id);

ANALYZE public.api_public_identities;
ANALYZE api_public.models;

INSERT INTO public.schema_migrations (version, filename)
VALUES ('013', '013_public_api_models.sql')
ON CONFLICT (version) DO NOTHING;

NOTIFY pgrst, 'reload schema';
