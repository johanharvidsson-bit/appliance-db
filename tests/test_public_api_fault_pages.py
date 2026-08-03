from pathlib import Path
import json
import os
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import psycopg2
import pytest

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

EXPECTED_COLUMNS = ["fault_page_id", "fault_id", "brand_key", "category_key", "locale", "slug", "name", "title", "description", "canonical_path", "indexable", "published_at", "updated_at"]

def _dsn():
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value: pytest.skip("explicit dev integration DSN not set")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"}: pytest.fail("loopback dev database required")
    return value

def _query(sql, params=(), role=None):
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            if role: cursor.execute(f"SET LOCAL ROLE {role}")
            cursor.execute(sql, params)
            return cursor.fetchall()

def test_live_contract_identity_routes_and_publication():
    columns = _query("SELECT a.attname,format_type(a.atttypid,a.atttypmod) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='api_public' AND c.relname='fault_pages' AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum")
    assert [row[0] for row in columns] == EXPECTED_COLUMNS
    assert not {"id", "brand_id", "category_id", "translation_id"}.intersection(row[0] for row in columns)
    assert _query("SELECT fault_page_id FROM api_public.fault_pages GROUP BY fault_page_id HAVING count(*)>1") == []
    assert _query("SELECT fault_id,locale FROM api_public.fault_pages GROUP BY fault_id,locale HAVING count(*)>1") == []
    assert _query("SELECT count(*) FROM api_public.fault_pages WHERE indexable OR published_at IS NOT NULL")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.fault_pages WHERE canonical_path !~ '^/[^?#]*/$'")[0][0] == 0

@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_live_roles_are_read_only(role):
    _query("SELECT fault_page_id FROM api_public.fault_pages LIMIT 1", role=role)
    assert not _query("SELECT has_table_privilege(%s,'api_public.fault_pages','INSERT,UPDATE,DELETE,TRUNCATE')", (role,))[0][0]

def test_live_query_plan_executes():
    plan = _query("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT fault_page_id FROM api_public.fault_pages WHERE locale='en' ORDER BY canonical_path,fault_page_id LIMIT 50")
    assert plan[0][0][0]["Execution Time"] < 1000

def test_postgrest_filters_identity_order_and_cap():
    base = os.getenv("REPAIRBASE_POSTGREST_DEV_URL")
    if not base: pytest.skip("explicit dev PostgREST URL not set")
    if urlparse(base).hostname not in {"127.0.0.1", "localhost"}: pytest.fail("loopback PostgREST required")
    url = base.rstrip("/") + "/fault_pages?" + urlencode({"select":"*","locale":"eq.en","order":"canonical_path.asc,fault_page_id.asc","limit":"3"}, safe=".,()*")
    with urlopen(Request(url, headers={"Accept-Profile":"api_public"}), timeout=10) as response:
        rows = json.load(response)
    assert len(rows) <= 3
    if rows:
        assert list(rows[0]) == EXPECTED_COLUMNS and rows[0]["locale"] == "en"
