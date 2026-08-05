-- RepairBase phase 1c: localized presentation and site-scoped publication.
-- Public page subjects use real nullable foreign keys plus an exactly-one
-- constraint; no entity_type/entity_id registry is used.

CREATE TABLE rb_site_brands (
    site_id BIGINT NOT NULL REFERENCES rb_sites(site_id) ON DELETE CASCADE,
    brand_id BIGINT NOT NULL REFERENCES rb_brands(brand_id) ON DELETE RESTRICT,
    PRIMARY KEY (site_id, brand_id)
);

CREATE TABLE rb_product_line_translations (
    product_line_id BIGINT NOT NULL REFERENCES rb_product_lines(product_line_id) ON DELETE RESTRICT,
    language_code VARCHAR(35) NOT NULL REFERENCES rb_languages(language_code) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    short_description TEXT,
    body TEXT,
    translation_state TEXT NOT NULL DEFAULT 'missing' CHECK (translation_state IN (
        'missing','machine_draft','human_review_required','approved','outdated'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (product_line_id, language_code)
);

CREATE TABLE rb_engine_model_translations (
    engine_model_id BIGINT NOT NULL REFERENCES rb_engine_models(engine_model_id) ON DELETE RESTRICT,
    language_code VARCHAR(35) NOT NULL REFERENCES rb_languages(language_code) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    short_description TEXT,
    body TEXT,
    translation_state TEXT NOT NULL DEFAULT 'missing' CHECK (translation_state IN (
        'missing','machine_draft','human_review_required','approved','outdated'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (engine_model_id, language_code)
);

CREATE TABLE rb_engine_generation_translations (
    engine_generation_id BIGINT NOT NULL REFERENCES rb_engine_generations(engine_generation_id) ON DELETE RESTRICT,
    language_code VARCHAR(35) NOT NULL REFERENCES rb_languages(language_code) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    short_description TEXT,
    body TEXT,
    translation_state TEXT NOT NULL DEFAULT 'missing' CHECK (translation_state IN (
        'missing','machine_draft','human_review_required','approved','outdated'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (engine_generation_id, language_code)
);

CREATE TABLE rb_manual_translations (
    manual_id BIGINT NOT NULL REFERENCES rb_manuals(manual_id) ON DELETE RESTRICT,
    language_code VARCHAR(35) NOT NULL REFERENCES rb_languages(language_code) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    short_description TEXT,
    body TEXT,
    translation_state TEXT NOT NULL DEFAULT 'missing' CHECK (translation_state IN (
        'missing','machine_draft','human_review_required','approved','outdated'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (manual_id, language_code)
);

CREATE TABLE rb_hreflang_clusters (
    hreflang_cluster_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_key CITEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rb_pages (
    page_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id BIGINT NOT NULL REFERENCES rb_sites(site_id) ON DELETE RESTRICT,
    language_code VARCHAR(35) NOT NULL REFERENCES rb_languages(language_code) ON DELETE RESTRICT,
    page_type TEXT NOT NULL CHECK (page_type IN (
        'home','category','brand','product_line','engine_model','engine_generation',
        'model_variant','model_year','manual','specifications'
    )),
    category_id BIGINT REFERENCES rb_product_categories(category_id) ON DELETE RESTRICT,
    brand_id BIGINT REFERENCES rb_brands(brand_id) ON DELETE RESTRICT,
    product_line_id BIGINT REFERENCES rb_product_lines(product_line_id) ON DELETE RESTRICT,
    engine_model_id BIGINT REFERENCES rb_engine_models(engine_model_id) ON DELETE RESTRICT,
    engine_generation_id BIGINT REFERENCES rb_engine_generations(engine_generation_id) ON DELETE RESTRICT,
    model_variant_id BIGINT REFERENCES rb_model_variants(model_variant_id) ON DELETE RESTRICT,
    model_year_id BIGINT REFERENCES rb_model_years(model_year_id) ON DELETE RESTRICT,
    manual_id BIGINT REFERENCES rb_manuals(manual_id) ON DELETE RESTRICT,
    route_scope_key CITEXT NOT NULL,
    slug CITEXT NOT NULL,
    canonical_path CITEXT NOT NULL,
    canonical_page_id BIGINT REFERENCES rb_pages(page_id) ON DELETE RESTRICT,
    hreflang_cluster_id BIGINT REFERENCES rb_hreflang_clusters(hreflang_cluster_id) ON DELETE RESTRICT,
    publication_state TEXT NOT NULL DEFAULT 'draft' CHECK (publication_state IN (
        'draft','review','published','withdrawn','archived'
    )),
    index_state TEXT NOT NULL DEFAULT 'not_eligible' CHECK (index_state IN (
        'index','noindex','blocked','not_eligible'
    )),
    noindex_reason TEXT CHECK (noindex_reason IN (
        'thin_translation','insufficient_evidence','duplicate_intent','low_distinctness',
        'stale_source','rights_restriction','unresolved_conflict','no_search_demand',
        'incomplete_applicability','editorial_hold'
    )),
    quality_score NUMERIC(5,4) CHECK (quality_score BETWEEN 0 AND 1),
    distinctness_score NUMERIC(5,4) CHECK (distinctness_score BETWEEN 0 AND 1),
    demand_score NUMERIC(5,4) CHECK (demand_score BETWEEN 0 AND 1),
    sitemap_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    first_published_at TIMESTAMPTZ,
    last_published_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    CONSTRAINT rb_pages_one_subject CHECK (
        (page_type = 'home' AND num_nonnulls(
            category_id, brand_id, product_line_id, engine_model_id,
            engine_generation_id, model_variant_id, model_year_id, manual_id
        ) = 0)
        OR
        (page_type <> 'home' AND num_nonnulls(
            category_id, brand_id, product_line_id, engine_model_id,
            engine_generation_id, model_variant_id, model_year_id, manual_id
        ) = 1)
    ),
    CONSTRAINT rb_pages_type_matches_subject CHECK (
        (page_type = 'home')
        OR (page_type = 'category' AND category_id IS NOT NULL)
        OR (page_type = 'brand' AND brand_id IS NOT NULL)
        OR (page_type = 'product_line' AND product_line_id IS NOT NULL)
        OR (page_type IN ('engine_model','specifications') AND engine_model_id IS NOT NULL)
        OR (page_type = 'engine_generation' AND engine_generation_id IS NOT NULL)
        OR (page_type = 'model_variant' AND model_variant_id IS NOT NULL)
        OR (page_type = 'model_year' AND model_year_id IS NOT NULL)
        OR (page_type = 'manual' AND manual_id IS NOT NULL)
    ),
    CONSTRAINT rb_pages_path_absolute CHECK (canonical_path::TEXT ~ '^/[^?]*$'),
    CONSTRAINT rb_pages_index_reason CHECK (
        (index_state = 'noindex' AND noindex_reason IS NOT NULL)
        OR (index_state <> 'noindex' AND noindex_reason IS NULL)
    ),
    CONSTRAINT rb_pages_sitemap_gate CHECK (
        NOT sitemap_eligible OR (publication_state = 'published' AND index_state = 'index')
    ),
    CONSTRAINT rb_pages_not_self_canonical CHECK (
        canonical_page_id IS NULL OR canonical_page_id <> page_id
    )
);

CREATE UNIQUE INDEX rb_pages_canonical_path_uq
    ON rb_pages (site_id, language_code, canonical_path)
    WHERE archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_active_slug_uq
    ON rb_pages (site_id, language_code, route_scope_key, slug)
    WHERE archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_home_uq
    ON rb_pages (site_id, language_code)
    WHERE page_type = 'home' AND archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_category_subject_uq
    ON rb_pages (site_id, language_code, page_type, category_id)
    WHERE category_id IS NOT NULL AND archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_brand_subject_uq
    ON rb_pages (site_id, language_code, page_type, brand_id)
    WHERE brand_id IS NOT NULL AND archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_line_subject_uq
    ON rb_pages (site_id, language_code, page_type, product_line_id)
    WHERE product_line_id IS NOT NULL AND archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_model_subject_uq
    ON rb_pages (site_id, language_code, page_type, engine_model_id)
    WHERE engine_model_id IS NOT NULL AND archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_generation_subject_uq
    ON rb_pages (site_id, language_code, page_type, engine_generation_id)
    WHERE engine_generation_id IS NOT NULL AND archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_variant_subject_uq
    ON rb_pages (site_id, language_code, page_type, model_variant_id)
    WHERE model_variant_id IS NOT NULL AND archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_year_subject_uq
    ON rb_pages (site_id, language_code, page_type, model_year_id)
    WHERE model_year_id IS NOT NULL AND archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_manual_subject_uq
    ON rb_pages (site_id, language_code, page_type, manual_id)
    WHERE manual_id IS NOT NULL AND archived_at IS NULL;
CREATE UNIQUE INDEX rb_pages_hreflang_language_uq
    ON rb_pages (hreflang_cluster_id, language_code)
    WHERE hreflang_cluster_id IS NOT NULL AND archived_at IS NULL;

CREATE TABLE rb_page_revisions (
    page_revision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    page_id BIGINT NOT NULL REFERENCES rb_pages(page_id) ON DELETE RESTRICT,
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    content_hash TEXT NOT NULL,
    render_context_hash TEXT,
    publication_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT NOT NULL,
    UNIQUE (page_id, revision_number),
    UNIQUE (page_revision_id, page_id)
);

CREATE OR REPLACE FUNCTION rb_reject_page_revision_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'page revisions are immutable; create a new revision';
END $$;

CREATE TRIGGER rb_page_revisions_immutable
BEFORE UPDATE OR DELETE ON rb_page_revisions
FOR EACH ROW EXECUTE FUNCTION rb_reject_page_revision_mutation();

ALTER TABLE rb_pages
    ADD COLUMN published_revision_id BIGINT,
    ADD CONSTRAINT rb_pages_published_revision_fk
        FOREIGN KEY (published_revision_id, page_id)
        REFERENCES rb_page_revisions(page_revision_id, page_id) ON DELETE RESTRICT;

CREATE TABLE rb_redirects (
    redirect_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id BIGINT NOT NULL REFERENCES rb_sites(site_id) ON DELETE RESTRICT,
    language_code VARCHAR(35) NOT NULL REFERENCES rb_languages(language_code) ON DELETE RESTRICT,
    from_path CITEXT NOT NULL,
    to_page_id BIGINT NOT NULL REFERENCES rb_pages(page_id) ON DELETE RESTRICT,
    http_status SMALLINT NOT NULL CHECK (http_status IN (301,302,307,308)),
    valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT rb_redirects_valid_order CHECK (valid_to IS NULL OR valid_from <= valid_to),
    CONSTRAINT rb_redirects_path_absolute CHECK (from_path::TEXT ~ '^/[^?]*$'),
    UNIQUE (site_id, language_code, from_path, valid_from)
);
CREATE UNIQUE INDEX rb_redirects_active_path_uq
    ON rb_redirects(site_id, language_code, from_path) WHERE valid_to IS NULL;

CREATE OR REPLACE FUNCTION rb_validate_redirect_target()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM rb_pages p
        WHERE p.page_id = NEW.to_page_id
          AND p.site_id = NEW.site_id
          AND p.language_code = NEW.language_code
    ) THEN
        RAISE EXCEPTION 'redirect target must belong to the same site and language';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER rb_redirects_validate_target
BEFORE INSERT OR UPDATE ON rb_redirects
FOR EACH ROW EXECUTE FUNCTION rb_validate_redirect_target();

CREATE TABLE rb_audit_events (
    audit_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('user','pipeline','system')),
    actor_id TEXT,
    object_table TEXT NOT NULL,
    object_pk TEXT NOT NULL,
    action TEXT NOT NULL,
    before_json JSONB,
    after_json JSONB,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION rb_record_audit_event()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    configured_actor_type TEXT := NULLIF(current_setting('repairbase.actor_type', true), '');
    configured_actor_id TEXT := NULLIF(current_setting('repairbase.actor_id', true), '');
    configured_reason TEXT := NULLIF(current_setting('repairbase.change_reason', true), '');
    row_id TEXT;
BEGIN
    IF configured_actor_type IS NOT NULL
       AND configured_actor_type NOT IN ('user','pipeline','system') THEN
        RAISE EXCEPTION 'invalid repairbase.actor_type';
    END IF;
    IF TG_TABLE_NAME = 'rb_technical_assertions' THEN
        row_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.assertion_id ELSE NEW.assertion_id END::TEXT;
    ELSIF TG_TABLE_NAME = 'rb_pages' THEN
        row_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.page_id ELSE NEW.page_id END::TEXT;
    END IF;
    INSERT INTO rb_audit_events (
        actor_type, actor_id, object_table, object_pk, action,
        before_json, after_json, reason
    ) VALUES (
        COALESCE(configured_actor_type, 'system'), configured_actor_id,
        TG_TABLE_NAME, row_id, lower(TG_OP),
        CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END,
        CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END,
        configured_reason
    );
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER rb_technical_assertions_audit
AFTER INSERT OR UPDATE OR DELETE ON rb_technical_assertions
FOR EACH ROW EXECUTE FUNCTION rb_record_audit_event();
CREATE TRIGGER rb_pages_audit
AFTER INSERT OR UPDATE OR DELETE ON rb_pages
FOR EACH ROW EXECUTE FUNCTION rb_record_audit_event();

CREATE OR REPLACE FUNCTION rb_validate_site_language_and_subject()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    subject_category BIGINT;
    subject_brand BIGINT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM rb_site_languages sl
        WHERE sl.site_id = NEW.site_id AND sl.language_code = NEW.language_code AND sl.is_enabled
    ) THEN
        RAISE EXCEPTION 'page language is not enabled for site';
    END IF;

    IF NEW.hreflang_cluster_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM rb_pages p
        WHERE p.hreflang_cluster_id = NEW.hreflang_cluster_id
          AND p.page_id <> COALESCE(NEW.page_id, -1)
          AND (
              p.site_id <> NEW.site_id
              OR p.page_type <> NEW.page_type
              OR p.category_id IS DISTINCT FROM NEW.category_id
              OR p.brand_id IS DISTINCT FROM NEW.brand_id
              OR p.product_line_id IS DISTINCT FROM NEW.product_line_id
              OR p.engine_model_id IS DISTINCT FROM NEW.engine_model_id
              OR p.engine_generation_id IS DISTINCT FROM NEW.engine_generation_id
              OR p.model_variant_id IS DISTINCT FROM NEW.model_variant_id
              OR p.model_year_id IS DISTINCT FROM NEW.model_year_id
              OR p.manual_id IS DISTINCT FROM NEW.manual_id
          )
    ) THEN
        RAISE EXCEPTION 'hreflang cluster cannot cross sites or content identities';
    END IF;

    IF NEW.brand_id IS NOT NULL THEN subject_brand := NEW.brand_id;
    ELSIF NEW.product_line_id IS NOT NULL THEN
        SELECT brand_id INTO subject_brand FROM rb_product_lines WHERE product_line_id = NEW.product_line_id;
    ELSIF NEW.engine_model_id IS NOT NULL THEN
        SELECT brand_id INTO subject_brand FROM rb_engine_models WHERE engine_model_id = NEW.engine_model_id;
    ELSIF NEW.engine_generation_id IS NOT NULL THEN
        SELECT m.brand_id INTO subject_brand FROM rb_engine_generations g
        JOIN rb_engine_models m ON m.engine_model_id = g.engine_model_id
        WHERE g.engine_generation_id = NEW.engine_generation_id;
    ELSIF NEW.model_variant_id IS NOT NULL THEN
        SELECT m.brand_id INTO subject_brand FROM rb_model_variants v
        JOIN rb_engine_generations g ON g.engine_generation_id = v.engine_generation_id
        JOIN rb_engine_models m ON m.engine_model_id = g.engine_model_id
        WHERE v.model_variant_id = NEW.model_variant_id;
    ELSIF NEW.model_year_id IS NOT NULL THEN
        SELECT m.brand_id INTO subject_brand FROM rb_model_years y
        JOIN rb_engine_generations g ON g.engine_generation_id = y.engine_generation_id
        JOIN rb_engine_models m ON m.engine_model_id = g.engine_model_id
        WHERE y.model_year_id = NEW.model_year_id;
    END IF;

    IF NEW.category_id IS NOT NULL THEN subject_category := NEW.category_id;
    ELSIF NEW.product_line_id IS NOT NULL THEN
        SELECT category_id INTO subject_category FROM rb_product_lines WHERE product_line_id = NEW.product_line_id;
    ELSIF NEW.engine_model_id IS NOT NULL THEN
        SELECT category_id INTO subject_category FROM rb_engine_models WHERE engine_model_id = NEW.engine_model_id;
    ELSIF NEW.engine_generation_id IS NOT NULL THEN
        SELECT m.category_id INTO subject_category FROM rb_engine_generations g
        JOIN rb_engine_models m ON m.engine_model_id = g.engine_model_id
        WHERE g.engine_generation_id = NEW.engine_generation_id;
    ELSIF NEW.model_variant_id IS NOT NULL THEN
        SELECT m.category_id INTO subject_category FROM rb_model_variants v
        JOIN rb_engine_generations g ON g.engine_generation_id = v.engine_generation_id
        JOIN rb_engine_models m ON m.engine_model_id = g.engine_model_id
        WHERE v.model_variant_id = NEW.model_variant_id;
    ELSIF NEW.model_year_id IS NOT NULL THEN
        SELECT m.category_id INTO subject_category FROM rb_model_years y
        JOIN rb_engine_generations g ON g.engine_generation_id = y.engine_generation_id
        JOIN rb_engine_models m ON m.engine_model_id = g.engine_model_id
        WHERE y.model_year_id = NEW.model_year_id;
    END IF;

    IF subject_category IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM rb_site_categories sc
        WHERE sc.site_id = NEW.site_id AND sc.category_id = subject_category
    ) THEN
        RAISE EXCEPTION 'page subject category is not enabled for site';
    END IF;
    IF subject_brand IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM rb_site_brands sb
        WHERE sb.site_id = NEW.site_id AND sb.brand_id = subject_brand
    ) THEN
        RAISE EXCEPTION 'page subject brand is not enabled for site';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER rb_pages_validate_site_scope
BEFORE INSERT OR UPDATE OF site_id, language_code, category_id, product_line_id,
    brand_id, engine_model_id, engine_generation_id, model_variant_id,
    model_year_id, manual_id, page_type, hreflang_cluster_id
ON rb_pages FOR EACH ROW EXECUTE FUNCTION rb_validate_site_language_and_subject();

CREATE OR REPLACE FUNCTION rb_validate_published_page()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.publication_state = 'published' AND NEW.published_revision_id IS NULL THEN
        RAISE EXCEPTION 'published page must reference a page revision';
    END IF;
    IF NEW.index_state = 'index' AND NEW.publication_state <> 'published' THEN
        RAISE EXCEPTION 'only published pages may be indexed';
    END IF;
    RETURN NEW;
END $$;

CREATE CONSTRAINT TRIGGER rb_pages_publication_gate
AFTER INSERT OR UPDATE OF publication_state, index_state, published_revision_id ON rb_pages
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION rb_validate_published_page();

INSERT INTO schema_migrations (version, filename)
VALUES ('013', '013_repairbase_localization_publication.sql')
ON CONFLICT (version) DO NOTHING;
