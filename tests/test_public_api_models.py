"""Focused dev contract tests for migration 013."""

import json
import os
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import psycopg2
import pytest


EXPECTED_COLUMNS = [
    "model_id",
    "brand_key",
    "category_key",
    "product_line_key",
    "name",
    "slug",
    "series",
    "release_year",
    "manual_url",
    "indexable",
    "updated_at",
]
FORBIDDEN_COLUMNS = {
    "id",
    "brand_id",
    "category_id",
    "product_line_id",
    "base_model",
    "manual_pdf_url",
    "manual_pdf_path",
    "scrape_status",
    "last_scraped_at",
    "created_at",
}


def _dsn() -> str:
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value:
        pytest.skip("explicit dev integration DSN not set")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        pytest.fail("tests require a loopback database target")
    if parsed.path != "/repair_appliance_dev":
        pytest.fail("tests require repair_appliance_dev")
    return value


def _query(sql: str, params=(), role: str | None = None):
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            if role:
                cursor.execute(f"SET LOCAL ROLE {role}")
            cursor.execute(sql, params)
            return cursor.fetchall()


def test_exact_contract_columns_types_and_nullability():
    columns = _query(
        "SELECT a.attname, format_type(a.atttypid,a.atttypmod), "
        "a.attnotnull FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='api_public' AND c.relname='models' "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
    )
    assert [row[0] for row in columns] == EXPECTED_COLUMNS
    assert [row[1] for row in columns] == [
        "uuid", "text", "text", "text", "text", "text", "text",
        "integer", "text", "boolean", "timestamp with time zone",
    ]
    assert not FORBIDDEN_COLUMNS.intersection(row[0] for row in columns)


def test_identity_relations_and_publication_compatibility_gate():
    assert _query("SELECT count(*) FROM api_public.models WHERE model_id IS NULL")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.models GROUP BY model_id HAVING count(*) > 1") == []
    assert _query("SELECT count(*) FROM api_public.models GROUP BY brand_key,category_key,slug HAVING count(*) > 1") == []
    assert _query("SELECT count(*) FROM api_public.models WHERE name='' OR slug !~ '^[a-z0-9]+(-[a-z0-9]+)*$'")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.models WHERE indexable OR manual_url IS NOT NULL OR updated_at IS NOT NULL")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.models m LEFT JOIN api_public.brands b USING (brand_key) WHERE b.brand_key IS NULL")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.models m WHERE NOT EXISTS (SELECT 1 FROM api_public.category_pages c WHERE c.category_key=m.category_key)")[0][0] == 0


def test_identity_is_stable_and_slug_independent():
    rows = _query(
        "SELECT i.source_id,i.public_id,m.slug FROM public.api_public_identities i "
        "JOIN public.models m ON m.id=i.source_id WHERE i.resource_type='model' "
        "ORDER BY i.source_id LIMIT 2"
    )
    assert len(rows) == 2
    assert rows[0][1] != rows[1][1]
    source_id, public_id, _ = rows[0]
    rerun = _query(
        "SELECT public_id FROM public.api_public_identities "
        "WHERE resource_type='model' AND source_id=%s",
        (source_id,),
    )[0][0]
    assert rerun == public_id


def test_actual_slug_change_does_not_change_model_id():
    with psycopg2.connect(_dsn()) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT m.id,m.slug,i.public_id FROM public.models m "
                    "JOIN public.api_public_identities i ON i.resource_type='model' "
                    "AND i.source_id=m.id ORDER BY m.id LIMIT 1"
                )
                source_id, slug, public_id = cursor.fetchone()
                cursor.execute(
                    "UPDATE public.models SET slug=%s WHERE id=%s",
                    (slug + "-identity-test", source_id),
                )
                cursor.execute("REFRESH MATERIALIZED VIEW api_public.models")
                cursor.execute(
                    "SELECT model_id FROM api_public.models "
                    "WHERE model_id=%s AND slug=%s",
                    (public_id, slug + "-identity-test"),
                )
                assert cursor.fetchone() == (public_id,)
        finally:
            connection.rollback()


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_public_roles_read_but_cannot_write(role):
    _query("SELECT model_id FROM api_public.models LIMIT 1", role=role)
    assert not _query(
        "SELECT has_table_privilege(%s,'api_public.models','INSERT,UPDATE,DELETE,TRUNCATE')",
        (role,),
    )[0][0]


def test_owner_source_grants_are_column_scoped():
    grants = set(
        _query(
            "SELECT table_name,column_name FROM information_schema.column_privileges "
            "WHERE table_schema='public' AND grantee='api_public_owner'"
        )
    )
    model_columns = {column for table, column in grants if table == "models"}
    assert model_columns == {
        "id", "brand_id", "category_id", "product_line_id", "name", "slug",
        "series", "release_year",
    }
    assert not {"manual_url", "manual_pdf_url", "manual_pdf_path", "scrape_status"}.intersection(model_columns)


def test_deterministic_keyset_pagination():
    first = _query(
        'SELECT name,model_id FROM api_public.models '
        'ORDER BY name COLLATE "C",model_id LIMIT 100'
    )
    assert first
    name, model_id = first[-1]
    second = _query(
        'SELECT name,model_id FROM api_public.models '
        'WHERE (name COLLATE "C",model_id)>(%s,%s) '
        'ORDER BY name COLLATE "C",model_id LIMIT 100',
        (name, model_id),
    )
    combined = first + second
    assert len(combined) == len(set(combined))
    assert combined == sorted(combined)


def _postgrest_get(params: dict[str, str]):
    base = os.getenv("REPAIRBASE_POSTGREST_DEV_URL")
    if not base:
        pytest.skip("explicit dev PostgREST URL not set")
    parsed = urlparse(base)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        pytest.fail("PostgREST tests require a loopback target")
    request = Request(
        base.rstrip("/") + "/models?" + urlencode(params, safe=".,()*"),
        headers={"Accept-Profile": "api_public", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.load(response), response.headers
    except HTTPError as error:
        pytest.fail(f"PostgREST returned HTTP {error.code}")


def test_postgrest_filters_order_limit_and_field_allowlist():
    status, rows, _ = _postgrest_get(
        {"select": "*", "brand_key": "eq.samsung", "order": "name.asc,model_id.asc", "limit": "3"}
    )
    assert status == 200
    assert 0 < len(rows) <= 3
    assert list(rows[0]) == EXPECTED_COLUMNS
    assert not FORBIDDEN_COLUMNS.intersection(rows[0])
    assert all(row["brand_key"] == "samsung" for row in rows)


def test_postgrest_category_identity_and_max_rows():
    status, filtered, _ = _postgrest_get(
        {"select": "model_id,category_key", "category_key": "eq.washing_machine", "limit": "2"}
    )
    assert status == 200
    assert 0 < len(filtered) <= 2
    model_id = filtered[0]["model_id"]
    status, identity, _ = _postgrest_get({"select": "model_id", "model_id": f"eq.{model_id}"})
    assert status == 200 and identity == [{"model_id": model_id}]
    status, capped, _ = _postgrest_get({"select": "model_id", "limit": "1500"})
    assert status == 200
    assert len(capped) <= 1000
