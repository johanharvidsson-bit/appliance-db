-- Migration 016: language-independent public error-code catalog.
ALTER TABLE public.api_public_identities DROP CONSTRAINT IF EXISTS api_public_identities_resource_type_check;
ALTER TABLE public.api_public_identities ADD CONSTRAINT api_public_identities_resource_type_check
  CHECK (resource_type IN ('brand','category','model','product_line','fault','error_code'));

INSERT INTO public.api_public_identities(resource_type,source_id,public_key,public_id)
SELECT 'error_code',e.id,'error_code_'||md5(b.public_key||':'||c.public_key||':'||lower(e.code)),
       uuid_generate_v5(uuid_ns_url(),'repairbase:v1:error_code:'||b.public_key||':'||c.public_key||':'||lower(e.code))
FROM public.error_codes e
JOIN public.api_public_identities b ON b.resource_type='brand' AND b.source_id=e.brand_id
JOIN public.api_public_identities c ON c.resource_type='category' AND c.source_id=e.category_id
ON CONFLICT(resource_type,source_id) DO NOTHING;

GRANT SELECT(id,brand_id,category_id,code,short_description,description,severity,diy_possible,last_verified_at)
  ON public.error_codes TO api_public_owner;

CREATE OR REPLACE VIEW api_public.error_codes AS
SELECT i.public_id AS error_code_id,b.public_key::text AS brand_key,c.public_key::text AS category_key,
       e.code::text COLLATE "C" AS code,NULLIF(btrim(e.short_description),'')::text AS short_description,
       NULLIF(btrim(e.description),'')::text AS description,e.severity::text AS severity,
       e.diy_possible::boolean AS diy_possible,
       (e.last_verified_at IS NOT NULL AND NULLIF(btrim(e.short_description),'') IS NOT NULL) AS published,
       e.last_verified_at::timestamptz AS verified_at,e.last_verified_at::timestamptz AS updated_at
FROM public.error_codes e
JOIN public.brands br ON br.id=e.brand_id AND br.is_active
JOIN public.categories cat ON cat.id=e.category_id AND cat.is_active
JOIN public.api_public_identities i ON i.resource_type='error_code' AND i.source_id=e.id AND i.public_id IS NOT NULL
JOIN public.api_public_identities b ON b.resource_type='brand' AND b.source_id=e.brand_id
JOIN public.api_public_identities c ON c.resource_type='category' AND c.source_id=e.category_id
WHERE btrim(e.code)<>'';

ALTER VIEW api_public.error_codes OWNER TO api_public_owner;
REVOKE ALL ON api_public.error_codes FROM PUBLIC,anon,authenticated;
GRANT SELECT ON api_public.error_codes TO anon,authenticated;
INSERT INTO public.schema_migrations(version,filename) VALUES('016','016_public_api_error_codes.sql') ON CONFLICT(version) DO NOTHING;
NOTIFY pgrst,'reload schema';
