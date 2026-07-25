-- Migration 006: Add series column to models
--
-- series: the model family grouping key shown in the UI.
-- e.g. WW80K, B1245, WF45T, FlexWash WV60M
--
-- Populated by pipeline/populate_series.py after this migration runs.
-- Can be manually corrected per row without touching other columns.

ALTER TABLE models
    ADD COLUMN IF NOT EXISTS series TEXT;

CREATE INDEX IF NOT EXISTS idx_models_series ON models (series);

INSERT INTO schema_migrations (version, filename) VALUES
    ('006', '006_add_series_to_models.sql')
ON CONFLICT (version) DO NOTHING;
