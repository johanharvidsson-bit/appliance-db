-- Sanitized, idempotent development seed for the five-item worker pilot.
-- Scope: exactly one active brand x one active category x one site locale.
-- Expected Cube Coverage backlog:
--   2 create_model_overview + 1 enrich_model_specs + 2 describe_error_code.
BEGIN;

DO $guard$
BEGIN
    IF current_database() <> 'repair_appliance_dev' THEN
        RAISE EXCEPTION 'gate_b_five_item_pilot is restricted to repair_appliance_dev';
    END IF;
END
$guard$;

-- Preserve prior integration-test rows, but remove them from the frozen pilot scope.
UPDATE public.brands SET is_active = false WHERE slug <> 'samsung' AND is_active;
UPDATE public.categories SET is_active = false WHERE slug_en <> 'washing_machine' AND is_active;
UPDATE public.site_locales SET status = 'disabled', is_default = false
WHERE site_id = 'appliance-repair-base' AND locale <> 'en' AND status = 'active';

INSERT INTO public.locales(code, name, is_active, is_default)
VALUES ('en', 'English', true, true)
ON CONFLICT(code) DO UPDATE SET name = EXCLUDED.name, is_active = true, is_default = true;

INSERT INTO public.site_locales(site_id, locale, is_default, status)
VALUES ('appliance-repair-base', 'en', true, 'active')
ON CONFLICT(site_id, locale) DO UPDATE SET is_default = true, status = 'active';

INSERT INTO public.brands(name, slug, support_url, is_active)
VALUES ('Samsung', 'samsung', 'https://www.samsung.com/support/', true)
ON CONFLICT(slug) DO UPDATE SET name = EXCLUDED.name, support_url = EXCLUDED.support_url, is_active = true;

INSERT INTO public.categories(slug_en, sort_order, is_active)
VALUES ('washing_machine', 10, true)
ON CONFLICT(slug_en) DO UPDATE SET sort_order = EXCLUDED.sort_order, is_active = true;

INSERT INTO public.category_translations(category_id, locale, name, slug)
SELECT c.id, 'en', 'Washing machines', 'washing-machines'
FROM public.categories c WHERE c.slug_en = 'washing_machine'
ON CONFLICT(category_id, locale) DO UPDATE SET name = EXCLUDED.name, slug = EXCLUDED.slug;

INSERT INTO public.models(brand_id, category_id, name, slug, base_model, series, release_year)
SELECT b.id, c.id, v.name, v.slug, v.base_model, 'WF45', v.release_year
FROM public.brands b
CROSS JOIN public.categories c
CROSS JOIN (VALUES
    ('Samsung WF45T6000A Front Load Washer', 'wf45t6000a', 'WF45T6000A', 2020),
    ('Samsung WF45B6300AC Front Load Washer', 'wf45b6300ac', 'WF45B6300AC', 2022)
) AS v(name, slug, base_model, release_year)
WHERE b.slug = 'samsung' AND c.slug_en = 'washing_machine'
ON CONFLICT(brand_id, category_id, slug) DO UPDATE
SET name = EXCLUDED.name, base_model = EXCLUDED.base_model, series = EXCLUDED.series,
    release_year = EXCLUDED.release_year;

INSERT INTO public.api_public_identities(resource_type, source_id, public_key)
SELECT 'brand', id, replace(slug, '-', '_') FROM public.brands WHERE slug = 'samsung'
UNION ALL
SELECT 'category', id, 'washing_machine' FROM public.categories WHERE slug_en = 'washing_machine'
ON CONFLICT(resource_type, source_id) DO NOTHING;

INSERT INTO public.api_public_identities(resource_type, source_id, public_key, public_id)
SELECT 'model', m.id,
       'model_' || md5(bi.public_key || ':' || ci.public_key || ':' || m.slug),
       uuid_generate_v5(uuid_ns_url(), 'repairbase:v1:model:' || bi.public_key || ':' || ci.public_key || ':' || m.slug)
FROM public.models m
JOIN public.api_public_identities bi ON bi.resource_type='brand' AND bi.source_id=m.brand_id
JOIN public.api_public_identities ci ON ci.resource_type='category' AND ci.source_id=m.category_id
WHERE m.slug IN ('wf45t6000a', 'wf45b6300ac')
ON CONFLICT(resource_type, source_id) DO NOTHING;

INSERT INTO public.model_specs(model_id, specs)
SELECT id, '{"capacity_kg": 9}'::jsonb FROM public.models WHERE slug = 'wf45t6000a'
ON CONFLICT(model_id) DO UPDATE SET specs = EXCLUDED.specs;

INSERT INTO public.error_codes(brand_id, category_id, code, short_description, description)
SELECT b.id, c.id, v.code, NULL, NULL
FROM public.brands b
CROSS JOIN public.categories c
CROSS JOIN (VALUES ('4C'), ('5C')) AS v(code)
WHERE b.slug = 'samsung' AND c.slug_en = 'washing_machine'
ON CONFLICT(brand_id, category_id, code) DO NOTHING;

INSERT INTO public.error_code_translations(error_code_id, locale, title, description, publication_status)
SELECT ec.id, 'en', ec.code, NULL, 'published'
FROM public.error_codes ec
JOIN public.brands b ON b.id = ec.brand_id AND b.slug = 'samsung'
JOIN public.categories c ON c.id = ec.category_id AND c.slug_en = 'washing_machine'
WHERE ec.code IN ('4C', '5C')
ON CONFLICT(error_code_id, locale) DO NOTHING;

-- Keep unrelated integration-test codes outside the pilot backlog without deleting them.
INSERT INTO public.error_code_translations(error_code_id, locale, title, description, publication_status)
SELECT ec.id, 'en', ec.code, 'Existing sanitized integration-test description.', 'published'
FROM public.error_codes ec
JOIN public.brands b ON b.id = ec.brand_id AND b.slug = 'samsung'
JOIN public.categories c ON c.id = ec.category_id AND c.slug_en = 'washing_machine'
WHERE ec.code NOT IN ('4C', '5C')
ON CONFLICT(error_code_id, locale) DO UPDATE
SET title = EXCLUDED.title, description = EXCLUDED.description, publication_status = 'published';

INSERT INTO public.site_entity_publications(
    site_id, locale, model_id, publication_status, indexable,
    published_at, reviewed_at, reviewed_by
)
SELECT 'appliance-repair-base', 'en', m.id, 'published', false, now(), now(), 'gate-b-seed'
FROM public.models m
JOIN public.brands b ON b.id = m.brand_id AND b.slug = 'samsung'
JOIN public.categories c ON c.id = m.category_id AND c.slug_en = 'washing_machine'
WHERE m.slug IN ('wf45t6000a', 'wf45b6300ac')
ON CONFLICT(site_id, locale, entity_key) DO UPDATE
SET publication_status = 'published', indexable = false, published_at = now(),
    reviewed_at = now(), reviewed_by = 'gate-b-seed';

REFRESH MATERIALIZED VIEW api_public.models;
REFRESH MATERIALIZED VIEW api_public.model_pages;
REFRESH MATERIALIZED VIEW api_public.sitemap_entries;

DO $verify$
DECLARE findings integer;
BEGIN
    IF (SELECT count(*) FROM public.brands WHERE is_active) <> 1
       OR (SELECT count(*) FROM public.categories WHERE is_active) <> 1
       OR (SELECT count(*) FROM public.site_locales WHERE site_id = 'appliance-repair-base' AND status = 'active') <> 1
       OR (SELECT count(*) FROM public.models m JOIN public.brands b ON b.id=m.brand_id JOIN public.categories c ON c.id=m.category_id WHERE b.slug='samsung' AND c.slug_en='washing_machine') <> 2
       OR (SELECT count(*) FROM public.error_codes ec JOIN public.brands b ON b.id=ec.brand_id JOIN public.categories c ON c.id=ec.category_id WHERE b.slug='samsung' AND c.slug_en='washing_machine' AND ec.code IN ('4C','5C')) <> 2 THEN
        RAISE EXCEPTION 'sanitized pilot cardinality check failed';
    END IF;
END
$verify$;

COMMIT;
