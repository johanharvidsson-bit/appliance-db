-- RepairBase phase 1a: shared catalog identity and applicability foundation.
-- The rb_ prefix isolates the shared RepairBase platform from the legacy
-- ApplianceRepairBase tables in this database.

CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE rb_languages (
    language_code VARCHAR(35) PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    native_name TEXT NOT NULL,
    is_rtl BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT rb_languages_code_format CHECK (
        language_code ~ '^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$'
    )
);

CREATE TABLE rb_sites (
    site_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_key CITEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    domain CITEXT NOT NULL UNIQUE,
    default_language_code VARCHAR(35) NOT NULL REFERENCES rb_languages(language_code) ON DELETE RESTRICT,
    publication_state TEXT NOT NULL DEFAULT 'draft'
        CHECK (publication_state IN ('draft','review','published','withdrawn','archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ
);

CREATE TABLE rb_site_languages (
    site_id BIGINT NOT NULL REFERENCES rb_sites(site_id) ON DELETE CASCADE,
    language_code VARCHAR(35) NOT NULL REFERENCES rb_languages(language_code) ON DELETE RESTRICT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (site_id, language_code)
);

CREATE OR REPLACE FUNCTION rb_validate_site_default_language()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    affected_site_id BIGINT;
BEGIN
    affected_site_id := CASE
        WHEN TG_TABLE_NAME = 'rb_sites' THEN
            CASE WHEN TG_OP = 'DELETE' THEN OLD.site_id ELSE NEW.site_id END
        ELSE
            CASE WHEN TG_OP = 'DELETE' THEN OLD.site_id ELSE NEW.site_id END
    END;
    IF EXISTS (SELECT 1 FROM rb_sites s WHERE s.site_id = affected_site_id)
       AND NOT EXISTS (
           SELECT 1
           FROM rb_sites s
           JOIN rb_site_languages sl
             ON sl.site_id = s.site_id
            AND sl.language_code = s.default_language_code
            AND sl.is_enabled
           WHERE s.site_id = affected_site_id
       ) THEN
        RAISE EXCEPTION 'site default language must be an enabled site language';
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER rb_sites_default_language_membership
AFTER INSERT OR UPDATE OF default_language_code ON rb_sites
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION rb_validate_site_default_language();
CREATE CONSTRAINT TRIGGER rb_site_languages_preserve_default
AFTER INSERT OR UPDATE OR DELETE ON rb_site_languages
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION rb_validate_site_default_language();

CREATE TABLE rb_product_categories (
    category_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_key CITEXT NOT NULL UNIQUE,
    canonical_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rb_site_categories (
    site_id BIGINT NOT NULL REFERENCES rb_sites(site_id) ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES rb_product_categories(category_id) ON DELETE RESTRICT,
    PRIMARY KEY (site_id, category_id)
);

CREATE TABLE rb_manufacturers (
    manufacturer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manufacturer_key CITEXT NOT NULL UNIQUE,
    legal_name TEXT NOT NULL,
    country_code CHAR(2),
    website_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rb_brands (
    brand_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    brand_key CITEXT NOT NULL UNIQUE,
    manufacturer_id BIGINT REFERENCES rb_manufacturers(manufacturer_id) ON DELETE RESTRICT,
    brand_type TEXT NOT NULL CHECK (brand_type IN ('engine','parts','fluid','multi_category')),
    canonical_name TEXT NOT NULL,
    website_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ
);

CREATE TABLE rb_product_lines (
    product_line_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_line_key CITEXT NOT NULL UNIQUE,
    brand_id BIGINT NOT NULL REFERENCES rb_brands(brand_id) ON DELETE RESTRICT,
    category_id BIGINT NOT NULL REFERENCES rb_product_categories(category_id) ON DELETE RESTRICT,
    canonical_name TEXT NOT NULL,
    production_date_start DATE,
    production_date_end DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    CONSTRAINT rb_product_lines_date_order CHECK (
        production_date_start IS NULL OR production_date_end IS NULL OR production_date_start <= production_date_end
    ),
    UNIQUE (product_line_id, brand_id, category_id)
);

CREATE TABLE rb_engine_models (
    engine_model_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_key CITEXT NOT NULL UNIQUE,
    brand_id BIGINT NOT NULL REFERENCES rb_brands(brand_id) ON DELETE RESTRICT,
    category_id BIGINT NOT NULL REFERENCES rb_product_categories(category_id) ON DELETE RESTRICT,
    product_line_id BIGINT,
    canonical_name TEXT NOT NULL,
    normalized_model_code CITEXT NOT NULL,
    horsepower_hp NUMERIC(7,2) CHECK (horsepower_hp > 0),
    fuel_type TEXT NOT NULL CHECK (fuel_type IN ('gasoline','diesel','electric','other')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    CONSTRAINT rb_engine_models_line_chain_fk
        FOREIGN KEY (product_line_id, brand_id, category_id)
        REFERENCES rb_product_lines(product_line_id, brand_id, category_id) ON DELETE RESTRICT,
    UNIQUE (brand_id, normalized_model_code),
    UNIQUE (engine_model_id, brand_id)
);

CREATE TABLE rb_engine_generations (
    engine_generation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_model_id BIGINT NOT NULL REFERENCES rb_engine_models(engine_model_id) ON DELETE RESTRICT,
    generation_key CITEXT NOT NULL,
    generation_name TEXT,
    engine_platform_code TEXT,
    stroke_type TEXT CHECK (stroke_type IN ('two_stroke','four_stroke','other')),
    engine_configuration TEXT,
    displacement_cc NUMERIC(9,2) CHECK (displacement_cc > 0),
    cylinder_count SMALLINT CHECK (cylinder_count > 0),
    production_date_start DATE,
    production_date_end DATE,
    model_year_start SMALLINT,
    model_year_end SMALLINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    CONSTRAINT rb_engine_generations_date_order CHECK (
        production_date_start IS NULL OR production_date_end IS NULL OR production_date_start <= production_date_end
    ),
    CONSTRAINT rb_engine_generations_year_order CHECK (
        model_year_start IS NULL OR model_year_end IS NULL OR model_year_start <= model_year_end
    ),
    UNIQUE (engine_model_id, generation_key),
    UNIQUE (engine_generation_id, engine_model_id)
);

CREATE TABLE rb_model_variants (
    model_variant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_generation_id BIGINT NOT NULL REFERENCES rb_engine_generations(engine_generation_id) ON DELETE RESTRICT,
    variant_key CITEXT NOT NULL,
    full_model_code CITEXT NOT NULL,
    shaft_length_code TEXT,
    shaft_length_mm NUMERIC(8,2) CHECK (shaft_length_mm > 0),
    rotation_direction TEXT CHECK (rotation_direction IN ('standard','counter','not_applicable','unknown')),
    steering_type TEXT,
    starting_system TEXT,
    trim_system TEXT,
    market_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    UNIQUE (engine_generation_id, variant_key),
    UNIQUE (model_variant_id, engine_generation_id)
);

CREATE TABLE rb_model_years (
    model_year_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_generation_id BIGINT NOT NULL REFERENCES rb_engine_generations(engine_generation_id) ON DELETE RESTRICT,
    model_variant_id BIGINT,
    model_year SMALLINT NOT NULL CHECK (model_year BETWEEN 1900 AND 2200),
    production_date_start DATE,
    production_date_end DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT rb_model_years_variant_chain_fk
        FOREIGN KEY (model_variant_id, engine_generation_id)
        REFERENCES rb_model_variants(model_variant_id, engine_generation_id) ON DELETE RESTRICT,
    CONSTRAINT rb_model_years_date_order CHECK (
        production_date_start IS NULL OR production_date_end IS NULL OR production_date_start <= production_date_end
    )
);

CREATE UNIQUE INDEX rb_model_years_generation_only_uq
    ON rb_model_years (engine_generation_id, model_year)
    WHERE model_variant_id IS NULL;
CREATE UNIQUE INDEX rb_model_years_variant_uq
    ON rb_model_years (engine_generation_id, model_variant_id, model_year)
    WHERE model_variant_id IS NOT NULL;

-- Alias targets are split into FK-safe tables rather than entity_type/entity_id.
CREATE TABLE rb_model_aliases (
    model_alias_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_model_id BIGINT REFERENCES rb_engine_models(engine_model_id) ON DELETE CASCADE,
    engine_generation_id BIGINT REFERENCES rb_engine_generations(engine_generation_id) ON DELETE CASCADE,
    model_variant_id BIGINT REFERENCES rb_model_variants(model_variant_id) ON DELETE CASCADE,
    alias CITEXT NOT NULL,
    alias_type TEXT NOT NULL CHECK (alias_type IN ('search','market','legacy','spelling','redirect')),
    language_code VARCHAR(35) REFERENCES rb_languages(language_code) ON DELETE RESTRICT,
    market_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT rb_model_aliases_one_target CHECK (
        num_nonnulls(engine_model_id, engine_generation_id, model_variant_id) = 1
    )
);
CREATE UNIQUE INDEX rb_model_aliases_model_uq
    ON rb_model_aliases (engine_model_id, alias, COALESCE(language_code, ''), COALESCE(market_code, ''))
    WHERE engine_model_id IS NOT NULL;
CREATE UNIQUE INDEX rb_model_aliases_generation_uq
    ON rb_model_aliases (engine_generation_id, alias, COALESCE(language_code, ''), COALESCE(market_code, ''))
    WHERE engine_generation_id IS NOT NULL;
CREATE UNIQUE INDEX rb_model_aliases_variant_uq
    ON rb_model_aliases (model_variant_id, alias, COALESCE(language_code, ''), COALESCE(market_code, ''))
    WHERE model_variant_id IS NOT NULL;

CREATE TABLE rb_serial_schemes (
    serial_scheme_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    brand_id BIGINT NOT NULL REFERENCES rb_brands(brand_id) ON DELETE RESTRICT,
    scheme_key CITEXT NOT NULL,
    name TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    normalization_pattern TEXT,
    comparison_strategy TEXT NOT NULL
        CHECK (comparison_strategy IN ('lexical','numeric_suffix','parsed_segments','custom')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand_id, scheme_key, parser_version),
    UNIQUE (serial_scheme_id, brand_id)
);

CREATE TABLE rb_applicability_sets (
    applicability_set_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    applicability_key CITEXT NOT NULL UNIQUE,
    name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rb_applicability_rules (
    applicability_rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    applicability_set_id BIGINT NOT NULL REFERENCES rb_applicability_sets(applicability_set_id) ON DELETE CASCADE,
    is_exclusion BOOLEAN NOT NULL DEFAULT FALSE,
    is_global BOOLEAN NOT NULL DEFAULT FALSE,
    category_id BIGINT REFERENCES rb_product_categories(category_id) ON DELETE RESTRICT,
    brand_id BIGINT REFERENCES rb_brands(brand_id) ON DELETE RESTRICT,
    product_line_id BIGINT REFERENCES rb_product_lines(product_line_id) ON DELETE RESTRICT,
    engine_model_id BIGINT REFERENCES rb_engine_models(engine_model_id) ON DELETE RESTRICT,
    engine_generation_id BIGINT REFERENCES rb_engine_generations(engine_generation_id) ON DELETE RESTRICT,
    model_variant_id BIGINT REFERENCES rb_model_variants(model_variant_id) ON DELETE RESTRICT,
    model_year_start SMALLINT,
    model_year_end SMALLINT,
    production_date_start DATE,
    production_date_end DATE,
    market_code TEXT,
    serial_scheme_id BIGINT REFERENCES rb_serial_schemes(serial_scheme_id) ON DELETE RESTRICT,
    serial_prefix TEXT,
    serial_start_text TEXT,
    serial_end_text TEXT,
    serial_start_normalized TEXT,
    serial_end_normalized TEXT,
    range_start_inclusive BOOLEAN NOT NULL DEFAULT TRUE,
    range_end_inclusive BOOLEAN NOT NULL DEFAULT TRUE,
    notes_internal TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT rb_applicability_rules_one_target CHECK (
        num_nonnulls(category_id, brand_id, product_line_id, engine_model_id, engine_generation_id, model_variant_id)
        + CASE WHEN is_global THEN 1 ELSE 0 END = 1
    ),
    CONSTRAINT rb_applicability_rules_year_order CHECK (
        model_year_start IS NULL OR model_year_end IS NULL OR model_year_start <= model_year_end
    ),
    CONSTRAINT rb_applicability_rules_date_order CHECK (
        production_date_start IS NULL OR production_date_end IS NULL OR production_date_start <= production_date_end
    ),
    CONSTRAINT rb_applicability_rules_serial_scheme_required CHECK (
        (serial_prefix IS NULL AND serial_start_text IS NULL AND serial_end_text IS NULL
         AND serial_start_normalized IS NULL AND serial_end_normalized IS NULL)
        OR serial_scheme_id IS NOT NULL
    ),
    CONSTRAINT rb_applicability_rules_serial_bounds CHECK (
        (serial_start_text IS NULL) = (serial_start_normalized IS NULL)
        AND (serial_end_text IS NULL) = (serial_end_normalized IS NULL)
    )
);

CREATE INDEX rb_applicability_rules_set_idx ON rb_applicability_rules(applicability_set_id);
CREATE INDEX rb_applicability_rules_model_idx ON rb_applicability_rules(engine_model_id) WHERE engine_model_id IS NOT NULL;
CREATE INDEX rb_applicability_rules_generation_idx ON rb_applicability_rules(engine_generation_id) WHERE engine_generation_id IS NOT NULL;
CREATE INDEX rb_applicability_rules_variant_idx ON rb_applicability_rules(model_variant_id) WHERE model_variant_id IS NOT NULL;

-- Validate target ancestry and serial ownership, which ordinary CHECK constraints
-- cannot express across tables.
CREATE OR REPLACE FUNCTION rb_validate_applicability_rule()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    target_brand BIGINT;
BEGIN
    IF NEW.product_line_id IS NOT NULL THEN
        SELECT brand_id INTO target_brand FROM rb_product_lines WHERE product_line_id = NEW.product_line_id;
    ELSIF NEW.engine_model_id IS NOT NULL THEN
        SELECT brand_id INTO target_brand FROM rb_engine_models WHERE engine_model_id = NEW.engine_model_id;
    ELSIF NEW.engine_generation_id IS NOT NULL THEN
        SELECT m.brand_id INTO target_brand
        FROM rb_engine_generations g JOIN rb_engine_models m ON m.engine_model_id = g.engine_model_id
        WHERE g.engine_generation_id = NEW.engine_generation_id;
    ELSIF NEW.model_variant_id IS NOT NULL THEN
        SELECT m.brand_id INTO target_brand
        FROM rb_model_variants v
        JOIN rb_engine_generations g ON g.engine_generation_id = v.engine_generation_id
        JOIN rb_engine_models m ON m.engine_model_id = g.engine_model_id
        WHERE v.model_variant_id = NEW.model_variant_id;
    ELSIF NEW.brand_id IS NOT NULL THEN
        target_brand := NEW.brand_id;
    END IF;

    IF NEW.serial_scheme_id IS NOT NULL AND target_brand IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM rb_serial_schemes s
        WHERE s.serial_scheme_id = NEW.serial_scheme_id AND s.brand_id = target_brand
    ) THEN
        RAISE EXCEPTION 'serial scheme does not belong to applicability target brand';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER rb_applicability_rule_validate
BEFORE INSERT OR UPDATE ON rb_applicability_rules
FOR EACH ROW EXECUTE FUNCTION rb_validate_applicability_rule();

CREATE OR REPLACE FUNCTION rb_validate_applicability_set_structure()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    affected_set_id BIGINT;
BEGIN
    affected_set_id := CASE WHEN TG_OP = 'DELETE'
        THEN OLD.applicability_set_id ELSE NEW.applicability_set_id END;
    IF EXISTS (
        SELECT 1 FROM rb_applicability_rules r
        WHERE r.applicability_set_id = affected_set_id AND r.is_exclusion
    ) AND NOT EXISTS (
        SELECT 1 FROM rb_applicability_rules r
        WHERE r.applicability_set_id = affected_set_id AND NOT r.is_exclusion
    ) THEN
        RAISE EXCEPTION 'applicability set % has exclusions but no inclusion', affected_set_id;
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER rb_applicability_set_structure
AFTER INSERT OR UPDATE OR DELETE ON rb_applicability_rules
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION rb_validate_applicability_set_structure();

INSERT INTO rb_languages (language_code, canonical_name, native_name) VALUES
    ('en','English','English'), ('sv','Swedish','Svenska'),
    ('nl','Dutch','Nederlands'), ('fr','French','Français'),
    ('es','Spanish','Español'), ('it','Italian','Italiano')
ON CONFLICT (language_code) DO NOTHING;

INSERT INTO schema_migrations (version, filename)
VALUES ('011', '011_repairbase_catalog_applicability.sql')
ON CONFLICT (version) DO NOTHING;
