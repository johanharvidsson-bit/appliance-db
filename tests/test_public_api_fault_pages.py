from pathlib import Path

SQL = (Path(__file__).parents[1] / "db/migrations/015_public_api_fault_pages.sql").read_text()

def test_fault_pages_contract_and_security():
    for column in ("fault_page_id", "fault_id", "brand_key", "category_key", "locale", "canonical_path", "indexable"):
        assert column in SQL
    assert "scrape_status" not in SQL
    assert "false AS indexable" in SQL
    assert "GRANT SELECT ON api_public.fault_pages TO anon,authenticated" in SQL
    assert "GRANT INSERT" not in SQL and "GRANT UPDATE" not in SQL

def test_fault_identity_is_independent_of_localized_content():
    identity = "'repairbase:v1:fault:'||b.public_key||':'||c.public_key||':'||f.slug"
    assert identity in SQL
    assert "symptom_name" not in identity and "meta_title" not in identity
