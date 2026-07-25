-- ============================================================
-- appliance-db  –  full database schema
-- ============================================================
-- Reconstructed from live Supabase instance (2026-03-16).
-- To apply to a fresh project:
--   1. Run this file in the Supabase SQL editor (Settings → SQL Editor)
--   2. Then apply each migration in db/migrations/ in order
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- used by text-search indexes

-- ── brands ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS brands (
    id                  SERIAL PRIMARY KEY,
    name                TEXT        NOT NULL,
    slug                TEXT        NOT NULL UNIQUE,
    logo_url            TEXT,
    support_url         TEXT,
    manual_base_url     TEXT,
    manualslib_brand_id TEXT,
    scrape_status       TEXT        NOT NULL DEFAULT 'pending',
    last_scraped_at     TIMESTAMPTZ,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── categories ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS categories (
    id          SERIAL PRIMARY KEY,
    slug_en     TEXT        NOT NULL UNIQUE,
    icon_url    TEXT,
    sort_order  INTEGER     NOT NULL DEFAULT 0,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── product_lines ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS product_lines (
    id          SERIAL PRIMARY KEY,
    brand_id    INTEGER     NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    category_id INTEGER     NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    slug        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand_id, category_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_product_lines_brand_cat ON product_lines (brand_id, category_id);

-- ── models ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS models (
    id               SERIAL PRIMARY KEY,
    brand_id         INTEGER     NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    category_id      INTEGER     NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    product_line_id  INTEGER     REFERENCES product_lines(id) ON DELETE SET NULL,
    name             TEXT        NOT NULL,
    slug             TEXT        NOT NULL,
    -- base_model: everything before the first '/' — groups regional variants
    -- e.g. WW90T986DSH/EN  →  WW90T986DSH
    base_model       TEXT,
    release_year     INTEGER,
    manual_url       TEXT,           -- ManualsLib viewer page URL
    manual_pdf_url   TEXT,           -- Direct PDF download URL
    manual_pdf_path  TEXT,           -- Local file path (if DOWNLOAD_MANUALS=true)
    scrape_status    TEXT        NOT NULL DEFAULT 'pending',
    last_scraped_at  TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand_id, category_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_models_brand_cat        ON models (brand_id, category_id);
CREATE INDEX IF NOT EXISTS idx_models_base_model       ON models (brand_id, category_id, base_model);
CREATE INDEX IF NOT EXISTS idx_models_scrape_status    ON models (scrape_status);
CREATE INDEX IF NOT EXISTS idx_models_product_line     ON models (product_line_id);

-- ── product_codes ─────────────────────────────────────────────────────────────
-- One row per market-specific model identifier.
-- market: 'US' | 'EU' | 'GB' | NULL (source-agnostic / ManualsLib derived)

CREATE TABLE IF NOT EXISTS product_codes (
    id            SERIAL PRIMARY KEY,
    model_id      INTEGER     NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    code          TEXT        NOT NULL UNIQUE,
    market        TEXT,
    ean           TEXT,
    retailer_url  TEXT,
    scrape_status TEXT        NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_codes_model    ON product_codes (model_id);
CREATE INDEX IF NOT EXISTS idx_product_codes_market   ON product_codes (market);

-- ── error_codes ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS error_codes (
    id               SERIAL PRIMARY KEY,
    brand_id         INTEGER     NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    category_id      INTEGER     NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    code             TEXT        NOT NULL,
    -- short_description: one-line headline shown on model pages and cards
    -- e.g. "Water supply problem" or "Door not closing properly"
    short_description TEXT,
    -- display_text: raw OCR-extracted context from manual (source material)
    display_text     VARCHAR(500),
    -- description: full synthesised description (2-3 sentences, from enrich_error_codes.py)
    description      TEXT,
    severity         severity_enum NOT NULL DEFAULT 'medium',  -- easy | medium | advanced
    diy_possible     BOOLEAN     NOT NULL DEFAULT TRUE,
    source           TEXT,           -- URL of the best reference source
    scrape_status    TEXT        NOT NULL DEFAULT 'pending',
    last_verified_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand_id, category_id, code)
);

CREATE INDEX IF NOT EXISTS idx_error_codes_brand_cat ON error_codes (brand_id, category_id);

-- ── error_code_product_codes ──────────────────────────────────────────────────
-- Junction table: which product codes exhibit which error codes

CREATE TABLE IF NOT EXISTS error_code_product_codes (
    error_code_id   INTEGER NOT NULL REFERENCES error_codes(id)   ON DELETE CASCADE,
    product_code_id INTEGER NOT NULL REFERENCES product_codes(id) ON DELETE CASCADE,
    PRIMARY KEY (error_code_id, product_code_id)
);

CREATE INDEX IF NOT EXISTS idx_ecpc_product_code ON error_code_product_codes (product_code_id);

-- ── articles ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS articles (
    id               SERIAL PRIMARY KEY,
    error_code_id    INTEGER     NOT NULL REFERENCES error_codes(id) ON DELETE CASCADE,
    author_id        UUID,
    -- status: draft | generating | published | failed | archived
    status           TEXT        NOT NULL DEFAULT 'draft',
    firmware_version TEXT,
    review_flag      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_articles_error_code ON articles (error_code_id);
CREATE INDEX IF NOT EXISTS idx_articles_status     ON articles (status);

-- ── article_translations ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS article_translations (
    id                          SERIAL PRIMARY KEY,
    article_id                  INTEGER     NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    locale                      TEXT        NOT NULL,   -- e.g. 'en', 'sv', 'de'
    slug                        TEXT,
    title_tag                   TEXT,
    meta_description            TEXT,
    h1                          TEXT,
    description                 TEXT,       -- one-sentence fault description (from article generator)
    quick_fix                   TEXT,
    meta_bar_json               JSONB,
    intro_html                  TEXT,
    causes_json                 JSONB,
    symptoms_json               JSONB,
    steps_json                  JSONB,
    affected_models_json        JSONB,
    when_to_call_technician_html TEXT,
    prevention_html             TEXT,
    faq_json                    JSONB,
    parts_json                  JSONB,
    -- translation_status: draft | published | needs_review
    translation_status          TEXT        NOT NULL DEFAULT 'draft',
    translated_by               TEXT,       -- 'claude' | 'human' | null
    source_locale               TEXT        DEFAULT 'en',
    last_updated                TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (article_id, locale)
);

CREATE INDEX IF NOT EXISTS idx_article_translations_article ON article_translations (article_id);
CREATE INDEX IF NOT EXISTS idx_article_translations_locale  ON article_translations (locale);
CREATE INDEX IF NOT EXISTS idx_article_translations_slug    ON article_translations (slug);

-- ── scrape_jobs ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS scrape_jobs (
    id          SERIAL PRIMARY KEY,
    -- target_type: model | manual_pdf | error_code | product_code | article
    target_type TEXT        NOT NULL,
    target_id   INTEGER,
    source_url  TEXT,
    -- job_status: queued | running | done | failed
    job_status  TEXT        NOT NULL DEFAULT 'queued',
    raw_data    TEXT,
    parsed_json JSONB,
    error_log   TEXT,
    retry_count INTEGER     NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at  TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_scrape_jobs_status      ON scrape_jobs (job_status);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_target_type ON scrape_jobs (target_type, target_id);

-- ── schema_migrations ─────────────────────────────────────────────────────────
-- Tracks which migration files have been applied.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT        PRIMARY KEY,  -- e.g. '002', '003'
    filename    TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Mark existing migrations as already applied (they were run manually)
INSERT INTO schema_migrations (version, filename)
VALUES
    ('002', '002_add_description_to_article_translations.sql'),
    ('003', '003_add_base_model.sql')
ON CONFLICT (version) DO NOTHING;
