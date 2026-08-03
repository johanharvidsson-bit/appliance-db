from pathlib import Path

SQL = (Path(__file__).parents[1] / "db/migrations/017_public_api_article_pages.sql").read_text()

def test_article_pages_contract_security_and_publication():
    for column in ("article_page_id", "article_id", "subject_id", "article_type", "locale", "canonical_path", "indexable", "published_at"):
        assert column in SQL
    assert "translation_status='published'" in SQL and "a.status='published'" in SQL
    assert "scrape_status" not in SQL and "source_locale" not in SQL
    assert "GRANT SELECT ON api_public.article_pages TO anon,authenticated" in SQL
    assert "GRANT INSERT" not in SQL and "GRANT UPDATE" not in SQL

def test_page_identity_is_locale_specific_but_content_independent():
    assert "repairbase:v1:article_page:" in SQL
    identity_line = next(line for line in SQL.splitlines() if "repairbase:v1:article_page:" in line)
    assert "t.locale" in identity_line
    assert "title" not in identity_line and "slug" not in identity_line
