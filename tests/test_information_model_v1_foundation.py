"""Contract and isolated-dev integration tests for migration 016."""

from datetime import datetime, timezone
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import psycopg2
import pytest


MIGRATION = Path("db/migrations/016_information_model_v1_foundation.sql")
SQL = MIGRATION.read_text(encoding="utf-8").lower()
NEW_TABLES = {
    "model_variants",
    "legacy_model_mapping",
    "legacy_model_mapping_candidates",
    "model_content_translations",
    "error_code_translations",
    "guides",
    "guide_translations",
    "sources",
    "source_evidence",
    "article_guides",
    "guide_error_codes",
    "guide_faults",
    "guide_models",
    "error_code_model_overrides",
    "fault_model_overrides",
    "url_redirects",
}


def _dsn() -> str:
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value:
        pytest.skip("explicit dev integration DSN not set")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 15432:
        pytest.fail("migration 016 tests require loopback port 15432")
    if parsed.path != "/repair_appliance_dev":
        pytest.fail("migration 016 tests require repair_appliance_dev")
    return value


def _query(sql: str, params=()):
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            if cursor.description:
                return cursor.fetchall()
            return []


def _seed_scope(prefix: str) -> tuple[int, int, int, int, int]:
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO brands(name,slug) VALUES(%s,%s) "
                "ON CONFLICT(slug) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                (prefix, prefix),
            )
            brand_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO categories(slug_en) VALUES(%s) "
                "ON CONFLICT(slug_en) DO UPDATE SET slug_en=EXCLUDED.slug_en RETURNING id",
                (prefix,),
            )
            category_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO models(brand_id,category_id,name,slug) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT(brand_id,category_id,slug) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                (brand_id, category_id, prefix, prefix),
            )
            model_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO error_codes(brand_id,category_id,code) VALUES(%s,%s,%s) "
                "ON CONFLICT(brand_id,category_id,code) DO UPDATE SET code=EXCLUDED.code RETURNING id",
                (brand_id, category_id, prefix.upper()),
            )
            error_code_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO faults(brand_id,category_id,slug,canonical_name) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT(brand_id,category_id,slug) DO UPDATE SET canonical_name=EXCLUDED.canonical_name RETURNING id",
                (brand_id, category_id, prefix, prefix),
            )
            fault_id = cursor.fetchone()[0]
    return brand_id, category_id, model_id, error_code_id, fault_id


def test_migration_is_transactional_and_contains_no_business_backfill():
    assert SQL.startswith("-- migration 016")
    assert "begin;" in SQL and SQL.rstrip().endswith("commit;")
    assert "insert into public.schema_migrations" in SQL
    for table in NEW_TABLES:
        assert f"create table public.{table}" in SQL
    assert "insert into public.model_variants" not in SQL
    assert "insert into public.guides" not in SQL
    assert "insert into public.legacy_model_mapping" not in SQL


def test_all_new_tables_exist_with_forced_rls_and_no_public_privileges():
    rows = _query(
        "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname=ANY(%s) ORDER BY c.relname",
        (list(NEW_TABLES),),
    )
    assert {row[0] for row in rows} == NEW_TABLES
    assert all(row[1:] == (True, True) for row in rows)
    for table in NEW_TABLES:
        assert _query(
            "SELECT has_table_privilege('anon',%s,'SELECT,INSERT,UPDATE,DELETE'),"
            "has_table_privilege('authenticated',%s,'SELECT,INSERT,UPDATE,DELETE'),"
            "has_table_privilege('service_role',%s,'SELECT,INSERT,UPDATE'),"
            "has_table_privilege('service_role',%s,'DELETE')",
            (table, table, table, table),
        )[0] == (False, False, True, False)


def test_retained_table_changes_and_no_backfill():
    product_columns = {row[0] for row in _query(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='product_codes'"
    )}
    assert {"model_variant_id", "normalized_code"} <= product_columns
    fault_columns = {row[0] for row in _query(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='fault_translations'"
    )}
    assert {"publication_status", "source_hash", "reviewed_at", "updated_at"} <= fault_columns


def test_updated_at_is_server_authoritative():
    _, _, model_id, _, _ = _seed_scope("v1-updated-at")
    code = f"A-{uuid4().hex}"
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO model_variants(model_id,variant_code,normalized_variant_code,updated_at) "
                "VALUES(%s,%s,%s,'2000-01-01') RETURNING id,updated_at",
                (model_id, code, code),
            )
            variant_id, before = cursor.fetchone()
            cursor.execute(
                "UPDATE model_variants SET description='changed',updated_at='2001-01-01' "
                "WHERE id=%s RETURNING updated_at",
                (variant_id,),
            )
            after = cursor.fetchone()[0]
            assert before.year == 2000
            assert after.year >= 2026


def test_cross_scope_relations_are_rejected_at_commit():
    _, category_a, model_a, _, _ = _seed_scope("v1-scope-a")
    brand_b, _, model_b, error_b, _ = _seed_scope("v1-scope-b")
    with pytest.raises(psycopg2.errors.RaiseException):
        with psycopg2.connect(_dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO legacy_model_mapping(legacy_model_id,canonical_model_id,mapping_status,mapping_reason,confidence) "
                    "VALUES(%s,%s,'mapped_to_main','test',100)",
                    (model_a, model_b),
                )
    with pytest.raises(psycopg2.errors.RaiseException):
        with psycopg2.connect(_dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO error_code_model_overrides(model_id,error_code_id,applicability,confidence) "
                    "VALUES(%s,%s,'applies',50)",
                    (model_a, error_b),
                )
    with pytest.raises(psycopg2.errors.RaiseException):
        with psycopg2.connect(_dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO guides(category_id,brand_id,canonical_title) VALUES(%s,%s,'scope test') RETURNING id",
                    (category_a, brand_b),
                )
                guide_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO guide_models(guide_id,model_id,applicability,confidence) VALUES(%s,%s,'applies',50)",
                    (guide_id, model_a),
                )


def test_variant_relations_must_match_their_model():
    brand_id, category_id, model_a, _, _ = _seed_scope("v1-variant-a")
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO models(brand_id,category_id,name,slug) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT(brand_id,category_id,slug) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                (brand_id, category_id, "v1 variant sibling", "v1-variant-sibling"),
            )
            sibling_model_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO model_variants(model_id,variant_code,normalized_variant_code) "
                "VALUES(%s,%s,%s) RETURNING id",
                (sibling_model_id, uuid4().hex, uuid4().hex),
            )
            variant_id = cursor.fetchone()[0]
    with pytest.raises(psycopg2.errors.RaiseException):
        with psycopg2.connect(_dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO product_codes(model_id,code,model_variant_id) VALUES(%s,%s,%s)",
                    (model_a, f"PC-{uuid4().hex}", variant_id),
                )
    with pytest.raises(psycopg2.errors.RaiseException):
        with psycopg2.connect(_dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO legacy_model_mapping(legacy_model_id,canonical_model_id,model_variant_id,mapping_status,mapping_reason,confidence) "
                    "VALUES(%s,%s,%s,'mapped_to_variant','test',100)",
                    (sibling_model_id, model_a, variant_id),
                )


def test_published_guides_need_topic_and_published_translation_needs_steps():
    brand_id, category_id, _, error_code_id, _ = _seed_scope("v1-guide")
    with pytest.raises(psycopg2.errors.RaiseException):
        with psycopg2.connect(_dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO guides(category_id,brand_id,canonical_title,content_status) "
                    "VALUES(%s,%s,'invalid published','published')",
                    (category_id, brand_id),
                )
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO guides(category_id,brand_id,canonical_title) VALUES(%s,%s,'valid published') RETURNING id",
                (category_id, brand_id),
            )
            guide_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO guide_error_codes(guide_id,error_code_id,relation_status,confidence) "
                "VALUES(%s,%s,'verified',100)",
                (guide_id, error_code_id),
            )
            cursor.execute("UPDATE guides SET content_status='published' WHERE id=%s", (guide_id,))
    with pytest.raises(psycopg2.errors.CheckViolation):
        _query(
            "INSERT INTO guide_translations(guide_id,locale,slug,title,publication_status) "
            "VALUES(%s,'en','empty-steps','Empty','published')",
            (guide_id,),
        )


def test_source_evidence_is_fk_safe_and_referenced_source_is_immutable():
    _, _, model_id, _, _ = _seed_scope("v1-source")
    token = uuid4().hex
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO sources(url,normalized_url,source_type,retrieved_at,content_hash) "
                "VALUES(%s,%s,'manual',%s,%s) RETURNING id",
                (f"https://example.invalid/{token}", f"https://example.invalid/{token}/", datetime.now(timezone.utc), token),
            )
            source_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO source_evidence(source_id,model_id,field_name,source_locator,observed_value,confidence,observed_at) "
                "VALUES(%s,%s,'name','page:1','\"observed\"'::jsonb,90,%s) RETURNING target_key",
                (source_id, model_id, datetime.now(timezone.utc)),
            )
            assert cursor.fetchone()[0] == f"model:{model_id}"
    with pytest.raises(psycopg2.errors.RaiseException):
        _query("UPDATE sources SET title='changed' WHERE id=%s", (source_id,))


def test_url_bindings_support_new_entities_and_redirects_fail_closed():
    _, _, model_id, _, _ = _seed_scope("v1-url")
    token = uuid4().hex
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO model_variants(model_id,variant_code,normalized_variant_code) VALUES(%s,%s,%s) RETURNING id",
                (model_id, token, token),
            )
            variant_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO url_registry(environment,url,normalized_url,path,page_type,first_observed_at,last_observed_at) "
                "VALUES('development',%s,%s,%s,'model_variant',now(),now()) RETURNING id",
                (f"http://127.0.0.1/{token}-source/", f"http://127.0.0.1/{token}-source/", f"/{token}-source/"),
            )
            source_url_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO entity_url_bindings(url_id,model_variant_id,binding_role,valid_from) VALUES(%s,%s,'primary',now()) RETURNING entity_key",
                (source_url_id, variant_id),
            )
            assert cursor.fetchone()[0] == f"model_variant:{variant_id}"
            cursor.execute(
                "INSERT INTO url_registry(environment,url,normalized_url,path,page_type,http_status,canonical_url,first_observed_at,last_observed_at) "
                "VALUES('development',%s,%s,%s,'model',200,%s,now(),now()) RETURNING id",
                (f"http://127.0.0.1/{token}-destination/", f"http://127.0.0.1/{token}-destination/", f"/{token}-destination/", f"http://127.0.0.1/{token}-destination/"),
            )
            destination_url_id = cursor.fetchone()[0]
    with pytest.raises(psycopg2.errors.RaiseException):
        _query(
            "INSERT INTO url_redirects(source_url_id,destination_url_id,approval_status,reason,migration_batch_id,approved_at,approved_by,activated_at) "
            "VALUES(%s,%s,'activated','test','batch',now(),'tester',now())",
            (source_url_id, destination_url_id),
        )
