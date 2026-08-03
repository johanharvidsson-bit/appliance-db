-- Migration 018: public, model-keyed specification documents.
GRANT SELECT(model_id,specs) ON public.model_specs TO api_public_owner;

CREATE OR REPLACE VIEW api_public.model_specs AS
SELECT mi.public_id AS model_id,m.brand_key,m.category_key,
       jsonb_strip_nulls(s.specs) AS specs,
       (jsonb_typeof(s.specs)='object' AND s.specs<>'{}'::jsonb) AS published,
       NULL::timestamptz AS updated_at
FROM public.model_specs s
JOIN public.api_public_identities mi ON mi.resource_type='model' AND mi.source_id=s.model_id AND mi.public_id IS NOT NULL
JOIN api_public.models m ON m.model_id=mi.public_id
WHERE jsonb_typeof(s.specs)='object' AND s.specs<>'{}'::jsonb;

ALTER VIEW api_public.model_specs OWNER TO api_public_owner;
REVOKE ALL ON api_public.model_specs FROM PUBLIC,anon,authenticated;
GRANT SELECT ON api_public.model_specs TO anon,authenticated;
INSERT INTO public.schema_migrations(version,filename) VALUES('018','018_public_api_model_specs.sql') ON CONFLICT(version) DO NOTHING;
NOTIFY pgrst,'reload schema';
