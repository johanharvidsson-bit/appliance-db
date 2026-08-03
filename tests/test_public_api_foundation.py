"""Dev-only contract tests for migration 012.

Skipped unless REPAIRBASE_SECURITY_TEST_DB_URL explicitly names the loopback
repair_appliance_dev database. No credential or DSN is included in failures.
"""

import os
from urllib.parse import urlparse

import psycopg2
import pytest


EXPECTED_COLUMNS = {
    "brands": ["brand_key", "slug", "name", "logo_url", "canonical_path", "updated_at"],
    "category_pages": ["category_key", "locale", "slug", "name", "icon_key", "sort_order", "canonical_path", "indexable", "updated_at"],
    "model_pages": ["model_page_id", "model_id", "brand_key", "category_key", "locale", "category_slug", "model_slug", "canonical_path", "hreflang", "indexable", "published_at", "updated_at"],
    "models": ["model_id", "brand_key", "category_key", "product_line_key", "name", "slug", "series", "release_year", "manual_url", "indexable", "updated_at"],
    "sitemap_entries": ["sitemap_entry_id", "content_type", "public_content_id", "locale", "canonical_path", "updated_at", "indexable", "hreflang", "projection_revision"],
}
EXPECTED_TYPES = {
    "brands": ["text", "text", "text", "text", "text", "timestamp with time zone"],
    "category_pages": ["text", "text", "text", "text", "text", "integer", "text", "boolean", "timestamp with time zone"],
    "model_pages": ["uuid", "uuid", "text", "text", "text", "text", "text", "text", "jsonb", "boolean", "timestamp with time zone", "timestamp with time zone"],
    "models": ["uuid", "text", "text", "text", "text", "text", "text", "integer", "text", "boolean", "timestamp with time zone"],
    "sitemap_entries": ["uuid", "text", "text", "text", "text", "timestamp with time zone", "boolean", "jsonb", "uuid"],
}


def _dsn() -> str:
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value:
        pytest.skip("explicit dev integration DSN not set")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.path != "/repair_appliance_dev":
        pytest.fail("tests require loopback repair_appliance_dev")
    return value


def _query(sql: str, params=(), role: str | None = None):
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            if role:
                cursor.execute(f"SET LOCAL ROLE {role}")
            cursor.execute(sql, params)
            return cursor.fetchall()


def test_exact_foundation_resources_and_columns():
    resources = _query("SELECT table_name FROM information_schema.views WHERE table_schema='api_public' UNION ALL SELECT matviewname FROM pg_matviews WHERE schemaname='api_public' ORDER BY 1")
    assert resources == [(resource,) for resource in sorted(EXPECTED_COLUMNS)]
    for resource, expected in EXPECTED_COLUMNS.items():
        columns = _query("SELECT a.attname,format_type(a.atttypid,a.atttypmod) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='api_public' AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum", (resource,))
        assert [row[0] for row in columns] == expected
        assert [row[1] for row in columns] == EXPECTED_TYPES[resource]


@pytest.mark.parametrize("role", ["anon", "authenticated"])
@pytest.mark.parametrize("resource", EXPECTED_COLUMNS)
def test_public_roles_can_read_only_approved_resources(role, resource):
    _query(f"SELECT 1 FROM api_public.{resource} LIMIT 1", role=role)
    assert not _query("SELECT has_table_privilege(%s, %s, 'INSERT,UPDATE,DELETE,TRUNCATE')", (role, f"api_public.{resource}"))[0][0]


@pytest.mark.parametrize("role", ["anon", "authenticated", "api_public_owner"])
def test_roles_cannot_create_in_public_api_schema(role):
    assert not _query("SELECT has_schema_privilege(%s, 'api_public', 'CREATE')", (role,))[0][0]


def test_owner_is_constrained_and_separate_from_sources():
    attrs = _query("SELECT rolsuper,rolcreatedb,rolcreaterole,rolcanlogin,rolbypassrls FROM pg_roles WHERE rolname='api_public_owner'")[0]
    assert attrs == (False, False, False, False, False)
    owners = _query("SELECT DISTINCT pg_get_userbyid(relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('brands','categories','category_translations','models')")
    assert owners == [("postgres",)]
    assert _query("SELECT pg_get_userbyid(relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='api_public' ORDER BY c.relname")


def test_owner_has_only_expected_source_columns_and_no_public_functions():
    grants = set(_query("SELECT table_name,column_name FROM information_schema.column_privileges WHERE table_schema='public' AND grantee='api_public_owner'"))
    expected = {
        *(('api_public_identities', c) for c in ('resource_type', 'source_id', 'public_key', 'public_id')),
        *(('brands', c) for c in ('id', 'name', 'slug', 'logo_url', 'is_active')),
        *(('models', c) for c in ('id', 'brand_id', 'category_id', 'product_line_id', 'name', 'slug', 'series', 'release_year')),
        *(('categories', c) for c in ('id', 'sort_order', 'is_active')),
        *(('category_translations', c) for c in ('category_id', 'locale', 'name', 'slug')),
        *(('product_lines', c) for c in ('id', 'brand_id', 'category_id', 'slug')),
    }
    assert grants == expected
    assert _query("SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='api_public'") == []


def test_publication_locale_and_field_allowlist():
    assert _query("SELECT count(*) FROM api_public.brands")[0][0] == 5
    assert _query("SELECT count(*) FROM api_public.category_pages")[0][0] == 14
    assert _query("SELECT count(*) FROM api_public.category_pages WHERE locale NOT IN ('en','sv') OR slug='' OR name=''")[0][0] == 0
    forbidden = {"id", "source_id", "brand_id", "category_id", "product_line_id", "scrape_status", "support_url", "manual_base_url", "icon_url", "created_at"}
    assert not forbidden.intersection({c for cols in EXPECTED_COLUMNS.values() for c in cols})


def test_paths_hreflang_and_snapshot_revision():
    assert _query("SELECT count(*) FROM api_public.sitemap_entries")[0][0] == 24
    assert _query("SELECT count(*) FROM api_public.sitemap_entries WHERE NOT indexable OR canonical_path !~ '^/[^?#]*$'")[0][0] == 0
    assert _query("SELECT count(*) FROM api_public.sitemap_entries GROUP BY sitemap_entry_id HAVING count(*)>1") == []
    assert _query("SELECT count(DISTINCT projection_revision) FROM api_public.sitemap_entries")[0][0] == 1
    assert _query("SELECT count(*) FROM api_public.sitemap_entries WHERE NOT (hreflang ? locale)")[0][0] == 0


def test_keyset_scans_are_complete_without_duplicates():
    specifications = [
        ("api_public.brands", "name COLLATE \"C\", brand_key", 5),
        ("api_public.category_pages", "sort_order, category_key, locale COLLATE \"C\"", 14),
        ("api_public.sitemap_entries", "canonical_path COLLATE \"C\", locale COLLATE \"C\", sitemap_entry_id", 24),
    ]
    for relation, order, expected in specifications:
        rows = _query(f"SELECT * FROM {relation} ORDER BY {order}")
        assert len(rows) == expected
        assert len({repr(row) for row in rows}) == expected


def test_keyset_boundary_behavior_with_concurrent_shape_changes():
    original = [("alpha", "a"), ("beta", "b"), ("beta", "c"), ("delta", "d")]
    first_page = original[:2]
    cursor = first_page[-1]
    changed = [("aardvark", "z"), *original[:-1], ("gamma", "g")]
    second_page = [row for row in changed if row > cursor]
    assert first_page + second_page == [("alpha", "a"), ("beta", "b"), ("beta", "c"), ("gamma", "g")]
    assert len(set(first_page + second_page)) == len(first_page + second_page)


def test_actual_keyset_pages_cover_fixed_revision_without_duplicates():
    first = _query('SELECT canonical_path,locale,sitemap_entry_id,projection_revision FROM api_public.sitemap_entries ORDER BY canonical_path COLLATE "C",locale COLLATE "C",sitemap_entry_id LIMIT 10')
    path, locale, entry_id, revision = first[-1]
    second = _query('SELECT canonical_path,locale,sitemap_entry_id,projection_revision FROM api_public.sitemap_entries WHERE projection_revision=%s AND (canonical_path COLLATE "C",locale COLLATE "C",sitemap_entry_id)>(%s,%s,%s) ORDER BY canonical_path COLLATE "C",locale COLLATE "C",sitemap_entry_id', (revision, path, locale, entry_id))
    combined = first + second
    assert len(combined) == 24
    assert len({row[2] for row in combined}) == 24
    assert {row[3] for row in combined} == {revision}


def test_migration_011_denials_remain():
    for role in ("anon", "authenticated"):
        for table in ("scrape_jobs", "schema_migrations"):
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                _query(f"SELECT 1 FROM public.{table} LIMIT 1", role=role)
