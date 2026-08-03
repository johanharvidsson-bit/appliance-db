-- Migration 015: localized public fault pages.
ALTER TABLE public.api_public_identities DROP CONSTRAINT IF EXISTS api_public_identities_resource_type_check;
ALTER TABLE public.api_public_identities ADD CONSTRAINT api_public_identities_resource_type_check
  CHECK (resource_type IN ('brand','category','model','product_line','fault'));

INSERT INTO public.api_public_identities(resource_type,source_id,public_key,public_id)
SELECT 'fault',f.id,'fault_'||md5(b.public_key||':'||c.public_key||':'||f.slug),
       uuid_generate_v5(uuid_ns_url(),'repairbase:v1:fault:'||b.public_key||':'||c.public_key||':'||f.slug)
FROM public.faults f
JOIN public.api_public_identities b ON b.resource_type='brand' AND b.source_id=f.brand_id
JOIN public.api_public_identities c ON c.resource_type='category' AND c.source_id=f.category_id
ON CONFLICT(resource_type,source_id) DO NOTHING;

GRANT SELECT(id,brand_id,category_id,slug,canonical_name,severity,has_error_code) ON public.faults TO api_public_owner;
GRANT SELECT(fault_id,locale,symptom_name,meta_title,meta_description) ON public.fault_translations TO api_public_owner;

CREATE OR REPLACE VIEW api_public.fault_pages AS
SELECT i.public_id AS fault_page_id,i.public_id AS fault_id,b.public_key::text AS brand_key,
       c.public_key::text AS category_key,t.locale::text COLLATE "C" AS locale,
       f.slug::text AS slug,t.symptom_name::text COLLATE "C" AS name,
       t.meta_title::text AS title,t.meta_description::text AS description,
       (CASE WHEN t.locale='en' THEN '/'||cp.slug ELSE '/'||t.locale||'/'||cp.slug END||
        '/'||br.slug||'/problems/'||f.slug||'/')::text AS canonical_path,
       false AS indexable,NULL::timestamptz AS published_at,NULL::timestamptz AS updated_at
FROM public.faults f
JOIN public.fault_translations t ON t.fault_id=f.id
JOIN public.brands br ON br.id=f.brand_id AND br.is_active
JOIN public.categories cat ON cat.id=f.category_id AND cat.is_active
JOIN public.api_public_identities i ON i.resource_type='fault' AND i.source_id=f.id AND i.public_id IS NOT NULL
JOIN public.api_public_identities b ON b.resource_type='brand' AND b.source_id=f.brand_id
JOIN public.api_public_identities c ON c.resource_type='category' AND c.source_id=f.category_id
JOIN api_public.category_pages cp ON cp.category_key=c.public_key AND cp.locale=t.locale
WHERE f.slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND btrim(t.symptom_name)<>'';

ALTER VIEW api_public.fault_pages OWNER TO api_public_owner;
REVOKE ALL ON api_public.fault_pages FROM PUBLIC,anon,authenticated;
GRANT SELECT ON api_public.fault_pages TO anon,authenticated;
INSERT INTO public.schema_migrations(version,filename) VALUES('015','015_public_api_fault_pages.sql') ON CONFLICT(version) DO NOTHING;
NOTIFY pgrst,'reload schema';
