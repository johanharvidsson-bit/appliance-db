-- Migration 008: Model specifications
--
-- Adds a dedicated typed table for washing machine specs.
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
    capacity_kg             NUMERIC(4,1),      -- Drum capacity in kg
    spin_speed_rpm          INTEGER,            -- Max centrifuge speed in RPM
    energy_class            TEXT,               -- EU energy rating: A, B, C, D, E, F, G
    width_mm                INTEGER,            -- Width in mm
    height_mm               INTEGER,            -- Height in mm
    depth_mm                INTEGER,            -- Depth in mm
    noise_spinning_db       NUMERIC(4,1),       -- Centrifuge noise level in dB
    energy_consumption_kwh  NUMERIC(6,1),       -- Annual energy consumption in kWh
    water_consumption_l     NUMERIC(6,1),       -- Annual water consumption in litres
    door_type               TEXT,               -- 'front' | 'top'
    scraped_at              TIMESTAMPTZ,        -- When this row was last populated by scraper
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT wm_specs_door_type_check CHECK (door_type IN ('front', 'top'))
);

CREATE INDEX IF NOT EXISTS idx_wm_specs_model ON washing_machine_specs (model_id);

-- ── RLS ────────────────────────────────────────────────────────────────────

ALTER TABLE washing_machine_specs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read washing_machine_specs"
    ON washing_machine_specs FOR SELECT USING (true);

GRANT SELECT ON washing_machine_specs TO anon, authenticated;

-- ── migration tracking ─────────────────────────────────────────────────────

INSERT INTO schema_migrations (version, filename)
VALUES ('008', '008_model_specs.sql')
ON CONFLICT (version) DO NOTHING;
