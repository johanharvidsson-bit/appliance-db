from pathlib import Path

SQL = (Path(__file__).parents[1] / "db/migrations/016_public_api_error_codes.sql").read_text()

def test_error_code_contract_is_public_and_read_only():
    for column in ("error_code_id", "brand_key", "category_key", "code", "short_description", "description", "severity", "diy_possible", "published", "verified_at"):
        assert column in SQL
    assert "scrape_status" not in SQL and "source::" not in SQL
    assert "GRANT SELECT ON api_public.error_codes TO anon,authenticated" in SQL
    assert "GRANT INSERT" not in SQL and "GRANT UPDATE" not in SQL

def test_publication_is_explicit_and_not_scrape_derived():
    assert "last_verified_at IS NOT NULL" in SQL
    assert "short_description" in SQL
    assert "scrape_status" not in SQL
    assert "repairbase:v1:error_code:" in SQL
