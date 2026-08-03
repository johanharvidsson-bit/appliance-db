-- Migration 010: Generic model_specs (JSONB) replacing per-category typed spec tables
--
-- washing_machine_specs (migration 008) used one typed column per spec field,
-- which doesn't scale across categories or across future site verticals —
-- every new appliance type needed its own table + its own fetch function.
-- This adds a generic model_specs table (one JSONB blob per model) that any
-- category, on any site built from this schema template, can write into
-- without a schema change.
--
-- washing_machine_specs is NOT dropped here. Existing data is copied over,
-- but the old table stays in place as a rollback safety net until the new
-- path has run in production for a while — drop it in a later migration
-- once confirmed stable.

CREATE TABLE IF NOT EXISTS model_specs (
    model_id   INTEGER PRIMARY KEY REFERENCES models(id) ON DELETE CASCADE,
    specs      JSONB NOT NULL DEFAULT '{}'::jsonb,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_specs_model ON model_specs (model_id);
CREATE INDEX IF NOT EXISTS idx_model_specs_gin   ON model_specs USING GIN (specs);

-- Backfill existing washing machine specs into the generic table
INSERT INTO model_specs (model_id, specs, scraped_at, created_at)
SELECT
    model_id,
    jsonb_strip_nulls(jsonb_build_object(
        'capacity_kg',            capacity_kg,
        'spin_speed_rpm',         spin_speed_rpm,
        'energy_class',           energy_class,
        'width_mm',               width_mm,
        'height_mm',              height_mm,
        'depth_mm',               depth_mm,
        'noise_spinning_db',      noise_spinning_db,
        'energy_consumption_kwh', energy_consumption_kwh,
        'water_consumption_l',    water_consumption_l,
        'door_type',              door_type
    )),
    scraped_at,
    created_at
FROM washing_machine_specs
ON CONFLICT (model_id) DO NOTHING;

-- ── RLS ────────────────────────────────────────────────────────────────────

ALTER TABLE model_specs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read model_specs"
    ON model_specs FOR SELECT USING (true);

GRANT SELECT ON model_specs TO anon, authenticated;

-- ── migration tracking ─────────────────────────────────────────────────────

INSERT INTO schema_migrations (version, filename)
VALUES ('010', '010_model_specs_generic.sql')
ON CONFLICT (version) DO NOTHING;
