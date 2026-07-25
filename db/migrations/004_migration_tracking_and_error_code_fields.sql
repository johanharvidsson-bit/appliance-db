-- Migration 004: schema_migrations tracking + error_code description/severity fields
--
-- 1. schema_migrations: tracks which migration files have been applied
--    so apply_migration.py can skip already-applied files safely.
--
-- 2. error_codes.short_description: one-line headline for the error code
--    e.g. "Water supply problem" — shown on model pages, cards, search results.
--
-- 3. error_codes.description: full synthesised 2-3 sentence explanation
--    from enrich_error_codes.py. display_text remains for raw OCR context.
--
-- 4. error_codes.severity: DIY difficulty badge
--    Values: 'easy' | 'medium' | 'advanced'
--    Maps to: Easy (user fix) | Medium (moderate repair) | Advanced (technician)

-- ── schema_migrations ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT        PRIMARY KEY,
    filename   TEXT        NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Mark existing migrations as already applied
INSERT INTO schema_migrations (version, filename) VALUES
    ('002', '002_add_description_to_article_translations.sql'),
    ('003', '003_add_base_model.sql'),
    ('004', '004_migration_tracking_and_error_code_fields.sql')
ON CONFLICT (version) DO NOTHING;

-- ── error_codes: new text fields ──────────────────────────────────────────────

ALTER TABLE error_codes
    ADD COLUMN IF NOT EXISTS short_description TEXT,
    ADD COLUMN IF NOT EXISTS description        TEXT;

-- Change severity to use standardised badge values (easy / medium / advanced)
-- Keep existing DEFAULT 'medium' — just add a check constraint going forward
ALTER TABLE error_codes
    ALTER COLUMN severity SET DEFAULT 'medium';

ALTER TABLE error_codes
    DROP CONSTRAINT IF EXISTS error_codes_severity_check;

ALTER TABLE error_codes
    ADD CONSTRAINT error_codes_severity_check
    CHECK (severity IN ('easy', 'medium', 'advanced'));

-- Normalise any legacy severity values to the new set
UPDATE error_codes SET severity = 'easy'     WHERE severity IN ('low');
UPDATE error_codes SET severity = 'advanced' WHERE severity IN ('high', 'critical');

-- ── Backfill from existing enriched display_text ──────────────────────────────

-- short_description: first sentence of the current display_text
UPDATE error_codes
SET short_description = CASE
    WHEN POSITION('.' IN display_text) > 0
        THEN TRIM(LEFT(display_text, POSITION('.' IN display_text) - 1))
    ELSE TRIM(LEFT(display_text, 80))
END
WHERE scrape_status = 'done'
  AND display_text IS NOT NULL
  AND short_description IS NULL;

-- description: full display_text (it currently holds the synthesised description)
UPDATE error_codes
SET description = display_text
WHERE scrape_status = 'done'
  AND display_text IS NOT NULL
  AND description IS NULL;
