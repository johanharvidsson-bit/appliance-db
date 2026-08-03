import os
from urllib.parse import urlparse

import psycopg2
import pytest

from workers.cube_repository import CubeRepository


def dsn():
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value:
        pytest.skip("isolated dev database is not configured")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.path != "/repair_appliance_dev":
        pytest.fail("cube worker integration tests require isolated loopback repair_appliance_dev")
    return value


def test_scope_history_lock_and_internal_security():
    connection = psycopg2.connect(dsn())
    try:
        repo = CubeRepository(connection)
        first = repo.snapshot("appliance-repair-base", "development", create=True, force_new=True)
        second = repo.snapshot("appliance-repair-base", "development", create=True, force_new=True)
        assert second["scope_version"] == first["scope_version"] + 1
        with connection.cursor() as cursor:
            cursor.execute("SELECT status FROM cube_scope_snapshots WHERE id=%s", (first["id"],))
            assert cursor.fetchone()[0] == "superseded"
            for table in ("worker_runs","cube_scope_snapshots","cube_coverage_observations","findings","content_backlog"):
                cursor.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass", (table,))
                assert cursor.fetchone() == (True, True)
                cursor.execute("SELECT has_table_privilege('anon',%s,'SELECT,INSERT,UPDATE,DELETE')", (table,))
                assert cursor.fetchone()[0] is False
        assert repo.lock("appliance-repair-base", "development", second["id"])
        other = psycopg2.connect(dsn())
        try:
            assert CubeRepository(other).lock("appliance-repair-base", "development", second["id"]) is False
        finally:
            other.close()
        repo.unlock("appliance-repair-base", "development", second["id"])
    finally:
        connection.rollback()
        connection.close()
