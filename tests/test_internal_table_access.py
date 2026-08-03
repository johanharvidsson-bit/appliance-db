"""Dev-only integration checks for migration 011.

The suite is skipped unless REPAIRBASE_SECURITY_TEST_DB_URL is explicitly set.
It refuses every database except the isolated local repair_appliance_dev target.
"""

import os
from urllib.parse import urlparse

import psycopg2
import pytest


INTERNAL_TABLES = ("scrape_jobs", "schema_migrations")
FRONTEND_TABLES = (
    "brands",
    "categories",
    "category_translations",
    "models",
    "articles",
    "article_translations",
)


def _dev_dsn() -> str:
    dsn = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not dsn:
        pytest.skip("REPAIRBASE_SECURITY_TEST_DB_URL is not set")
    parsed = urlparse(dsn)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        pytest.fail("security access tests require a loopback database target")
    if parsed.path.lstrip("/") != "repair_appliance_dev":
        pytest.fail("security access tests require repair_appliance_dev")
    return dsn


def _select_as(role: str, table: str) -> None:
    with psycopg2.connect(_dev_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(f"SET LOCAL ROLE {role}")
            cursor.execute(f"SELECT 1 FROM public.{table} LIMIT 1")


@pytest.mark.parametrize("role", ("anon", "authenticated"))
@pytest.mark.parametrize("table", INTERNAL_TABLES)
def test_public_roles_cannot_read_internal_tables(role: str, table: str) -> None:
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        _select_as(role, table)


@pytest.mark.parametrize("table", INTERNAL_TABLES)
def test_service_role_can_read_internal_tables(table: str) -> None:
    _select_as("service_role", table)


@pytest.mark.parametrize("table", FRONTEND_TABLES)
def test_anon_can_still_read_frontend_tables(table: str) -> None:
    _select_as("anon", table)
