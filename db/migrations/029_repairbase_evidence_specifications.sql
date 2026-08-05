-- RepairBase phase 1b: sources, reviewable assertions, units, specifications,
-- manuals, and FK-safe ownership/applicability junctions.

CREATE TABLE rb_units (
    unit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    unit_key CITEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    quantity_type TEXT NOT NULL,
    unit_system TEXT NOT NULL CHECK (unit_system IN ('SI','US_CUSTOMARY','IMPERIAL','OEM')),
    si_factor NUMERIC,
    si_offset NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rb_operating_conditions (
    operating_condition_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    condition_key CITEXT NOT NULL UNIQUE,
    condition_type TEXT,
    canonical_description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rb_sources (
    source_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_type TEXT NOT NULL CHECK (source_type IN (
        'owner_manual','service_manual','parts_catalog','rigging_manual',
        'service_bulletin','manufacturer_webpage','dealer_document',
        'regulatory_document','other'
    )),
    title TEXT NOT NULL,
    publisher TEXT,
    document_number CITEXT,
    publication_date DATE,
    source_url TEXT,
    language_code VARCHAR(35) REFERENCES rb_languages(language_code) ON DELETE RESTRICT,
    rights_holder TEXT,
    hosting_permitted BOOLEAN,
    license_notes TEXT,
    source_authority NUMERIC(4,3) CHECK (source_authority BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX rb_sources_document_uq
    ON rb_sources (publisher, document_number)
    WHERE document_number IS NOT NULL;

CREATE TABLE rb_source_revisions (
    source_revision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES rb_sources(source_id) ON DELETE RESTRICT,
    revision_label TEXT,
    content_hash TEXT NOT NULL,
    valid_from DATE,
    valid_to DATE,
    retrieved_at TIMESTAMPTZ NOT NULL,
    supersedes_source_revision_id BIGINT REFERENCES rb_source_revisions(source_revision_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT rb_source_revisions_valid_order CHECK (
        valid_from IS NULL OR valid_to IS NULL OR valid_from <= valid_to
    ),
    UNIQUE (source_id, content_hash),
    CONSTRAINT rb_source_revisions_no_self_supersession CHECK (
        supersedes_source_revision_id IS NULL OR supersedes_source_revision_id <> source_revision_id
    )
);

CREATE OR REPLACE FUNCTION rb_reject_source_revision_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'source revisions are immutable; create a superseding revision';
END $$;

CREATE TRIGGER rb_source_revisions_immutable
BEFORE UPDATE OR DELETE ON rb_source_revisions
FOR EACH ROW EXECUTE FUNCTION rb_reject_source_revision_mutation();

CREATE TABLE rb_technical_assertions (
    assertion_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assertion_key CITEXT NOT NULL UNIQUE,
    predicate_key CITEXT NOT NULL,
    value_type TEXT NOT NULL CHECK (value_type IN ('number','text','boolean','enum','range','reference')),
    value_text TEXT,
    value_number NUMERIC,
    value_boolean BOOLEAN,
    value_reference_key TEXT,
    source_value_text TEXT,
    source_unit_id BIGINT REFERENCES rb_units(unit_id) ON DELETE RESTRICT,
    normalized_value_number NUMERIC,
    normalized_unit_id BIGINT REFERENCES rb_units(unit_id) ON DELETE RESTRICT,
    minimum_value NUMERIC,
    maximum_value NUMERIC,
    tolerance_minus NUMERIC CHECK (tolerance_minus >= 0),
    tolerance_plus NUMERIC CHECK (tolerance_plus >= 0),
    operating_condition_id BIGINT REFERENCES rb_operating_conditions(operating_condition_id) ON DELETE RESTRICT,
    applicability_set_id BIGINT NOT NULL REFERENCES rb_applicability_sets(applicability_set_id) ON DELETE RESTRICT,
    ingestion_state TEXT NOT NULL DEFAULT 'discovered' CHECK (ingestion_state IN (
        'discovered','fetched','extracted','normalized','enriched','failed'
    )),
    review_state TEXT NOT NULL DEFAULT 'unreviewed' CHECK (review_state IN (
        'unreviewed','automated_checks_passed','needs_review','technically_reviewed','rejected'
    )),
    publication_state TEXT NOT NULL DEFAULT 'draft' CHECK (publication_state IN (
        'draft','review','published','withdrawn','archived'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT rb_assertions_range_order CHECK (
        minimum_value IS NULL OR maximum_value IS NULL OR minimum_value <= maximum_value
    ),
    CONSTRAINT rb_assertions_typed_value CHECK (
        (value_type = 'number' AND value_number IS NOT NULL)
        OR (value_type IN ('text','enum') AND value_text IS NOT NULL)
        OR (value_type = 'boolean' AND value_boolean IS NOT NULL)
        OR (value_type = 'reference' AND value_reference_key IS NOT NULL)
        OR (value_type = 'range' AND minimum_value IS NOT NULL AND maximum_value IS NOT NULL)
    )
);

CREATE TABLE rb_evidence_links (
    evidence_link_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assertion_id BIGINT NOT NULL REFERENCES rb_technical_assertions(assertion_id) ON DELETE RESTRICT,
    source_revision_id BIGINT NOT NULL REFERENCES rb_source_revisions(source_revision_id) ON DELETE RESTRICT,
    source_locator TEXT NOT NULL,
    support_type TEXT NOT NULL CHECK (support_type IN ('direct','derived','contradicts','supersedes','context_only')),
    short_internal_excerpt TEXT,
    extraction_confidence NUMERIC(4,3) CHECK (extraction_confidence BETWEEN 0 AND 1),
    reviewed_by TEXT,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (assertion_id, source_revision_id, source_locator)
);

-- Assertions have strict FK ownership. Additional domains add their own
-- junction rather than writing an entity_type/entity_id pair.
CREATE TABLE rb_engine_generation_assertions (
    engine_generation_id BIGINT NOT NULL REFERENCES rb_engine_generations(engine_generation_id) ON DELETE RESTRICT,
    assertion_id BIGINT NOT NULL REFERENCES rb_technical_assertions(assertion_id) ON DELETE RESTRICT,
    PRIMARY KEY (engine_generation_id, assertion_id)
);
CREATE TABLE rb_model_variant_assertions (
    model_variant_id BIGINT NOT NULL REFERENCES rb_model_variants(model_variant_id) ON DELETE RESTRICT,
    assertion_id BIGINT NOT NULL REFERENCES rb_technical_assertions(assertion_id) ON DELETE RESTRICT,
    PRIMARY KEY (model_variant_id, assertion_id)
);

CREATE TABLE rb_specification_definitions (
    specification_definition_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    specification_key CITEXT NOT NULL UNIQUE,
    quantity_type TEXT,
    value_type TEXT NOT NULL CHECK (value_type IN ('number','text','boolean','enum','range','reference')),
    canonical_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rb_specification_values (
    specification_value_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    specification_definition_id BIGINT NOT NULL REFERENCES rb_specification_definitions(specification_definition_id) ON DELETE RESTRICT,
    assertion_id BIGINT NOT NULL UNIQUE REFERENCES rb_technical_assertions(assertion_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rb_manuals (
    manual_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manual_key CITEXT NOT NULL UNIQUE,
    manual_type TEXT NOT NULL CHECK (manual_type IN (
        'owner','service','parts','rigging','installation','wiring','maintenance','other'
    )),
    title TEXT NOT NULL,
    document_number CITEXT,
    revision TEXT,
    publication_date DATE,
    external_url TEXT,
    hosted_file_url TEXT,
    rights_holder TEXT,
    hosting_permitted BOOLEAN,
    source_id BIGINT REFERENCES rb_sources(source_id) ON DELETE RESTRICT,
    publication_state TEXT NOT NULL DEFAULT 'draft' CHECK (publication_state IN (
        'draft','review','published','withdrawn','archived'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    CONSTRAINT rb_manuals_hosting_rights CHECK (
        hosted_file_url IS NULL OR hosting_permitted IS TRUE
    )
);

CREATE TABLE rb_manual_applicability (
    manual_id BIGINT NOT NULL REFERENCES rb_manuals(manual_id) ON DELETE RESTRICT,
    applicability_set_id BIGINT NOT NULL REFERENCES rb_applicability_sets(applicability_set_id) ON DELETE RESTRICT,
    PRIMARY KEY (manual_id, applicability_set_id)
);

CREATE OR REPLACE FUNCTION rb_protect_published_assertion()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND OLD.publication_state = 'published' THEN
        RAISE EXCEPTION 'published assertions must be withdrawn and retained';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.publication_state = 'published' THEN
        IF NEW.publication_state NOT IN ('withdrawn','archived') THEN
            RAISE EXCEPTION 'published assertions must be withdrawn before replacement';
        END IF;
        IF (to_jsonb(NEW) - ARRAY['publication_state','updated_at'])
           IS DISTINCT FROM
           (to_jsonb(OLD) - ARRAY['publication_state','updated_at']) THEN
            RAISE EXCEPTION 'technical values on a published assertion are immutable';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER rb_technical_assertions_protect_published
BEFORE UPDATE OR DELETE ON rb_technical_assertions
FOR EACH ROW EXECUTE FUNCTION rb_protect_published_assertion();

CREATE OR REPLACE FUNCTION rb_protect_published_evidence()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    target_assertion_id BIGINT := COALESCE(NEW.assertion_id, OLD.assertion_id);
BEGIN
    IF EXISTS (
        SELECT 1 FROM rb_technical_assertions a
        WHERE a.assertion_id = target_assertion_id
          AND a.publication_state = 'published'
    ) THEN
        RAISE EXCEPTION 'evidence for a published assertion is immutable; withdraw the assertion first';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER rb_evidence_links_protect_published
BEFORE INSERT OR UPDATE OR DELETE ON rb_evidence_links
FOR EACH ROW EXECUTE FUNCTION rb_protect_published_evidence();

-- Public publication is rejected unless an assertion has supporting evidence.
CREATE OR REPLACE FUNCTION rb_validate_assertion_publication()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.publication_state = 'published' AND (
        NEW.review_state <> 'technically_reviewed'
        OR NOT EXISTS (
            SELECT 1 FROM rb_evidence_links e
            WHERE e.assertion_id = NEW.assertion_id
              AND e.support_type IN ('direct','derived')
        )
        OR EXISTS (
            SELECT 1 FROM rb_evidence_links e
            WHERE e.assertion_id = NEW.assertion_id
              AND e.support_type = 'contradicts'
        )
    ) THEN
        RAISE EXCEPTION 'assertion % does not pass the publication gate', NEW.assertion_key;
    END IF;
    RETURN NEW;
END $$;

CREATE CONSTRAINT TRIGGER rb_assertion_publication_gate
AFTER INSERT OR UPDATE ON rb_technical_assertions
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION rb_validate_assertion_publication();

INSERT INTO rb_units (unit_key, symbol, quantity_type, unit_system, si_factor, si_offset) VALUES
    ('millilitre','mL','volume','SI',0.000001,0),
    ('litre','L','volume','SI',0.001,0),
    ('cubic-centimetre','cm³','volume','SI',0.000001,0),
    ('kilogram','kg','mass','SI',1,0),
    ('newton-metre','N·m','torque','SI',1,0),
    ('revolution-per-minute','rpm','rotational_speed','OEM',1,0)
ON CONFLICT (unit_key) DO NOTHING;

INSERT INTO schema_migrations (version, filename)
VALUES ('012', '012_repairbase_evidence_specifications.sql')
ON CONFLICT (version) DO NOTHING;
