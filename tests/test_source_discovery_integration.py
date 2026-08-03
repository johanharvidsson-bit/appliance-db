import os
from urllib.parse import urlparse

import psycopg2
import pytest


def dsn():
    value=os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value: pytest.skip("isolated dev database is not configured")
    parsed=urlparse(value)
    if parsed.hostname not in {"127.0.0.1","localhost"} or parsed.path!="/repair_appliance_dev":
        pytest.fail("source discovery integration requires isolated loopback repair_appliance_dev")
    return value


def test_candidate_tables_are_internal_and_history_preserving():
    with psycopg2.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            for table in ("source_candidates","source_discovery_cache"):
                cursor.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass",(table,))
                assert cursor.fetchone()==(True,True)
                for role in ("anon","authenticated"):
                    cursor.execute("SELECT has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE')",(role,table))
                    assert cursor.fetchone()[0] is False
                cursor.execute("SELECT has_table_privilege('service_role',%s,'DELETE')",(table,))
                assert cursor.fetchone()[0] is False


def test_candidate_identity_and_not_found_constraints_exist():
    with psycopg2.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='source_candidates'")
            definitions=" ".join(row[0] for row in cursor.fetchall())
            assert "backlog_id" in definitions and "candidate_key" in definitions
            cursor.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='source_candidates'::regclass")
            assert any("not_found" in row[0] for row in cursor.fetchall())
