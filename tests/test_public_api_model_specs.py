from pathlib import Path

SQL = (Path(__file__).parents[1] / "db/migrations/018_public_api_model_specs.sql").read_text()

def test_model_specs_contract_and_security():
    for column in ("model_id", "brand_key", "category_key", "specs", "published", "updated_at"):
        assert column in SQL
    assert "scraped_at" not in SQL and "created_at" not in SQL
    assert "GRANT SELECT(model_id,specs)" in SQL
    assert "GRANT SELECT ON api_public.model_specs TO anon,authenticated" in SQL
    assert "GRANT INSERT" not in SQL and "GRANT UPDATE" not in SQL

def test_only_nonempty_json_objects_are_projected():
    assert "jsonb_typeof(s.specs)='object'" in SQL
    assert "s.specs<>'{}'::jsonb" in SQL
    assert "JOIN api_public.models" in SQL
