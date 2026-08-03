from pathlib import Path
import json, os
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import psycopg2
import pytest

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

EXPECTED_COLUMNS = ["error_code_id","brand_key","category_key","code","short_description","description","severity","diy_possible","published","verified_at","updated_at"]

def _dsn():
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value: pytest.skip("explicit dev integration DSN not set")
    if urlparse(value).hostname not in {"127.0.0.1","localhost"}: pytest.fail("loopback dev database required")
    return value

def _query(sql, params=(), role=None):
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            if role: cursor.execute(f"SET LOCAL ROLE {role}")
            cursor.execute(sql, params)
            return cursor.fetchall()

def test_live_contract_identity_relations_and_publication():
    columns = _query("SELECT a.attname,format_type(a.atttypid,a.atttypmod) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='api_public' AND c.relname='error_codes' AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum")
    assert [row[0] for row in columns] == EXPECTED_COLUMNS
    assert not {"id","brand_id","category_id","source","scrape_status"}.intersection(row[0] for row in columns)
    assert _query("SELECT error_code_id FROM api_public.error_codes GROUP BY error_code_id HAVING count(*)>1") == []
    assert _query("SELECT count(*) FROM api_public.error_codes WHERE published<>(verified_at IS NOT NULL AND short_description IS NOT NULL)")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.error_codes e LEFT JOIN api_public.brands b USING(brand_key) WHERE b.brand_key IS NULL")[0][0] == 0

@pytest.mark.parametrize("role", ["anon","authenticated"])
def test_live_roles_are_read_only(role):
    _query("SELECT error_code_id FROM api_public.error_codes LIMIT 1", role=role)
    assert not _query("SELECT has_table_privilege(%s,'api_public.error_codes','INSERT,UPDATE,DELETE,TRUNCATE')", (role,))[0][0]

def test_live_query_plan_executes():
    plan = _query("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT error_code_id FROM api_public.error_codes WHERE published ORDER BY code,error_code_id LIMIT 50")
    assert plan[0][0][0]["Execution Time"] < 1000

def test_postgrest_filters_order_and_cap():
    base=os.getenv("REPAIRBASE_POSTGREST_DEV_URL")
    if not base: pytest.skip("explicit dev PostgREST URL not set")
    if urlparse(base).hostname not in {"127.0.0.1","localhost"}: pytest.fail("loopback PostgREST required")
    url=base.rstrip("/")+"/error_codes?"+urlencode({"select":"*","published":"eq.true","order":"code.asc,error_code_id.asc","limit":"3"},safe=".,()*")
    with urlopen(Request(url,headers={"Accept-Profile":"api_public"}),timeout=10) as response: rows=json.load(response)
    assert len(rows)<=3
    if rows: assert list(rows[0])==EXPECTED_COLUMNS and rows[0]["published"] is True
