from pathlib import Path
import json, os
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import psycopg2
import pytest

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

EXPECTED_COLUMNS=["model_id","brand_key","category_key","specs","published","updated_at"]

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

def test_live_contract_relation_and_publication():
    columns=_query("SELECT a.attname,format_type(a.atttypid,a.atttypmod) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='api_public' AND c.relname='model_specs' AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum")
    assert [row[0] for row in columns]==EXPECTED_COLUMNS
    assert not {"id","source_id","scraped_at","created_at"}.intersection(row[0] for row in columns)
    assert _query("SELECT model_id FROM api_public.model_specs GROUP BY model_id HAVING count(*)>1")==[]
    assert _query("SELECT count(*) FROM api_public.model_specs WHERE NOT published OR updated_at IS NOT NULL OR jsonb_typeof(specs)<>'object' OR specs='{}'::jsonb")[0][0]==0
    assert _query("SELECT count(*) FROM api_public.model_specs s LEFT JOIN api_public.models m USING(model_id) WHERE m.model_id IS NULL")[0][0]==0

@pytest.mark.parametrize("role",["anon","authenticated"])
def test_live_roles_are_read_only(role):
    _query("SELECT model_id FROM api_public.model_specs LIMIT 1",role=role)
    assert not _query("SELECT has_table_privilege(%s,'api_public.model_specs','INSERT,UPDATE,DELETE,TRUNCATE')",(role,))[0][0]

def test_live_query_plan_executes():
    plan=_query("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT model_id FROM api_public.model_specs WHERE category_key='washing_machine' ORDER BY model_id LIMIT 50")
    assert plan[0][0][0]["Execution Time"]<1000

def test_postgrest_filters_identity_and_cap():
    base=os.getenv("REPAIRBASE_POSTGREST_DEV_URL")
    if not base: pytest.skip("explicit dev PostgREST URL not set")
    if urlparse(base).hostname not in {"127.0.0.1","localhost"}: pytest.fail("loopback PostgREST required")
    url=base.rstrip("/")+"/model_specs?"+urlencode({"select":"*","published":"eq.true","order":"model_id.asc","limit":"3"},safe=".,()*")
    with urlopen(Request(url,headers={"Accept-Profile":"api_public"}),timeout=10) as response: rows=json.load(response)
    assert len(rows)<=3
    if rows: assert list(rows[0])==EXPECTED_COLUMNS and rows[0]["published"] is True
