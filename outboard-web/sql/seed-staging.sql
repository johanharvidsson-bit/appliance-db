BEGIN;

INSERT INTO rb_languages (language_code, canonical_name, native_name)
VALUES ('en', 'English', 'English') ON CONFLICT (language_code) DO NOTHING;
INSERT INTO rb_sites (site_key, name, domain, default_language_code, publication_state)
VALUES ('outboard-repair-base', 'OutboardRepairBase', 'staging.outboardrepairbase.test', 'en', 'published')
ON CONFLICT (site_key) DO UPDATE SET publication_state = 'published', updated_at = now();
INSERT INTO rb_site_languages (site_id, language_code)
SELECT site_id, 'en' FROM rb_sites WHERE site_key = 'outboard-repair-base' ON CONFLICT DO NOTHING;
INSERT INTO rb_product_categories (category_key, canonical_name)
VALUES ('outboard-engines', 'Outboard Engines') ON CONFLICT (category_key) DO NOTHING;
INSERT INTO rb_site_categories (site_id, category_id)
SELECT s.site_id, c.category_id FROM rb_sites s, rb_product_categories c
WHERE s.site_key = 'outboard-repair-base' AND c.category_key = 'outboard-engines' ON CONFLICT DO NOTHING;

INSERT INTO rb_manufacturers (manufacturer_key, legal_name) VALUES
  ('yamaha-motor-demo', 'Yamaha Motor demonstration record'),
  ('mercury-marine-demo', 'Mercury Marine demonstration record')
ON CONFLICT (manufacturer_key) DO NOTHING;
INSERT INTO rb_brands (brand_key, manufacturer_id, brand_type, canonical_name)
SELECT 'yamaha', manufacturer_id, 'engine', 'Yamaha' FROM rb_manufacturers WHERE manufacturer_key = 'yamaha-motor-demo'
ON CONFLICT (brand_key) DO NOTHING;
INSERT INTO rb_brands (brand_key, manufacturer_id, brand_type, canonical_name)
SELECT 'mercury', manufacturer_id, 'engine', 'Mercury' FROM rb_manufacturers WHERE manufacturer_key = 'mercury-marine-demo'
ON CONFLICT (brand_key) DO NOTHING;
INSERT INTO rb_site_brands (site_id, brand_id)
SELECT s.site_id, b.brand_id FROM rb_sites s CROSS JOIN rb_brands b
WHERE s.site_key = 'outboard-repair-base' AND b.brand_key IN ('yamaha','mercury') ON CONFLICT DO NOTHING;

INSERT INTO rb_engine_models (model_key, brand_id, category_id, canonical_name, normalized_model_code, horsepower_hp, fuel_type)
SELECT 'yamaha-f150-demo', b.brand_id, c.category_id, 'Yamaha F150', 'F150', 150, 'gasoline'
FROM rb_brands b, rb_product_categories c WHERE b.brand_key = 'yamaha' AND c.category_key = 'outboard-engines'
ON CONFLICT (model_key) DO NOTHING;
INSERT INTO rb_engine_models (model_key, brand_id, category_id, canonical_name, normalized_model_code, horsepower_hp, fuel_type)
SELECT 'mercury-150-fourstroke-demo', b.brand_id, c.category_id, 'Mercury 150 FourStroke', '150-FOURSTROKE', 150, 'gasoline'
FROM rb_brands b, rb_product_categories c WHERE b.brand_key = 'mercury' AND c.category_key = 'outboard-engines'
ON CONFLICT (model_key) DO NOTHING;

INSERT INTO rb_engine_model_translations (engine_model_id, language_code, name, short_description, translation_state)
SELECT engine_model_id, 'en', 'F150', 'A structured demonstration record for a 150 hp Yamaha outboard platform.', 'approved'
FROM rb_engine_models WHERE model_key = 'yamaha-f150-demo' ON CONFLICT (engine_model_id, language_code) DO NOTHING;
INSERT INTO rb_engine_model_translations (engine_model_id, language_code, name, short_description, translation_state)
SELECT engine_model_id, 'en', '150 FourStroke', 'A structured demonstration record for a Mercury 150 hp four-stroke outboard.', 'approved'
FROM rb_engine_models WHERE model_key = 'mercury-150-fourstroke-demo' ON CONFLICT (engine_model_id, language_code) DO NOTHING;

INSERT INTO rb_pages (site_id, language_code, page_type, engine_model_id, route_scope_key, slug, canonical_path)
SELECT s.site_id, 'en', 'engine_model', m.engine_model_id, 'outboard-engines/yamaha', 'yamaha-f150', '/models/yamaha-f150/'
FROM rb_sites s, rb_engine_models m WHERE s.site_key = 'outboard-repair-base' AND m.model_key = 'yamaha-f150-demo'
ON CONFLICT DO NOTHING;
INSERT INTO rb_pages (site_id, language_code, page_type, engine_model_id, route_scope_key, slug, canonical_path)
SELECT s.site_id, 'en', 'engine_model', m.engine_model_id, 'outboard-engines/mercury', 'mercury-150-fourstroke', '/models/mercury-150-fourstroke/'
FROM rb_sites s, rb_engine_models m WHERE s.site_key = 'outboard-repair-base' AND m.model_key = 'mercury-150-fourstroke-demo'
ON CONFLICT DO NOTHING;

INSERT INTO rb_page_revisions (page_id, revision_number, content_hash, publication_snapshot, created_by)
SELECT p.page_id, 1, 'staging-yamaha-f150-v1', '{"family":"Four-stroke outboard","accent":"#2458a6","generation":"Demonstration generation B","modelYears":[2020,2021,2022,2023,2024],"specifications":[["Rated output","150 hp"],["Engine type","Four-stroke"],["Fuel","Gasoline"],["Model code","F150"]],"sources":["Demonstration record — not a sourced technical claim"]}'::jsonb, 'staging-seed'
FROM rb_pages p WHERE p.slug = 'yamaha-f150' AND NOT EXISTS (SELECT 1 FROM rb_page_revisions r WHERE r.page_id = p.page_id);
INSERT INTO rb_page_revisions (page_id, revision_number, content_hash, publication_snapshot, created_by)
SELECT p.page_id, 1, 'staging-mercury-150-v1', '{"family":"Four-stroke outboard","accent":"#c8342d","generation":"Demonstration generation A","modelYears":[2023,2024],"specifications":[["Rated output","150 hp"],["Engine type","Four-stroke"],["Fuel","Gasoline"],["Model code","150-FOURSTROKE"]],"sources":["Demonstration record — not a sourced technical claim"]}'::jsonb, 'staging-seed'
FROM rb_pages p WHERE p.slug = 'mercury-150-fourstroke' AND NOT EXISTS (SELECT 1 FROM rb_page_revisions r WHERE r.page_id = p.page_id);

UPDATE rb_pages p SET publication_state = 'published', index_state = 'noindex', noindex_reason = 'editorial_hold',
  published_revision_id = r.page_revision_id, first_published_at = COALESCE(first_published_at, now()), last_published_at = now()
FROM rb_page_revisions r WHERE r.page_id = p.page_id AND r.revision_number = 1
  AND p.slug IN ('yamaha-f150','mercury-150-fourstroke');

COMMIT;
