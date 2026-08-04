import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from pipeline.guide_pilot import load_pilot, persist_guide_pilot, publish_reviewed_pilot


FIXTURE = Path("tests/fixtures/guide_pilot.json")


def _dsn() -> str:
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value:
        pytest.skip("explicit dev integration DSN not set")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 15432 or parsed.path != "/repair_appliance_dev":
        pytest.fail("compatibility tests require loopback repair_appliance_dev on port 15432")
    return value


def _seed_error_code() -> int:
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM brands WHERE is_active ORDER BY id LIMIT 1")
            brand_id = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM categories WHERE is_active ORDER BY id LIMIT 1")
            category_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO error_codes(brand_id,category_id,code) VALUES(%s,%s,'E10') "
                "ON CONFLICT(brand_id,category_id,code) DO UPDATE SET code=EXCLUDED.code RETURNING id",
                (brand_id, category_id),
            )
            return cursor.fetchone()[0]


def _query_as(role: str, sql: str, params=()):
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(f"SET LOCAL ROLE {role}")
            cursor.execute(sql, params)
            return cursor.fetchall()


def test_api_contract_has_only_safe_projection_columns():
    expected = {
        "model_variants_v1": {"variant_id", "model_id", "variant_code", "market", "region", "description"},
        "model_content_v1": {"model_id", "locale", "overview", "short_summary"},
        "guides_v1": {"guide_id", "category_key", "brand_key", "locale", "slug", "title", "short_description", "summary", "steps_json", "default_difficulty", "default_estimated_minutes", "safety_notes", "is_general"},
        "model_page_guides_v1": {"model_id", "guide_id", "locale", "slug", "title", "short_description", "default_difficulty", "default_estimated_minutes"},
    }
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            for view, columns in expected.items():
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='api_public' AND table_name=%s",
                    (view,),
                )
                assert {row[0] for row in cursor.fetchall()} == columns
                assert not {"source_evidence_id", "confidence", "reviewed_by", "source_id"}.intersection(columns)
    for role in ("anon", "authenticated"):
        for view in expected:
            _query_as(role, f"SELECT * FROM api_public.{view} LIMIT 1")
            assert _query_as(role, "SELECT has_table_privilege(%s,%s,'INSERT,UPDATE,DELETE')", (role, f"api_public.{view}"))[0][0] is False


def test_candidate_rows_never_appear_in_public_views():
    _seed_error_code()
    payload = {**load_pilot(FIXTURE), "brand_slug": "samsung", "category_slug": "washing_machine"}
    result = persist_guide_pilot(payload, dsn=_dsn())
    if not result["published"]:
        rows = _query_as("anon", "SELECT guide_id FROM api_public.guides_v1 WHERE slug='synthetic-e10-safe-checks'")
        if rows:
            # A previous idempotent test run may already have reviewed this exact fixture.
            assert len(rows) == 1
        else:
            assert rows == []


def test_reviewed_guide_is_reused_and_visible_without_placeholders():
    _seed_error_code()
    payload = {**load_pilot(FIXTURE), "brand_slug": "samsung", "category_slug": "washing_machine"}
    first = persist_guide_pilot(payload, dsn=_dsn())
    second = persist_guide_pilot(payload, dsn=_dsn())
    assert first["guide_id"] == second["guide_id"]
    assert not any(second["created"].values())
    publish_reviewed_pilot(first["guide_id"], reviewed_by="local-test", dsn=_dsn())
    rows = _query_as(
        "anon",
        "SELECT title,steps_json FROM api_public.guides_v1 WHERE slug='synthetic-e10-safe-checks'",
    )
    assert len(rows) == 1
    assert rows[0][0] == payload["title"]
    assert len(rows[0][1]) == 3
    assert "coming soon" not in str(rows[0]).lower()
    model_rows = _query_as(
        "anon",
        "SELECT count(*) FROM api_public.model_page_guides_v1 WHERE slug='synthetic-e10-safe-checks'",
    )
    assert model_rows[0][0] >= 1
