-- Transactional integration fixture for migrations 011-013.
-- It uses real marketed model identities but intentionally synthetic generation
-- keys and no technical claims. ROLLBACK guarantees it cannot become content.
BEGIN;

INSERT INTO rb_product_categories (category_key, canonical_name)
VALUES ('fixture-outboard-engines', 'Outboard Engines fixture');

INSERT INTO rb_sites (site_key, name, domain, default_language_code)
VALUES ('fixture-outboard-repair-base', 'OutboardRepairBase fixture', 'fixture.invalid', 'en');

INSERT INTO rb_site_languages (site_id, language_code)
SELECT site_id, language_code FROM rb_sites CROSS JOIN (VALUES ('en'), ('sv')) AS l(language_code)
WHERE site_key = 'fixture-outboard-repair-base';

INSERT INTO rb_site_categories (site_id, category_id)
SELECT s.site_id, c.category_id FROM rb_sites s, rb_product_categories c
WHERE s.site_key = 'fixture-outboard-repair-base' AND c.category_key = 'fixture-outboard-engines';

INSERT INTO rb_manufacturers (manufacturer_key, legal_name) VALUES
    ('fixture-yamaha-manufacturer', 'Yamaha fixture'),
    ('fixture-mercury-manufacturer', 'Mercury fixture');
INSERT INTO rb_brands (brand_key, manufacturer_id, brand_type, canonical_name)
SELECT 'fixture-yamaha', manufacturer_id, 'engine', 'Yamaha'
FROM rb_manufacturers WHERE manufacturer_key = 'fixture-yamaha-manufacturer'
UNION ALL
SELECT 'fixture-mercury', manufacturer_id, 'engine', 'Mercury'
FROM rb_manufacturers WHERE manufacturer_key = 'fixture-mercury-manufacturer';

INSERT INTO rb_site_brands (site_id, brand_id)
SELECT s.site_id, b.brand_id FROM rb_sites s CROSS JOIN rb_brands b
WHERE s.site_key = 'fixture-outboard-repair-base'
  AND b.brand_key IN ('fixture-yamaha','fixture-mercury');

INSERT INTO rb_engine_models (
    model_key, brand_id, category_id, canonical_name, normalized_model_code, horsepower_hp, fuel_type
)
SELECT 'fixture-yamaha-f150', b.brand_id, c.category_id, 'Yamaha F150', 'F150', 150, 'gasoline'
FROM rb_brands b, rb_product_categories c
WHERE b.brand_key = 'fixture-yamaha' AND c.category_key = 'fixture-outboard-engines'
UNION ALL
SELECT 'fixture-mercury-150-fourstroke', b.brand_id, c.category_id,
       'Mercury 150 FourStroke', '150-FOURSTROKE', 150, 'gasoline'
FROM rb_brands b, rb_product_categories c
WHERE b.brand_key = 'fixture-mercury' AND c.category_key = 'fixture-outboard-engines';

-- Two synthetic technical generations prove that one marketed identity can
-- resolve different scopes. They are not statements about actual production.
INSERT INTO rb_engine_generations (engine_model_id, generation_key, generation_name) SELECT
    engine_model_id, 'fixture-generation-a', 'Fixture generation A'
FROM rb_engine_models WHERE model_key = 'fixture-yamaha-f150';
INSERT INTO rb_engine_generations (engine_model_id, generation_key, generation_name) SELECT
    engine_model_id, 'fixture-generation-b', 'Fixture generation B'
FROM rb_engine_models WHERE model_key = 'fixture-yamaha-f150';
INSERT INTO rb_engine_generations (engine_model_id, generation_key, generation_name) SELECT
    engine_model_id, 'fixture-generation-a', 'Fixture generation A'
FROM rb_engine_models WHERE model_key = 'fixture-mercury-150-fourstroke';

INSERT INTO rb_model_years (engine_generation_id, model_year)
SELECT engine_generation_id, 2024 FROM rb_engine_generations WHERE generation_key = 'fixture-generation-b';

INSERT INTO rb_applicability_sets (applicability_key, name)
VALUES ('fixture-yamaha-f150-generation-b', 'Fixture Yamaha generation B');
INSERT INTO rb_applicability_rules (applicability_set_id, engine_generation_id, model_year_start)
SELECT a.applicability_set_id, g.engine_generation_id, 2020
FROM rb_applicability_sets a
JOIN rb_engine_generations g ON g.generation_key = 'fixture-generation-b'
JOIN rb_engine_models m ON m.engine_model_id = g.engine_model_id
WHERE a.applicability_key = 'fixture-yamaha-f150-generation-b'
  AND m.model_key = 'fixture-yamaha-f150';

INSERT INTO rb_engine_model_translations (engine_model_id, language_code, name, translation_state)
SELECT engine_model_id, 'en', canonical_name, 'approved'
FROM rb_engine_models WHERE model_key IN ('fixture-yamaha-f150','fixture-mercury-150-fourstroke');

INSERT INTO rb_hreflang_clusters (cluster_key) VALUES ('fixture-yamaha-f150-model');
INSERT INTO rb_pages (
    site_id, language_code, page_type, engine_model_id, route_scope_key,
    slug, canonical_path, hreflang_cluster_id
)
SELECT s.site_id, 'en', 'engine_model', m.engine_model_id, 'outboard/yamaha',
       'f150', '/en/outboard-engines/yamaha/f150/', h.hreflang_cluster_id
FROM rb_sites s, rb_engine_models m, rb_hreflang_clusters h
WHERE s.site_key = 'fixture-outboard-repair-base'
  AND m.model_key = 'fixture-yamaha-f150'
  AND h.cluster_key = 'fixture-yamaha-f150-model';

DO $$
DECLARE generation_count INTEGER;
BEGIN
    SELECT count(*) INTO generation_count
    FROM rb_engine_generations g
    JOIN rb_engine_models m ON m.engine_model_id = g.engine_model_id
    WHERE m.model_key = 'fixture-yamaha-f150';
    IF generation_count <> 2 THEN
        RAISE EXCEPTION 'fixture expected two Yamaha F150 generations, got %', generation_count;
    END IF;
END $$;

ROLLBACK;
