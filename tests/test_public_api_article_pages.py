from pathlib import Path
import json, os
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import psycopg2
import pytest

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

EXPECTED_COLUMNS = ["article_page_id","article_id","subject_id","article_type","brand_key","category_key","locale","slug","title","description","h1","quick_fix","intro_html","causes_json","symptoms_json","steps_json","affected_models_json","when_to_call_technician_html","prevention_html","faq_json","parts_json","canonical_path","indexable","published_at","updated_at"]

def _dsn():
    value=os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value: pytest.skip("explicit dev integration DSN not set")
    if urlparse(value).hostname not in {"127.0.0.1","localhost"}: pytest.fail("loopback dev database required")
    return value

def _query(sql,params=(),role=None):
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            if role: cursor.execute(f"SET LOCAL ROLE {role}")
            cursor.execute(sql,params)
            return cursor.fetchall()

def test_live_contract_identity_routes_and_publication():
    columns=_query("SELECT a.attname,format_type(a.atttypid,a.atttypmod) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='api_public' AND c.relname='article_pages' AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum")
    assert [row[0] for row in columns]==EXPECTED_COLUMNS
    assert not {"id","error_code_id","fault_id","author_id","review_flag","translation_status"}.intersection(row[0] for row in columns)
    assert _query("SELECT article_page_id FROM api_public.article_pages GROUP BY article_page_id HAVING count(*)>1")==[]
    assert _query("SELECT article_id,locale FROM api_public.article_pages GROUP BY article_id,locale HAVING count(*)>1")==[]
    assert _query("SELECT count(*) FROM api_public.article_pages WHERE NOT indexable OR published_at IS NULL OR canonical_path !~ '^/[^?#]*/$'")[0][0]==0
    assert _query("SELECT count(*) FROM api_public.article_pages WHERE article_type IN ('fault','fault_no_code') AND canonical_path NOT LIKE '%/problems/%'")[0][0]==0

@pytest.mark.parametrize("role",["anon","authenticated"])
def test_live_roles_are_read_only(role):
    _query("SELECT article_page_id FROM api_public.article_pages LIMIT 1",role=role)
    assert not _query("SELECT has_table_privilege(%s,'api_public.article_pages','INSERT,UPDATE,DELETE,TRUNCATE')",(role,))[0][0]

def test_live_query_plan_executes():
    plan=_query("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT article_page_id FROM api_public.article_pages WHERE locale='en' ORDER BY canonical_path,article_page_id LIMIT 50")
    assert plan[0][0][0]["Execution Time"]<1000

def test_postgrest_filters_order_and_cap():
    base=os.getenv("REPAIRBASE_POSTGREST_DEV_URL")
    if not base: pytest.skip("explicit dev PostgREST URL not set")
    if urlparse(base).hostname not in {"127.0.0.1","localhost"}: pytest.fail("loopback PostgREST required")
    url=base.rstrip("/")+"/article_pages?"+urlencode({"select":"*","locale":"eq.en","indexable":"eq.true","order":"canonical_path.asc,article_page_id.asc","limit":"3"},safe=".,()*")
    with urlopen(Request(url,headers={"Accept-Profile":"api_public"}),timeout=10) as response: rows=json.load(response)
    assert len(rows)<=3
    if rows: assert list(rows[0])==EXPECTED_COLUMNS and rows[0]["locale"]=="en"
