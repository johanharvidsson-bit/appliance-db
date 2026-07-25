-- Migration 009: Delete marketplace stub model rows
--
-- Models with no manual_url were created by marketplace scrapers
-- (eSpares, FixPart, AppliancePartsPros) before match_existing_only=True
-- was enforced. They have no manual content and produce empty model pages.
--
-- Safe to delete because:
--   - manual_url IS NULL means ManualsLib scraper never created them
--   - ON DELETE CASCADE removes orphaned product_codes automatically
--   - The match_existing_only fix prevents new stubs from being created
--
-- Affected: ~41,861 rows across Samsung, Bosch, Siemens, Electrolux
--           washing-machines (the only category with marketplace scraper data)

DELETE FROM models
WHERE manual_url IS NULL
  AND brand_id IN (
    SELECT id FROM brands WHERE slug IN ('samsung','bosch','siemens','electrolux','lg')
  );

INSERT INTO schema_migrations (version, filename) VALUES
    ('009', '009_delete_marketplace_stub_models.sql')
ON CONFLICT (version) DO NOTHING;
