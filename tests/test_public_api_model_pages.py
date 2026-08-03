"""Focused dev contract tests for migration 014."""

import json
import os
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import psycopg2
import pytest


EXPECTED_COLUMNS = [
    "model_page_id",
    "model_id",
    "brand_key",
    "category_key",
    "locale",
    "category_slug",
    "model_slug",
    "canonical_path",
    "hreflang",
    "indexable",
    "published_at",
    "updated_at",
]
EXPECTED_TYPES = [
    "uuid",
    "uuid",
    "text",
    "text",
    "text",
    "text",
    "text",
    "text",
    "jsonb",
    "boolean",
    "timestamp with time zone",
    "timestamp with time zone",
]
FORBIDDEN_COLUMNS = {
    "id",
    "source_id",
    "brand_id",
    "category_id",
    "translation_id",
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


def test_exact_contract_columns_types_and_data_nullability():
    columns = _query(
        "SELECT a.attname,format_type(a.atttypid,a.atttypmod) "
        "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='api_public' AND c.relname='model_pages' "
        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"
    )
    assert [column[0] for column in columns] == EXPECTED_COLUMNS
    assert [column[1] for column in columns] == EXPECTED_TYPES
    assert not FORBIDDEN_COLUMNS.intersection(column[0] for column in columns)
    required = "model_page_id,model_id,brand_key,category_key,locale,category_slug,model_slug,canonical_path,hreflang,indexable"
    assert _query(f"SELECT count(*) FROM api_public.model_pages WHERE num_nulls({required})>0")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.model_pages WHERE published_at IS NOT NULL")[0][0] == 0


def test_unique_identity_relation_locale_and_paths():
    assert _query("SELECT model_page_id FROM api_public.model_pages GROUP BY model_page_id HAVING count(*)>1") == []
    assert _query("SELECT model_id,locale FROM api_public.model_pages GROUP BY model_id,locale HAVING count(*)>1") == []
    assert _query("SELECT canonical_path FROM api_public.model_pages GROUP BY canonical_path HAVING count(*)>1") == []
    assert _query("SELECT count(*) FROM api_public.model_pages p LEFT JOIN api_public.models m USING(model_id) WHERE m.model_id IS NULL")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.model_pages WHERE locale !~ '^[a-z]{2}(-[A-Z]{2})?$'")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.model_pages WHERE canonical_path !~ '^/[^?#]*/$'")[0][0] == 0


def test_exact_locale_rows_no_fallback_and_all_pages_indexable():
    expected = _query(
        "SELECT count(*) FROM api_public.models m JOIN api_public.category_pages c "
        "ON c.category_key=m.category_key"
    )[0][0]
    actual = _query("SELECT count(*) FROM api_public.model_pages")[0][0]
    assert actual == expected
    assert _query("SELECT count(*) FROM api_public.model_pages WHERE NOT indexable")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.model_pages p WHERE NOT (p.hreflang ? p.locale)")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.model_pages p WHERE (SELECT count(*) FROM jsonb_object_keys(p.hreflang)) <> (SELECT count(*) FROM api_public.category_pages c WHERE c.category_key=p.category_key)")[0][0] == 0


def test_page_identity_is_stable_across_refresh():
    before = _query("SELECT model_id,locale,model_page_id FROM api_public.model_pages ORDER BY model_id,locale LIMIT 20")
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("REFRESH MATERIALIZED VIEW api_public.model_pages")
        connection.commit()
    after = _query("SELECT model_id,locale,model_page_id FROM api_public.model_pages ORDER BY model_id,locale LIMIT 20")
    assert after == before


def test_name_and_slug_changes_do_not_change_page_identity():
    with psycopg2.connect(_dsn()) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT i.source_id,m.name,m.slug,p.model_id,p.model_page_id,p.locale "
                    "FROM public.api_public_identities i "
                    "JOIN public.models m ON m.id=i.source_id "
                    "JOIN api_public.model_pages p ON p.model_id=i.public_id "
                    "WHERE i.resource_type='model' ORDER BY i.source_id,p.locale LIMIT 1"
                )
                source_id, name, slug, model_id, page_id, locale = cursor.fetchone()
                cursor.execute(
                    "UPDATE public.models SET name=%s,slug=%s WHERE id=%s",
                    (name + " identity test", slug + "-identity-test", source_id),
                )
                cursor.execute("REFRESH MATERIALIZED VIEW api_public.models")
                cursor.execute("REFRESH MATERIALIZED VIEW api_public.model_pages")
                cursor.execute(
                    "SELECT model_page_id,model_slug FROM api_public.model_pages "
                    "WHERE model_id=%s AND locale=%s",
                    (model_id, locale),
                )
                assert cursor.fetchone() == (page_id, slug + "-identity-test")
        finally:
            connection.rollback()


def test_different_models_and_locales_do_not_collide():
    rows = _query("SELECT model_id,locale,model_page_id FROM api_public.model_pages ORDER BY model_id,locale LIMIT 4")
    assert len({row[2] for row in rows}) == len(rows)
    same_model = _query("SELECT locale,model_page_id FROM api_public.model_pages WHERE model_id=(SELECT model_id FROM api_public.model_pages GROUP BY model_id HAVING count(*)>1 LIMIT 1) ORDER BY locale")
    assert len(same_model) > 1
    assert len({row[1] for row in same_model}) == len(same_model)


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_public_roles_read_but_cannot_write(role):
    _query("SELECT model_page_id FROM api_public.model_pages LIMIT 1", role=role)
    assert not _query(
        "SELECT has_table_privilege(%s,'api_public.model_pages','INSERT,UPDATE,DELETE,TRUNCATE')",
        (role,),
    )[0][0]


def test_no_new_source_grants_are_required():
    grants = set(_query("SELECT table_name,column_name FROM information_schema.column_privileges WHERE table_schema='public' AND grantee='api_public_owner'"))
    assert not {table for table, _ in grants}.intersection({"locales"})
    assert not {"scrape_status", "last_scraped_at", "created_at"}.intersection(column for _, column in grants)
    owner = _query("SELECT pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='api_public' AND c.relname='model_pages'")[0][0]
    assert owner == "api_public_owner"
    for role in ("anon", "authenticated"):
        assert not _query("SELECT pg_has_role(%s,'api_public_owner','MEMBER')", (role,))[0][0]


def test_deterministic_keyset_pagination():
    first = _query('SELECT canonical_path,model_page_id FROM api_public.model_pages ORDER BY canonical_path COLLATE "C",model_page_id LIMIT 100')
    path, page_id = first[-1]
    second = _query(
        'SELECT canonical_path,model_page_id FROM api_public.model_pages '
        'WHERE (canonical_path COLLATE "C",model_page_id)>(%s,%s) '
        'ORDER BY canonical_path COLLATE "C",model_page_id LIMIT 100',
        (path, page_id),
    )
    assert first + second == sorted(first + second)
    assert len(first + second) == len(set(first + second))


def _postgrest_get(params: dict[str, str]):
    base = os.getenv("REPAIRBASE_POSTGREST_DEV_URL")
    if not base:
        pytest.skip("explicit dev PostgREST URL not set")
    parsed = urlparse(base)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        pytest.fail("PostgREST tests require a loopback target")
    request = Request(
        base.rstrip("/") + "/model_pages?" + urlencode(params, safe=".,()*"),
        headers={"Accept-Profile": "api_public", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        pytest.fail(f"PostgREST returned HTTP {error.code}")


def test_postgrest_identity_model_locale_indexability_order_and_cap():
    status, rows = _postgrest_get({"select": "*", "locale": "eq.sv", "indexable": "eq.true", "order": "canonical_path.asc,model_page_id.asc", "limit": "3"})
    assert status == 200 and 0 < len(rows) <= 3
    assert list(rows[0]) == EXPECTED_COLUMNS
    assert not FORBIDDEN_COLUMNS.intersection(rows[0])
    assert all(row["locale"] == "sv" and row["indexable"] is True for row in rows)
    page_id, model_id = rows[0]["model_page_id"], rows[0]["model_id"]
    status, by_page = _postgrest_get({"select": "model_page_id", "model_page_id": f"eq.{page_id}"})
    assert status == 200 and by_page == [{"model_page_id": page_id}]
    status, by_model = _postgrest_get({"select": "model_id,locale", "model_id": f"eq.{model_id}"})
    assert status == 200 and len(by_model) >= 1
    status, capped = _postgrest_get({"select": "model_page_id", "limit": "1500"})
    assert status == 200 and len(capped) <= 1000
