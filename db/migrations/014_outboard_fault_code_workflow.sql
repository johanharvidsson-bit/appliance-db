-- Outboard fault-code editorial gate and resumable worker queue.

CREATE TABLE rb_fault_codes (
    fault_code_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fault_code_key CITEXT NOT NULL UNIQUE,
    brand_id BIGINT NOT NULL REFERENCES rb_brands(brand_id) ON DELETE RESTRICT,
    applicability_set_id BIGINT NOT NULL REFERENCES rb_applicability_sets(applicability_set_id) ON DELETE RESTRICT,
    display_code CITEXT NOT NULL,
    normalized_code CITEXT NOT NULL,
    title TEXT,
    description TEXT,
    editorial_review_state TEXT NOT NULL DEFAULT 'unreviewed' CHECK (editorial_review_state IN (
        'unreviewed','needs_review','approved','rejected'
    )),
    readiness_state TEXT NOT NULL DEFAULT 'incomplete' CHECK (readiness_state IN (
        'incomplete','ready','blocked'
    )),
    publication_blockers TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    publication_state TEXT NOT NULL DEFAULT 'draft' CHECK (publication_state IN (
        'draft','review','published','withdrawn','archived'
    )),
    last_assessed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    CONSTRAINT rb_fault_codes_title_length CHECK (title IS NULL OR char_length(btrim(title)) >= 3),
    CONSTRAINT rb_fault_codes_description_length CHECK (description IS NULL OR char_length(btrim(description)) >= 20)
);

CREATE INDEX rb_fault_codes_brand_code_idx ON rb_fault_codes(brand_id, normalized_code);
CREATE INDEX rb_fault_codes_work_queue_idx ON rb_fault_codes(readiness_state, publication_state)
    WHERE archived_at IS NULL;

CREATE TABLE rb_fault_code_sources (
    fault_code_source_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fault_code_id BIGINT NOT NULL REFERENCES rb_fault_codes(fault_code_id) ON DELETE RESTRICT,
    source_revision_id BIGINT NOT NULL REFERENCES rb_source_revisions(source_revision_id) ON DELETE RESTRICT,
    source_locator TEXT NOT NULL,
    support_type TEXT NOT NULL CHECK (support_type IN ('direct','derived','contradicts','context_only')),
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fault_code_id, source_revision_id, source_locator)
);

CREATE OR REPLACE FUNCTION rb_fault_code_publication_blockers(target_fault_code_id BIGINT)
RETURNS TEXT[] LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT ARRAY_REMOVE(ARRAY[
        CASE WHEN NULLIF(btrim(fc.title), '') IS NULL THEN 'missing_title' END,
        CASE WHEN char_length(COALESCE(btrim(fc.description), '')) < 80 THEN 'missing_description' END,
        CASE WHEN fc.editorial_review_state <> 'approved' THEN 'editorial_approval_required' END,
        CASE WHEN NOT EXISTS (
            SELECT 1 FROM rb_fault_code_sources fcs
            WHERE fcs.fault_code_id = fc.fault_code_id
              AND fcs.support_type IN ('direct','derived')
              AND fcs.verified_at IS NOT NULL
        ) THEN 'verified_source_required' END,
        CASE WHEN EXISTS (
            SELECT 1 FROM rb_fault_code_sources fcs
            WHERE fcs.fault_code_id = fc.fault_code_id
              AND fcs.support_type = 'contradicts'
        ) THEN 'unresolved_source_conflict' END,
        CASE WHEN NOT EXISTS (
            SELECT 1 FROM rb_applicability_rules ar
            WHERE ar.applicability_set_id = fc.applicability_set_id
              AND ar.is_exclusion = FALSE
        ) THEN 'applicability_required' END
    ], NULL)
    FROM rb_fault_codes fc
    WHERE fc.fault_code_id = target_fault_code_id
$$;

CREATE OR REPLACE FUNCTION rb_assess_fault_code_readiness(target_fault_code_id BIGINT)
RETURNS TEXT[] LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    blockers TEXT[];
BEGIN
    SELECT rb_fault_code_publication_blockers(target_fault_code_id) INTO blockers;
    IF blockers IS NULL THEN
        RAISE EXCEPTION 'fault code % does not exist', target_fault_code_id;
    END IF;

    UPDATE rb_fault_codes
    SET publication_blockers = blockers,
        readiness_state = CASE
            WHEN cardinality(blockers) = 0 THEN 'ready'
            WHEN 'unresolved_source_conflict' = ANY(blockers) OR editorial_review_state = 'rejected' THEN 'blocked'
            ELSE 'incomplete'
        END,
        last_assessed_at = now(),
        updated_at = now()
    WHERE fault_code_id = target_fault_code_id;
    RETURN blockers;
END $$;

CREATE OR REPLACE FUNCTION rb_validate_fault_code_publication()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    blockers TEXT[];
BEGIN
    IF NEW.publication_state = 'published' THEN
        IF TG_OP = 'INSERT' THEN
            RAISE EXCEPTION 'fault codes must be assessed and approved before publication';
        END IF;
        SELECT rb_fault_code_publication_blockers(NEW.fault_code_id) INTO blockers;
        IF cardinality(blockers) > 0 THEN
            RAISE EXCEPTION 'fault code % does not pass publication gate: %', NEW.fault_code_key, blockers;
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER rb_fault_codes_publication_gate
BEFORE INSERT OR UPDATE OF publication_state ON rb_fault_codes
FOR EACH ROW EXECUTE FUNCTION rb_validate_fault_code_publication();

CREATE OR REPLACE VIEW rb_public_fault_codes AS
SELECT fc.fault_code_id, fc.fault_code_key, fc.brand_id, fc.applicability_set_id,
       fc.display_code, fc.normalized_code, fc.title, fc.description, fc.updated_at
FROM rb_fault_codes fc
WHERE fc.publication_state = 'published'
  AND fc.archived_at IS NULL
  AND cardinality(rb_fault_code_publication_blockers(fc.fault_code_id)) = 0;

CREATE TABLE rb_worker_jobs (
    worker_job_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_type TEXT NOT NULL CHECK (job_type IN ('assess_fault_code_readiness')),
    entity_type TEXT NOT NULL CHECK (entity_type IN ('fault_code')),
    entity_id BIGINT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','leased','retry','succeeded','dead'
    )),
    priority SMALLINT NOT NULL DEFAULT 100,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 5 CHECK (max_attempts > 0),
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_owner TEXT,
    leased_until TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT rb_worker_jobs_lease_shape CHECK (
        (status = 'leased' AND lease_owner IS NOT NULL AND leased_until IS NOT NULL)
        OR (status <> 'leased' AND lease_owner IS NULL AND leased_until IS NULL)
    )
);

CREATE INDEX rb_worker_jobs_claim_idx
    ON rb_worker_jobs(status, available_at, priority, worker_job_id)
    WHERE status IN ('pending','retry','leased');

CREATE OR REPLACE FUNCTION rb_enqueue_fault_code_assessment(target_fault_code_id BIGINT)
RETURNS BIGINT LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    result_id BIGINT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM rb_fault_codes WHERE fault_code_id = target_fault_code_id) THEN
        RAISE EXCEPTION 'fault code % does not exist', target_fault_code_id;
    END IF;
    INSERT INTO rb_worker_jobs(job_type, entity_type, entity_id, idempotency_key)
    VALUES ('assess_fault_code_readiness', 'fault_code', target_fault_code_id,
            'assess_fault_code_readiness:' || target_fault_code_id)
    ON CONFLICT (idempotency_key) DO UPDATE SET
        status = CASE WHEN rb_worker_jobs.status = 'leased' THEN rb_worker_jobs.status ELSE 'pending' END,
        available_at = CASE WHEN rb_worker_jobs.status = 'leased' THEN rb_worker_jobs.available_at ELSE now() END,
        completed_at = NULL,
        updated_at = now()
    RETURNING worker_job_id INTO result_id;
    RETURN result_id;
END $$;

CREATE OR REPLACE FUNCTION rb_queue_fault_code_assessment()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM rb_enqueue_fault_code_assessment(NEW.fault_code_id);
    RETURN NEW;
END $$;

CREATE TRIGGER rb_fault_codes_queue_assessment
AFTER INSERT OR UPDATE OF title, description, editorial_review_state, applicability_set_id ON rb_fault_codes
FOR EACH ROW EXECUTE FUNCTION rb_queue_fault_code_assessment();

CREATE OR REPLACE FUNCTION rb_queue_fault_code_source_assessment()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM rb_enqueue_fault_code_assessment(CASE WHEN TG_OP = 'DELETE' THEN OLD.fault_code_id ELSE NEW.fault_code_id END);
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER rb_fault_code_sources_queue_assessment
AFTER INSERT OR UPDATE OR DELETE ON rb_fault_code_sources
FOR EACH ROW EXECUTE FUNCTION rb_queue_fault_code_source_assessment();

CREATE OR REPLACE FUNCTION rb_queue_applicability_fault_code_assessments()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target_set_id BIGINT := COALESCE(NEW.applicability_set_id, OLD.applicability_set_id);
    target_fault_code_id BIGINT;
BEGIN
    FOR target_fault_code_id IN
        SELECT fault_code_id FROM rb_fault_codes WHERE applicability_set_id = target_set_id
    LOOP
        PERFORM rb_enqueue_fault_code_assessment(target_fault_code_id);
    END LOOP;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER rb_applicability_rules_queue_fault_code_assessments
AFTER INSERT OR UPDATE OR DELETE ON rb_applicability_rules
FOR EACH ROW EXECUTE FUNCTION rb_queue_applicability_fault_code_assessments();

CREATE OR REPLACE FUNCTION rb_claim_worker_job(worker_name TEXT, lease_seconds INTEGER DEFAULT 60)
RETURNS SETOF rb_worker_jobs LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    RETURN QUERY
    WITH candidate AS (
        SELECT worker_job_id FROM rb_worker_jobs
        WHERE (status IN ('pending','retry') AND available_at <= now())
           OR (status = 'leased' AND leased_until <= now())
        ORDER BY priority, worker_job_id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE rb_worker_jobs j
    SET status = 'leased', lease_owner = worker_name,
        leased_until = now() + make_interval(secs => lease_seconds),
        attempts = attempts + 1, updated_at = now()
    FROM candidate c
    WHERE j.worker_job_id = c.worker_job_id
    RETURNING j.*;
END $$;

CREATE OR REPLACE FUNCTION rb_complete_worker_job(target_job_id BIGINT, worker_name TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    UPDATE rb_worker_jobs SET status = 'succeeded', lease_owner = NULL, leased_until = NULL,
        last_error = NULL, completed_at = now(), updated_at = now()
    WHERE worker_job_id = target_job_id AND status = 'leased' AND lease_owner = worker_name;
    IF NOT FOUND THEN RAISE EXCEPTION 'worker job % is not leased by %', target_job_id, worker_name; END IF;
END $$;

CREATE OR REPLACE FUNCTION rb_fail_worker_job(target_job_id BIGINT, worker_name TEXT, error_message TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    UPDATE rb_worker_jobs SET
        status = CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'retry' END,
        available_at = now() + make_interval(secs => LEAST(3600, 30 * (2 ^ GREATEST(attempts - 1, 0))::INTEGER)),
        lease_owner = NULL, leased_until = NULL, last_error = left(error_message, 2000), updated_at = now()
    WHERE worker_job_id = target_job_id AND status = 'leased' AND lease_owner = worker_name;
    IF NOT FOUND THEN RAISE EXCEPTION 'worker job % is not leased by %', target_job_id, worker_name; END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'outboard_worker') THEN
        GRANT SELECT ON rb_worker_jobs, rb_fault_codes TO outboard_worker;
        GRANT EXECUTE ON FUNCTION rb_claim_worker_job(TEXT, INTEGER) TO outboard_worker;
        GRANT EXECUTE ON FUNCTION rb_complete_worker_job(BIGINT, TEXT) TO outboard_worker;
        GRANT EXECUTE ON FUNCTION rb_fail_worker_job(BIGINT, TEXT, TEXT) TO outboard_worker;
        GRANT EXECUTE ON FUNCTION rb_assess_fault_code_readiness(BIGINT) TO outboard_worker;
    END IF;
END $$;

REVOKE ALL ON FUNCTION rb_assess_fault_code_readiness(BIGINT) FROM PUBLIC;
REVOKE ALL ON FUNCTION rb_fault_code_publication_blockers(BIGINT) FROM PUBLIC;
REVOKE ALL ON FUNCTION rb_enqueue_fault_code_assessment(BIGINT) FROM PUBLIC;
REVOKE ALL ON FUNCTION rb_claim_worker_job(TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION rb_complete_worker_job(BIGINT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION rb_fail_worker_job(BIGINT, TEXT, TEXT) FROM PUBLIC;

GRANT SELECT ON rb_public_fault_codes TO outboard_app;
GRANT EXECUTE ON FUNCTION rb_fault_code_publication_blockers(BIGINT) TO outboard_app;

INSERT INTO schema_migrations(version, filename)
VALUES ('014', '014_outboard_fault_code_workflow.sql')
ON CONFLICT (version) DO NOTHING;
