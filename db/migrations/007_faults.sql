-- Migration 007: Fault concept
--
-- Faults are human-observed symptoms (e.g. "Washing machine won't drain")
-- scoped at brand + category level. Every model page for a given brand +
-- category shows the same fault list — no per-model join table needed.
--
-- New tables:
--   faults               — one row per symptom per brand/category
--   fault_translations   — label + meta for model-page sections (not full article)
--   fault_error_code_map — many-to-many: which error codes relate to each fault
--
-- Altered tables:
--   articles             — error_code_id made nullable; fault_id + article_type added


-- ── faults ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS faults (
    id             SERIAL PRIMARY KEY,
    brand_id       INTEGER     NOT NULL REFERENCES brands(id)     ON DELETE CASCADE,
    category_id    INTEGER     NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    slug           TEXT        NOT NULL,
    canonical_name TEXT        NOT NULL,   -- e.g. "Washing machine won't drain"
    severity       TEXT,                   -- 'easy' | 'medium' | 'advanced'
    has_error_code BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand_id, category_id, slug),
    CONSTRAINT faults_severity_check CHECK (severity IN ('easy', 'medium', 'advanced'))
);

CREATE INDEX IF NOT EXISTS idx_faults_brand_cat ON faults (brand_id, category_id);

-- ── fault_translations ─────────────────────────────────────────────────────
-- Holds only the short label + SEO meta shown in model-page "Common Problems"
-- sections and fault listing pages. Full troubleshooting content lives in
-- article_translations (linked via articles.fault_id).

CREATE TABLE IF NOT EXISTS fault_translations (
    id               SERIAL PRIMARY KEY,
    fault_id         INTEGER     NOT NULL REFERENCES faults(id) ON DELETE CASCADE,
    locale           TEXT        NOT NULL,
    symptom_name     TEXT        NOT NULL,   -- translated label, e.g. "Tvättmaskinen tömmer inte"
    meta_title       TEXT,
    meta_description TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fault_id, locale)
);

CREATE INDEX IF NOT EXISTS idx_fault_translations_fault ON fault_translations (fault_id);

-- ── fault_error_code_map ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fault_error_code_map (
    fault_id      INTEGER NOT NULL REFERENCES faults(id)       ON DELETE CASCADE,
    error_code_id INTEGER NOT NULL REFERENCES error_codes(id)  ON DELETE CASCADE,
    PRIMARY KEY (fault_id, error_code_id)
);

CREATE INDEX IF NOT EXISTS idx_fecm_error_code ON fault_error_code_map (error_code_id);

-- ── articles: make error_code_id nullable, add fault_id + article_type ─────

ALTER TABLE articles
    ALTER COLUMN error_code_id DROP NOT NULL;

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS fault_id     INTEGER REFERENCES faults(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS article_type TEXT    NOT NULL DEFAULT 'error_code';

ALTER TABLE articles
    ADD CONSTRAINT articles_article_type_check
    CHECK (article_type IN ('error_code', 'fault', 'fault_no_code'));

-- Backfill: existing rows are all error_code articles
UPDATE articles SET article_type = 'error_code' WHERE article_type IS NULL OR article_type = '';

-- Constraint: every article must reference exactly one of error_code_id or fault_id
ALTER TABLE articles
    ADD CONSTRAINT articles_requires_subject
    CHECK (
        (error_code_id IS NOT NULL AND fault_id IS NULL)
        OR
        (fault_id IS NOT NULL AND error_code_id IS NULL)
    );

CREATE INDEX IF NOT EXISTS idx_articles_fault ON articles (fault_id);

-- ── RLS ────────────────────────────────────────────────────────────────────

ALTER TABLE faults              ENABLE ROW LEVEL SECURITY;
ALTER TABLE fault_translations  ENABLE ROW LEVEL SECURITY;
ALTER TABLE fault_error_code_map ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read faults"
    ON faults FOR SELECT USING (true);

CREATE POLICY "public read fault_translations"
    ON fault_translations FOR SELECT USING (true);

CREATE POLICY "public read fault_error_code_map"
    ON fault_error_code_map FOR SELECT USING (true);

-- ── fix article_translations slug uniqueness ──────────────────────────────
-- The global UNIQUE(locale, slug) constraint is wrong: slugs are already
-- scoped by brand in the URL path (/washing-machines/lg/error-code-ce/).
-- Two different brands can legitimately share the same error code slug.

ALTER TABLE article_translations
    DROP CONSTRAINT IF EXISTS article_translations_locale_slug_key;

-- ── migration tracking ─────────────────────────────────────────────────────

INSERT INTO schema_migrations (version, filename) VALUES
    ('007', '007_faults.sql')
ON CONFLICT (version) DO NOTHING;
