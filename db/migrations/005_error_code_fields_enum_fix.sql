-- Migration 005: Fix severity enum + add error_code text fields
--
-- Migration 004 failed because severity is a PostgreSQL enum type (severity_enum),
-- not plain TEXT. This migration handles it correctly.
--
-- Steps:
--   1. Add 'easy' and 'advanced' to severity_enum (idempotent via DO block)
--   2. Add short_description + description columns (IF NOT EXISTS)
--   3. Migrate legacy values: low → easy, high/critical → advanced
--   4. Backfill short_description + description from existing display_text
--   5. Record this migration in schema_migrations

-- ── 1. Extend the severity enum ───────────────────────────────────────────────
-- ALTER TYPE ... ADD VALUE does not support IF NOT EXISTS before PG 12,
-- so we guard with a DO block that checks pg_enum first.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumtypid = 'severity_enum'::regtype
          AND enumlabel = 'easy'
    ) THEN
        ALTER TYPE severity_enum ADD VALUE 'easy';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumtypid = 'severity_enum'::regtype
          AND enumlabel = 'advanced'
    ) THEN
        ALTER TYPE severity_enum ADD VALUE 'advanced';
    END IF;
END $$;

-- ── 2. Add new text columns (idempotent) ──────────────────────────────────────

ALTER TABLE error_codes
    ADD COLUMN IF NOT EXISTS short_description TEXT,
    ADD COLUMN IF NOT EXISTS description        TEXT;

-- ── 3. Migrate legacy severity values ─────────────────────────────────────────
-- Cast through text to avoid enum assignment errors on some PG versions.

UPDATE error_codes
SET severity = 'easy'::severity_enum
WHERE severity::text IN ('low');

UPDATE error_codes
SET severity = 'advanced'::severity_enum
WHERE severity::text IN ('high', 'critical');

-- ── 4. Backfill short_description + description from display_text ──────────────

-- short_description: first sentence (up to first '.'), max 80 chars
UPDATE error_codes
SET short_description = CASE
    WHEN POSITION('.' IN display_text) > 0
        THEN TRIM(LEFT(display_text, POSITION('.' IN display_text) - 1))
    ELSE TRIM(LEFT(display_text, 80))
END
WHERE scrape_status = 'done'
  AND display_text IS NOT NULL
  AND short_description IS NULL;

-- description: full display_text
UPDATE error_codes
SET description = display_text
WHERE scrape_status = 'done'
  AND display_text IS NOT NULL
  AND description IS NULL;

-- ── 5. Record in schema_migrations ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT        PRIMARY KEY,
    filename   TEXT        NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations (version, filename) VALUES
    ('002', '002_add_description_to_article_translations.sql'),
    ('003', '003_add_base_model.sql'),
    ('004', '004_migration_tracking_and_error_code_fields.sql'),
    ('005', '005_error_code_fields_enum_fix.sql')
ON CONFLICT (version) DO NOTHING;
