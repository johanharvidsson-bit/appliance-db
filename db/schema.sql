-- ============================================================
-- appliance-db  –  full database schema
-- ============================================================
-- Reconstructed from the live Supabase instance (2026-07-25) via
-- PostgREST OpenAPI introspection + db/migrations/*.sql history.
-- This version supersedes the 2026-03-16 reconstruction, which had
-- drifted from production (several tables were added directly in
-- the Supabase SQL editor and never committed: category_translations,
-- locales, symptom_translations, symptoms, parts, authors,
-- error_code_parts, error_code_symptoms).
--
-- NOT included: three reporting views that exist in Supabase but are
-- not queried by any pipeline/scraper/theme code (verified via repo
-- grep) — v_translation_progress, v_scrape_queue,
-- v_samsung_washing_machine_errors. Recreate manually if needed; their
-- view definitions aren't recoverable via REST introspection.
--
-- To apply to a fresh Postgres instance (self-hosted or Supabase):
--   psql "$DB_URL" -f db/schema.sql
--   Then apply each file in db/migrations/ in order (schema_migrations
--   bootstrap rows below already mark 002–009 as applied for a fresh
--   install built from this file, since their effects are baked in).
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- used by text-search indexes

-- ── enums ─────────────────────────────────────────────────────────────────────

CREATE TYPE scrape_status_enum AS ENUM ('pending', 'in_progress', 'done', 'failed', 'skipped');
CREATE TYPE severity_enum AS ENUM ('low', 'medium', 'high', 'critical', 'easy', 'advanced');
CREATE TYPE scrape_target_enum AS ENUM ('brand', 'category', 'product_line', 'model', 'product_code', 'error_code', 'manual_pdf', 'symptom', 'part');
CREATE TYPE job_status_enum AS ENUM ('queued', 'running', 'done', 'failed', 'skipped');
CREATE TYPE translation_status_enum AS ENUM ('pending', 'auto', 'reviewed', 'published');
CREATE TYPE translated_by_enum AS ENUM ('claude', 'gpt-4o', 'human', 'hybrid');
CREATE TYPE article_status_enum AS ENUM ('pending_translation', 'draft', 'review', 'published', 'stale', 'archived');
CREATE TYPE relevance_enum AS ENUM ('required', 'likely', 'possible');

-- ── locales ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS locales (
    code       VARCHAR(10) PRIMARY KEY,
    name       VARCHAR(50) NOT NULL,
    is_active  BOOLEAN     NOT NULL DEFAULT FALSE,
    is_default BOOLEAN     NOT NULL DEFAULT FALSE
);

-- ── brands ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS brands (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    slug                VARCHAR(100) NOT NULL UNIQUE,
    logo_url            VARCHAR(500),
    support_url         VARCHAR(500),
    manual_base_url     VARCHAR(500),
    manualslib_brand_id VARCHAR(100),
    scrape_status       scrape_status_enum NOT NULL DEFAULT 'pending',
    last_scraped_at     TIMESTAMPTZ,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── categories ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS categories (
    id          SERIAL PRIMARY KEY,
    slug_en     VARCHAR(100) NOT NULL UNIQUE,
    icon_url    VARCHAR(500),
    sort_order  SMALLINT    NOT NULL DEFAULT 0,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── category_translations ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS category_translations (
    id          SERIAL PRIMARY KEY,
    category_id INTEGER     NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    locale      VARCHAR(10) NOT NULL REFERENCES locales(code),
    name        VARCHAR(100) NOT NULL,
    slug        VARCHAR(100) NOT NULL,
    UNIQUE (category_id, locale)
);

CREATE INDEX IF NOT EXISTS idx_category_translations_locale ON category_translations (locale);

-- ── product_lines ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS product_lines (
    id          SERIAL PRIMARY KEY,
    brand_id    INTEGER     NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    category_id INTEGER     NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(200) NOT NULL,
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
    name             VARCHAR(200) NOT NULL,
    slug             VARCHAR(200) NOT NULL,
    -- base_model: everything before the first '/' — groups regional variants
    -- e.g. WW90T986DSH/EN  →  WW90T986DSH
    base_model       TEXT,
    -- series: model family grouping key shown in the UI, e.g. WW80K, WF45T
    series           TEXT,
    release_year     SMALLINT,
    manual_url       VARCHAR(500),   -- ManualsLib viewer page URL
    manual_pdf_url   VARCHAR(500),   -- Direct PDF download URL
    manual_pdf_path  VARCHAR(500),   -- Local file path (if DOWNLOAD_MANUALS=true)
    scrape_status    scrape_status_enum NOT NULL DEFAULT 'pending',
    last_scraped_at  TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand_id, category_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_models_brand_cat        ON models (brand_id, category_id);
CREATE INDEX IF NOT EXISTS idx_models_base_model       ON models (brand_id, category_id, base_model);
CREATE INDEX IF NOT EXISTS idx_models_series           ON models (series);
CREATE INDEX IF NOT EXISTS idx_models_scrape_status    ON models (scrape_status);
CREATE INDEX IF NOT EXISTS idx_models_product_line     ON models (product_line_id);

-- ── product_codes ─────────────────────────────────────────────────────────────
-- One row per market-specific model identifier.
-- market: 'US' | 'EU' | 'GB' | NULL (source-agnostic / ManualsLib derived)

CREATE TABLE IF NOT EXISTS product_codes (
    id            SERIAL PRIMARY KEY,
    model_id      INTEGER     NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    code          VARCHAR(100) NOT NULL UNIQUE,
    market        VARCHAR(10),
    ean           VARCHAR(20),
    retailer_url  VARCHAR(500),
    scrape_status scrape_status_enum NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_codes_model    ON product_codes (model_id);
CREATE INDEX IF NOT EXISTS idx_product_codes_market   ON product_codes (market);

-- ── error_codes ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS error_codes (
    id                SERIAL PRIMARY KEY,
    brand_id          INTEGER     NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    category_id       INTEGER     NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    code              VARCHAR(50) NOT NULL,
    -- short_description: one-line headline shown on model pages and cards
    short_description TEXT,
    -- display_text: raw OCR-extracted context from manual (source material)
    display_text      VARCHAR(500),
    -- description: full synthesised description (2-3 sentences, from enrich_error_codes.py)
    description       TEXT,
    severity          severity_enum NOT NULL DEFAULT 'medium',
    diy_possible      BOOLEAN     NOT NULL DEFAULT TRUE,
    source            VARCHAR(500),   -- URL of the best reference source
    scrape_status     scrape_status_enum NOT NULL DEFAULT 'pending',
    last_verified_at  TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand_id, category_id, code)
);

CREATE INDEX IF NOT EXISTS idx_error_codes_brand_cat ON error_codes (brand_id, category_id);

-- ── error_code_product_codes ──────────────────────────────────────────────────
-- Junction table: which product codes exhibit which error codes

CREATE TABLE IF NOT EXISTS error_code_product_codes (
    error_code_id       INTEGER NOT NULL REFERENCES error_codes(id)   ON DELETE CASCADE,
    product_code_id     INTEGER NOT NULL REFERENCES product_codes(id) ON DELETE CASCADE,
    model_specific_note TEXT,
    PRIMARY KEY (error_code_id, product_code_id)
);

CREATE INDEX IF NOT EXISTS idx_ecpc_product_code ON error_code_product_codes (product_code_id);

-- ── parts ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS parts (
    id            SERIAL PRIMARY KEY,
    brand_id      INTEGER     NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name          VARCHAR(200) NOT NULL,
    part_number   VARCHAR(100) NOT NULL,
    affiliate_url VARCHAR(500),
    avg_price_sek NUMERIC,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_parts_brand ON parts (brand_id);

-- ── error_code_parts ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS error_code_parts (
    error_code_id INTEGER NOT NULL REFERENCES error_codes(id) ON DELETE CASCADE,
    part_id       INTEGER NOT NULL REFERENCES parts(id)       ON DELETE CASCADE,
    relevance     relevance_enum NOT NULL DEFAULT 'likely',
    PRIMARY KEY (error_code_id, part_id)
);

CREATE INDEX IF NOT EXISTS idx_ecp_part ON error_code_parts (part_id);

-- ── symptoms ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS symptoms (
    id          SERIAL PRIMARY KEY,
    category_id INTEGER     NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    slug_en     VARCHAR(200) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_symptoms_category ON symptoms (category_id);

-- ── symptom_translations ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS symptom_translations (
    id          SERIAL PRIMARY KEY,
    symptom_id  INTEGER     NOT NULL REFERENCES symptoms(id) ON DELETE CASCADE,
    locale      VARCHAR(10) NOT NULL REFERENCES locales(code),
    description VARCHAR(500) NOT NULL,
    slug        VARCHAR(200) NOT NULL,
    UNIQUE (symptom_id, locale)
);

CREATE INDEX IF NOT EXISTS idx_symptom_translations_locale ON symptom_translations (locale);

-- ── error_code_symptoms ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS error_code_symptoms (
    error_code_id INTEGER NOT NULL REFERENCES error_codes(id) ON DELETE CASCADE,
    symptom_id    INTEGER NOT NULL REFERENCES symptoms(id)    ON DELETE CASCADE,
    PRIMARY KEY (error_code_id, symptom_id)
);

CREATE INDEX IF NOT EXISTS idx_ecs_symptom ON error_code_symptoms (symptom_id);

-- ── authors ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS authors (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    bio_html    TEXT,
    credentials VARCHAR(500),
    photo_url   VARCHAR(500),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── faults ─────────────────────────────────────────────────────────────────────
--
-- Faults are human-observed symptoms (e.g. "Washing machine won't drain")
-- scoped at brand + category level. Every model page for a given brand +
-- category shows the same fault list — no per-model join table needed.

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

-- ── fault_translations ─────────────────────────────────────────────────────────
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

-- ── fault_error_code_map ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fault_error_code_map (
    fault_id      INTEGER NOT NULL REFERENCES faults(id)       ON DELETE CASCADE,
    error_code_id INTEGER NOT NULL REFERENCES error_codes(id)  ON DELETE CASCADE,
    PRIMARY KEY (fault_id, error_code_id)
);

CREATE INDEX IF NOT EXISTS idx_fecm_error_code ON fault_error_code_map (error_code_id);

-- ── articles ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS articles (
    id               SERIAL PRIMARY KEY,
    error_code_id    INTEGER     REFERENCES error_codes(id) ON DELETE CASCADE,
    fault_id         INTEGER     REFERENCES faults(id)      ON DELETE CASCADE,
    author_id        INTEGER     REFERENCES authors(id),
    status           article_status_enum NOT NULL DEFAULT 'pending_translation',
    firmware_version VARCHAR(50),
    review_flag      BOOLEAN     NOT NULL DEFAULT FALSE,
    article_type     TEXT        NOT NULL DEFAULT 'error_code',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT articles_article_type_check
        CHECK (article_type IN ('error_code', 'fault', 'fault_no_code')),
    CONSTRAINT articles_requires_subject
        CHECK (
            (error_code_id IS NOT NULL AND fault_id IS NULL)
            OR
            (fault_id IS NOT NULL AND error_code_id IS NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_articles_error_code ON articles (error_code_id);
CREATE INDEX IF NOT EXISTS idx_articles_fault      ON articles (fault_id);
CREATE INDEX IF NOT EXISTS idx_articles_status     ON articles (status);

-- ── article_translations ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS article_translations (
    id                          SERIAL PRIMARY KEY,
    article_id                  INTEGER     NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    locale                      VARCHAR(10) NOT NULL REFERENCES locales(code),
    slug                        VARCHAR(300),
    title_tag                   VARCHAR(70),
    meta_description            VARCHAR(165),
    h1                          VARCHAR(200),
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
    translation_status          translation_status_enum NOT NULL DEFAULT 'pending',
    translated_by               translated_by_enum,
    source_locale               VARCHAR(10) REFERENCES locales(code) DEFAULT 'en',
    last_updated                TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (article_id, locale)
);

CREATE INDEX IF NOT EXISTS idx_article_translations_article ON article_translations (article_id);
CREATE INDEX IF NOT EXISTS idx_article_translations_locale  ON article_translations (locale);
CREATE INDEX IF NOT EXISTS idx_article_translations_slug    ON article_translations (slug);

-- ── washing_machine_specs ───────────────────────────────────────────────────────
--
-- Dedicated typed table for washing machine specs.
-- Design rationale:
--   - Individual typed columns (not JSONB) for type safety and query performance
--   - Adding new nullable columns is instant in PostgreSQL (no table rewrite)
--   - Separate table per appliance type keeps the models table clean
--   - All values stored in SI units; imperial conversion happens at render time
--
-- To add a new appliance type later, create a new table (e.g. dishwasher_specs)
-- following the same pattern.

CREATE TABLE IF NOT EXISTS washing_machine_specs (
    model_id                INTEGER PRIMARY KEY REFERENCES models(id) ON DELETE CASCADE,
    capacity_kg             NUMERIC(4,1),
    spin_speed_rpm          INTEGER,
    energy_class            TEXT,
    width_mm                INTEGER,
    height_mm               INTEGER,
    depth_mm                INTEGER,
    noise_spinning_db       NUMERIC(4,1),
    energy_consumption_kwh  NUMERIC(6,1),
    water_consumption_l     NUMERIC(6,1),
    door_type               TEXT,
    scraped_at              TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT wm_specs_door_type_check CHECK (door_type IN ('front', 'top'))
);

CREATE INDEX IF NOT EXISTS idx_wm_specs_model ON washing_machine_specs (model_id);

-- ── scrape_jobs ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS scrape_jobs (
    id           SERIAL PRIMARY KEY,
    target_type  scrape_target_enum NOT NULL,
    target_id    INTEGER,
    source_url   VARCHAR(500),
    job_status   job_status_enum NOT NULL DEFAULT 'queued',
    raw_data     TEXT,
    parsed_json  JSONB,
    error_log    TEXT,
    retry_count  SMALLINT    NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_scrape_jobs_status      ON scrape_jobs (job_status);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_target_type ON scrape_jobs (target_type, target_id);

-- ── schema_migrations ─────────────────────────────────────────────────────────
-- Tracks which migration files have been applied.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT        PRIMARY KEY,
    filename    TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- This file already bakes in the effects of migrations 002–009, so mark
-- them applied on a fresh install to keep apply_migration.py's tracking
-- consistent (it will skip them as no-ops).
INSERT INTO schema_migrations (version, filename)
VALUES
    ('002', '002_add_description_to_article_translations.sql'),
    ('003', '003_add_base_model.sql'),
    ('004', '004_migration_tracking_and_error_code_fields.sql'),
    ('005', '005_error_code_fields_enum_fix.sql'),
    ('006', '006_add_series_to_models.sql'),
    ('007', '007_faults.sql'),
    ('008', '008_model_specs.sql'),
    ('009', '009_delete_marketplace_stub_models.sql')
ON CONFLICT (version) DO NOTHING;

-- ── Row-level security ─────────────────────────────────────────────────────────
-- All content here is public (appliance repair articles/specs), so every
-- table gets a blanket "public read" policy. Writes only ever happen via
-- the service_role, which bypasses RLS entirely (see roles.sql).

DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN
        SELECT unnest(ARRAY[
            'locales','brands','categories','category_translations','product_lines',
            'models','product_codes','error_codes','error_code_product_codes',
            'parts','error_code_parts','symptoms','symptom_translations',
            'error_code_symptoms','authors','faults','fault_translations',
            'fault_error_code_map','articles','article_translations',
            'washing_machine_specs','scrape_jobs','schema_migrations'
        ])
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY "public read %1$s" ON %1$I FOR SELECT USING (true)', t
        );
    END LOOP;
END $$;
