-- Migration 003: Add base_model column to models table
--
-- base_model = the canonical model identifier stripped of regional/market suffixes.
-- Derived by taking everything before the first '/' in the model name.
--
-- Examples:
--   WW90T986DSH/EN   → WW90T986DSH
--   WW90T986DSH/LEV  → WW90T986DSH
--   WF45T6000AW/A4   → WF45T6000AW
--   WW90T986DSH      → WW90T986DSH  (already a base model)
--
-- Used to group regional variants under one model page on the site.

ALTER TABLE models ADD COLUMN IF NOT EXISTS base_model TEXT;

-- Populate: everything before the first '/', trimmed
UPDATE models
SET base_model = TRIM(SPLIT_PART(name, '/', 1))
WHERE base_model IS NULL;

-- Index for fast lookups (model browser pages, variant grouping)
CREATE INDEX IF NOT EXISTS idx_models_base_model ON models (brand_id, category_id, base_model);
