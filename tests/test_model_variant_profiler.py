import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlparse

import psycopg2
import pytest

from pipeline.model_variant_profiler import (
    ModelRecord,
    load_records,
    normalize_model_code,
    persist_candidates,
    profile_models,
)


FIXTURES = Path("tests/fixtures")


def _dsn() -> str:
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value:
        pytest.skip("explicit dev integration DSN not set")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 15432:
        pytest.fail("profiler persistence tests require loopback port 15432")
    if parsed.path != "/repair_appliance_dev":
        pytest.fail("profiler persistence tests require repair_appliance_dev")
    return value


def test_shared_normalization_fixtures():
    fixtures = json.loads((FIXTURES / "model_code_normalization.json").read_text(encoding="utf-8"))
    assert fixtures
    for fixture in fixtures:
        assert normalize_model_code(fixture["input"]) == fixture["normalized"]


def test_javascript_uses_the_same_normalization_fixtures():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    result = subprocess.run(
        [node, "tests/verify_model_normalization.mjs", str(FIXTURES / "model_code_normalization.json")],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == {"verified": 4}


def test_pilot_is_deterministic_and_conservative():
    records = load_records(FIXTURES / "model_variant_pilot.json")
    first = profile_models(records)
    second = profile_models(list(reversed(records)))
    assert first == second
    assert first.records == 6
    decisions = {decision.legacy_model_id: decision for decision in first.decisions}
    assert decisions[1001].recommended_status == "unchanged"
    assert decisions[1002].recommended_status == "mapped_to_variant"
    assert decisions[1002].normalized_candidate_variant_code == "EN"
    assert decisions[1003].normalized_candidate_variant_code == "US"
    assert decisions[1004].recommended_status == "unchanged"
    assert decisions[1004].review_classification == "manual_review"
    assert decisions[1006].review_classification == "retain_200"
    assert len(first.stop_gates) == 1
    assert all(candidate.legacy_model_id in {1002, 1003, 1004, 1005} for candidate in first.candidates)


def test_profiler_rejects_mixed_scope_and_duplicate_identity():
    base = ModelRecord(1, 1, 1, "A", "a")
    with pytest.raises(ValueError, match="one brand/category"):
        profile_models([base, ModelRecord(2, 1, 2, "B", "b")])
    with pytest.raises(ValueError, match="duplicate legacy"):
        profile_models([base, ModelRecord(1, 1, 1, "A/EN", "a-en")])


def _seed_pilot() -> list[ModelRecord]:
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO brands(name,slug) VALUES('Profiler Pilot','profiler-pilot') "
                "ON CONFLICT(slug) DO UPDATE SET name=EXCLUDED.name RETURNING id"
            )
            brand_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO categories(slug_en) VALUES('profiler-pilot') "
                "ON CONFLICT(slug_en) DO UPDATE SET slug_en=EXCLUDED.slug_en RETURNING id"
            )
            category_id = cursor.fetchone()[0]
            rows = []
            for name, slug, base_model in (
                ("PX100", "px100", "PX100"),
                ("PX100/EN", "px100-en", "PX100"),
                ("PX100/US", "px100-us", "PX100"),
            ):
                cursor.execute(
                    "INSERT INTO models(brand_id,category_id,name,slug,base_model) VALUES(%s,%s,%s,%s,%s) "
                    "ON CONFLICT(brand_id,category_id,slug) DO UPDATE SET name=EXCLUDED.name,base_model=EXCLUDED.base_model "
                    "RETURNING id,brand_id,category_id,name,slug,base_model",
                    (brand_id, category_id, name, slug, base_model),
                )
                rows.append(ModelRecord(*cursor.fetchone()))
            return rows


def test_candidate_persistence_is_guarded_idempotent_and_non_authoritative():
    report = profile_models(_seed_pilot())
    first = persist_candidates(report, dsn=_dsn(), environment="development")
    second = persist_candidates(report, dsn=_dsn(), environment="development")
    assert len(first["created_variant_ids"]) in {0, 2}
    assert len(first["created_candidate_ids"]) in {0, 2}
    assert second["created_variant_ids"] == []
    assert second["created_candidate_ids"] == []
    assert second["authoritative_mappings_written"] == 0
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*),bool_and(status='candidate') FROM model_variants v "
                "JOIN models m ON m.id=v.model_id JOIN brands b ON b.id=m.brand_id "
                "WHERE b.slug='profiler-pilot'"
            )
            assert cursor.fetchone() == (2, True)
            cursor.execute(
                "SELECT count(*),bool_and(candidate_status='candidate') "
                "FROM legacy_model_mapping_candidates c JOIN models m ON m.id=c.legacy_model_id "
                "JOIN brands b ON b.id=m.brand_id WHERE b.slug='profiler-pilot'"
            )
            assert cursor.fetchone() == (2, True)
            cursor.execute(
                "SELECT count(*) FROM legacy_model_mapping l JOIN models m ON m.id=l.legacy_model_id "
                "JOIN brands b ON b.id=m.brand_id WHERE b.slug='profiler-pilot'"
            )
            assert cursor.fetchone()[0] == 0


def test_candidate_persistence_rejects_production():
    report = profile_models(_seed_pilot())
    with pytest.raises(ValueError, match="restricted to development"):
        persist_candidates(report, dsn=_dsn(), environment="production")
