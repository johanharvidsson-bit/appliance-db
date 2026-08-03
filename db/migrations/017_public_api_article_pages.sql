-- Migration 017: localized, published public article pages.
ALTER TABLE public.api_public_identities DROP CONSTRAINT IF EXISTS api_public_identities_resource_type_check;
ALTER TABLE public.api_public_identities ADD CONSTRAINT api_public_identities_resource_type_check
  CHECK (resource_type IN ('brand','category','model','product_line','fault','error_code','article'));

INSERT INTO public.api_public_identities(resource_type,source_id,public_key,public_id)
SELECT 'article',a.id,'article_'||md5(a.article_type||':'||s.public_id::text),
       uuid_generate_v5(uuid_ns_url(),'repairbase:v1:article:'||a.article_type||':'||s.public_id::text)
FROM public.articles a
JOIN public.api_public_identities s ON
  (a.error_code_id IS NOT NULL AND s.resource_type='error_code' AND s.source_id=a.error_code_id) OR
  (a.fault_id IS NOT NULL AND s.resource_type='fault' AND s.source_id=a.fault_id)
WHERE s.public_id IS NOT NULL
ON CONFLICT(resource_type,source_id) DO NOTHING;

GRANT SELECT(id,error_code_id,fault_id,status,article_type,last_updated) ON public.articles TO api_public_owner;
GRANT SELECT(article_id,locale,slug,title_tag,meta_description,h1,description,quick_fix,intro_html,causes_json,
  symptoms_json,steps_json,affected_models_json,when_to_call_technician_html,prevention_html,faq_json,parts_json,
  translation_status,last_updated) ON public.article_translations TO api_public_owner;

CREATE OR REPLACE VIEW api_public.article_pages AS
WITH subjects AS (
 SELECT a.id article_source_id,a.article_type,e.brand_id,e.category_id,ei.public_id subject_id
 FROM public.articles a JOIN public.error_codes e ON e.id=a.error_code_id
 JOIN public.api_public_identities ei ON ei.resource_type='error_code' AND ei.source_id=e.id
 UNION ALL
 SELECT a.id,a.article_type,f.brand_id,f.category_id,fi.public_id
 FROM public.articles a JOIN public.faults f ON f.id=a.fault_id
 JOIN public.api_public_identities fi ON fi.resource_type='fault' AND fi.source_id=f.id
)
SELECT uuid_generate_v5(uuid_ns_url(),'repairbase:v1:article_page:'||ai.public_id::text||':'||t.locale) AS article_page_id,
       ai.public_id AS article_id,s.subject_id,s.article_type::text AS article_type,
       bi.public_key::text AS brand_key,ci.public_key::text AS category_key,t.locale::text COLLATE "C" AS locale,
       t.slug::text AS slug,t.title_tag::text AS title,t.meta_description::text AS description,t.h1::text AS h1,
       t.quick_fix::text,t.intro_html::text,t.causes_json,t.symptoms_json,t.steps_json,t.affected_models_json,
       t.when_to_call_technician_html::text,t.prevention_html::text,t.faq_json,t.parts_json,
       (CASE WHEN t.locale='en' THEN '/'||cp.slug ELSE '/'||t.locale||'/'||cp.slug END||'/'||br.slug||'/'||
        CASE WHEN s.article_type IN ('fault','fault_no_code') THEN 'problems/' ELSE '' END||t.slug||'/')::text AS canonical_path,
       true AS indexable,t.last_updated::timestamptz AS published_at,
       greatest(t.last_updated,a.last_updated)::timestamptz AS updated_at
FROM public.articles a JOIN subjects s ON s.article_source_id=a.id
JOIN public.article_translations t ON t.article_id=a.id AND t.translation_status='published'
JOIN public.brands br ON br.id=s.brand_id AND br.is_active
JOIN public.categories cat ON cat.id=s.category_id AND cat.is_active
JOIN public.api_public_identities ai ON ai.resource_type='article' AND ai.source_id=a.id AND ai.public_id IS NOT NULL
JOIN public.api_public_identities bi ON bi.resource_type='brand' AND bi.source_id=s.brand_id
JOIN public.api_public_identities ci ON ci.resource_type='category' AND ci.source_id=s.category_id
JOIN api_public.category_pages cp ON cp.category_key=ci.public_key AND cp.locale=t.locale
WHERE a.status='published' AND t.slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
  AND btrim(t.h1)<>'' AND NULLIF(btrim(t.meta_description),'') IS NOT NULL;

ALTER VIEW api_public.article_pages OWNER TO api_public_owner;
REVOKE ALL ON api_public.article_pages FROM PUBLIC,anon,authenticated;
GRANT SELECT ON api_public.article_pages TO anon,authenticated;
INSERT INTO public.schema_migrations(version,filename) VALUES('017','017_public_api_article_pages.sql') ON CONFLICT(version) DO NOTHING;
NOTIFY pgrst,'reload schema';
