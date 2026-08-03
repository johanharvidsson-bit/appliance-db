-- Migration 017: publication-safe v1 frontend compatibility projections.
-- Public URLs, redirects, canonicals and sitemap entries are unchanged.
BEGIN;

DROP POLICY IF EXISTS "api public owner verified variants" ON public.model_variants;
CREATE POLICY "api public owner verified variants" ON public.model_variants
    FOR SELECT TO api_public_owner USING(status='verified');
DROP POLICY IF EXISTS "api public owner published model content" ON public.model_content_translations;
CREATE POLICY "api public owner published model content" ON public.model_content_translations
    FOR SELECT TO api_public_owner USING(publication_status='published');
DROP POLICY IF EXISTS "api public owner published error content" ON public.error_code_translations;
CREATE POLICY "api public owner published error content" ON public.error_code_translations
    FOR SELECT TO api_public_owner USING(publication_status='published');
DROP POLICY IF EXISTS "api public owner published guides" ON public.guides;
CREATE POLICY "api public owner published guides" ON public.guides
    FOR SELECT TO api_public_owner USING(content_status='published');
DROP POLICY IF EXISTS "api public owner published guide content" ON public.guide_translations;
CREATE POLICY "api public owner published guide content" ON public.guide_translations
    FOR SELECT TO api_public_owner USING(publication_status='published');
DROP POLICY IF EXISTS "api public owner verified guide errors" ON public.guide_error_codes;
CREATE POLICY "api public owner verified guide errors" ON public.guide_error_codes
    FOR SELECT TO api_public_owner USING(relation_status='verified');
DROP POLICY IF EXISTS "api public owner verified guide faults" ON public.guide_faults;
CREATE POLICY "api public owner verified guide faults" ON public.guide_faults
    FOR SELECT TO api_public_owner USING(relation_status='verified');
DROP POLICY IF EXISTS "api public owner verified guide models" ON public.guide_models;
CREATE POLICY "api public owner verified guide models" ON public.guide_models
    FOR SELECT TO api_public_owner USING(relation_status='verified');

GRANT SELECT(id,model_id,variant_code,normalized_variant_code,market,region,description,status)
    ON public.model_variants TO api_public_owner;
GRANT SELECT(model_id,locale,overview,short_summary,publication_status)
    ON public.model_content_translations TO api_public_owner;
GRANT SELECT(error_code_id,locale,title,description,first_checks,publication_status)
    ON public.error_code_translations TO api_public_owner;
GRANT SELECT(id,category_id,brand_id,canonical_title,default_difficulty,default_estimated_minutes,safety_notes,is_general,content_status)
    ON public.guides TO api_public_owner;
GRANT SELECT(guide_id,locale,slug,title,short_description,summary,steps_json,publication_status)
    ON public.guide_translations TO api_public_owner;
GRANT SELECT(guide_id,error_code_id,is_primary,sort_order,relation_status)
    ON public.guide_error_codes TO api_public_owner;
GRANT SELECT(guide_id,fault_id,is_primary,sort_order,relation_status)
    ON public.guide_faults TO api_public_owner;
GRANT SELECT(guide_id,model_id,applicability,relation_status)
    ON public.guide_models TO api_public_owner;
GRANT SELECT(id,brand_id,category_id,code) ON public.error_codes TO api_public_owner;
GRANT SELECT(id,brand_id,category_id,slug) ON public.faults TO api_public_owner;

DROP VIEW IF EXISTS api_public.model_page_guides_v1;
DROP VIEW IF EXISTS api_public.guide_models_v1;
DROP VIEW IF EXISTS api_public.guide_topics_v1;
DROP VIEW IF EXISTS api_public.guides_v1;
DROP VIEW IF EXISTS api_public.error_code_content_v1;
DROP VIEW IF EXISTS api_public.model_content_v1;
DROP VIEW IF EXISTS api_public.model_variants_v1;

CREATE VIEW api_public.model_variants_v1 WITH(security_barrier=true) AS
SELECT uuid_generate_v5(uuid_ns_url(),'repairbase:v1:model-variant:'||m.model_id::text||':'||v.normalized_variant_code) AS variant_id,
       m.model_id,
       v.variant_code,
       v.market,
       v.region,
       v.description
FROM public.model_variants v
JOIN api_public.models m ON m.model_id=(
    SELECT i.public_id FROM public.api_public_identities i
    WHERE i.resource_type='model' AND i.source_id=v.model_id
)
WHERE v.status='verified';
ALTER VIEW api_public.model_variants_v1 OWNER TO api_public_owner;

CREATE VIEW api_public.model_content_v1 WITH(security_barrier=true) AS
SELECT i.public_id AS model_id,c.locale,c.overview,c.short_summary
FROM public.model_content_translations c
JOIN public.api_public_identities i ON i.resource_type='model' AND i.source_id=c.model_id
WHERE c.publication_status='published';
ALTER VIEW api_public.model_content_v1 OWNER TO api_public_owner;

CREATE VIEW api_public.error_code_content_v1 WITH(security_barrier=true) AS
SELECT uuid_generate_v5(uuid_ns_url(),'repairbase:v1:error-code:'||e.id::text) AS error_code_id,
       bi.public_key AS brand_key,ci.public_key AS category_key,
       t.locale,e.code,t.title,t.description,t.first_checks
FROM public.error_code_translations t
JOIN public.error_codes e ON e.id=t.error_code_id
JOIN public.api_public_identities bi ON bi.resource_type='brand' AND bi.source_id=e.brand_id
JOIN public.api_public_identities ci ON ci.resource_type='category' AND ci.source_id=e.category_id
WHERE t.publication_status='published';
ALTER VIEW api_public.error_code_content_v1 OWNER TO api_public_owner;

CREATE VIEW api_public.guides_v1 WITH(security_barrier=true) AS
SELECT uuid_generate_v5(uuid_ns_url(),'repairbase:v1:guide:'||g.id::text) AS guide_id,
       ci.public_key AS category_key,bi.public_key AS brand_key,
       t.locale,t.slug,t.title,t.short_description,t.summary,t.steps_json,
       g.default_difficulty,g.default_estimated_minutes,g.safety_notes,g.is_general
FROM public.guides g
JOIN public.guide_translations t ON t.guide_id=g.id
JOIN public.api_public_identities ci ON ci.resource_type='category' AND ci.source_id=g.category_id
LEFT JOIN public.api_public_identities bi ON bi.resource_type='brand' AND bi.source_id=g.brand_id
WHERE g.content_status='published' AND t.publication_status='published';
ALTER VIEW api_public.guides_v1 OWNER TO api_public_owner;

CREATE VIEW api_public.guide_topics_v1 WITH(security_barrier=true) AS
SELECT uuid_generate_v5(uuid_ns_url(),'repairbase:v1:guide:'||r.guide_id::text) AS guide_id,
       'error_code'::text AS topic_type,
       uuid_generate_v5(uuid_ns_url(),'repairbase:v1:error-code:'||r.error_code_id::text) AS topic_id,
       r.is_primary,r.sort_order
FROM public.guide_error_codes r WHERE r.relation_status='verified'
UNION ALL
SELECT uuid_generate_v5(uuid_ns_url(),'repairbase:v1:guide:'||r.guide_id::text),
       'fault'::text,
       uuid_generate_v5(uuid_ns_url(),'repairbase:v1:fault:'||r.fault_id::text),
       r.is_primary,r.sort_order
FROM public.guide_faults r WHERE r.relation_status='verified';
ALTER VIEW api_public.guide_topics_v1 OWNER TO api_public_owner;

CREATE VIEW api_public.guide_models_v1 WITH(security_barrier=true) AS
SELECT uuid_generate_v5(uuid_ns_url(),'repairbase:v1:guide:'||r.guide_id::text) AS guide_id,
       i.public_id AS model_id,r.applicability
FROM public.guide_models r
JOIN public.api_public_identities i ON i.resource_type='model' AND i.source_id=r.model_id
WHERE r.relation_status='verified';
ALTER VIEW api_public.guide_models_v1 OWNER TO api_public_owner;

CREATE VIEW api_public.model_page_guides_v1 WITH(security_barrier=true) AS
SELECT DISTINCT m.model_id,g.guide_id,g.locale,g.slug,g.title,
       g.short_description,g.default_difficulty,g.default_estimated_minutes
FROM api_public.models m
JOIN public.api_public_identities mi ON mi.resource_type='model' AND mi.public_id=m.model_id
JOIN public.models source_model ON source_model.id=mi.source_id
JOIN api_public.guides_v1 g ON g.category_key=m.category_key
  AND (g.brand_key IS NULL OR g.brand_key=m.brand_key)
WHERE NOT EXISTS(
    SELECT 1 FROM api_public.guide_models_v1 deny
    WHERE deny.guide_id=g.guide_id AND deny.model_id=m.model_id
      AND deny.applicability='does_not_apply'
)
AND (
    NOT EXISTS(SELECT 1 FROM api_public.guide_models_v1 scoped WHERE scoped.guide_id=g.guide_id)
    OR EXISTS(
        SELECT 1 FROM api_public.guide_models_v1 allow
        WHERE allow.guide_id=g.guide_id AND allow.model_id=m.model_id
          AND allow.applicability='applies'
    )
);
ALTER VIEW api_public.model_page_guides_v1 OWNER TO api_public_owner;

REVOKE ALL ON api_public.model_variants_v1,api_public.model_content_v1,
    api_public.error_code_content_v1,api_public.guides_v1,api_public.guide_topics_v1,
    api_public.guide_models_v1,api_public.model_page_guides_v1 FROM PUBLIC;
GRANT SELECT ON api_public.model_variants_v1,api_public.model_content_v1,
    api_public.error_code_content_v1,api_public.guides_v1,api_public.guide_topics_v1,
    api_public.guide_models_v1,api_public.model_page_guides_v1 TO anon,authenticated;

INSERT INTO public.schema_migrations(version,filename)
VALUES('017','017_frontend_compatibility_layer.sql') ON CONFLICT(version) DO NOTHING;
NOTIFY pgrst,'reload schema';
COMMIT;
