import json
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from config.site_contract import validate_site_contract
from pipeline.site_platform import SitePlatform


CONTRACT_PATH = Path("site_templates/example-next-site.json")


def _dsn() -> str:
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value:
        pytest.skip("explicit dev integration DSN not set")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 15432 or parsed.path != "/repair_appliance_dev":
        pytest.fail("multisite tests require isolated loopback dev database")
    return value


def _query_as(role: str, sql: str, params=()):
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(f"SET LOCAL ROLE {role}")
            cursor.execute(sql, params)
            return cursor.fetchall()


def test_starter_contract_is_valid_and_rejects_unsafe_shapes():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert validate_site_contract(contract) == contract
    with pytest.raises(ValueError, match="default_locale"):
        validate_site_contract({**contract, "default_locale": "de"})
    with pytest.raises(ValueError, match="invalid site_id"):
        validate_site_contract({**contract, "site_id": "Bad Site"})
    with pytest.raises(ValueError, match="routes"):
        validate_site_contract({**contract, "routes": {"model": "/{model}/"}})


def test_synthetic_site_registration_publication_and_sitemap_are_isolated():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    platform = SitePlatform(_dsn())
    assert platform.register(contract, activate=False) == contract["site_id"]
    assert platform.register(contract, activate=True) == contract["site_id"]
    assert platform.register(contract, activate=True) == contract["site_id"]
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM models ORDER BY id LIMIT 1")
            model_id = cursor.fetchone()[0]
    result = platform.publish_model(
        site_id=contract["site_id"],
        locale="en",
        model_id=model_id,
        normalized_url="http://127.0.0.1:18080/example/models/model-1/",
        path="/example/models/model-1/",
        reviewed_by="multisite-test",
    )
    repeat = platform.publish_model(
        site_id=contract["site_id"],
        locale="en",
        model_id=model_id,
        normalized_url="http://127.0.0.1:18080/example/models/model-1/",
        path="/example/models/model-1/",
        reviewed_by="multisite-test",
    )
    assert repeat["publication_id"] == result["publication_id"]
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT public_id FROM api_public_identities WHERE resource_type='model' AND source_id=%s", (model_id,))
            public_model_id = cursor.fetchone()[0]
    rows = _query_as("anon", "SELECT site_id,canonical_path,indexable FROM api_public.site_models_v1 WHERE model_id=%s", (public_model_id,))
    assert (contract["site_id"], "/example/models/model-1/", True) in rows
    assert not any(row[0] == "appliance-repair-base" for row in rows)
    sitemap = _query_as("anon", "SELECT site_id,canonical_path FROM api_public.site_sitemap_entries_v1")
    assert (contract["site_id"], "/example/models/model-1/") in sitemap
    assert not any(site == "appliance-repair-base" and path == "/example/models/model-1/" for site, path in sitemap)


def test_cross_site_canonical_is_rejected_and_tables_are_internal():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    SitePlatform(_dsn()).register(contract, activate=True)
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM models ORDER BY id LIMIT 1")
            model_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO url_registry(site_id,environment,url,normalized_url,path,page_type,http_status,canonical_url,first_observed_at,last_observed_at) "
                "VALUES('appliance-repair-base','development','http://127.0.0.1:18080/wrong/','http://127.0.0.1:18080/wrong/','/wrong/','model',200,'http://127.0.0.1:18080/wrong/',now(),now()) "
                "ON CONFLICT(site_id,environment,normalized_url) DO UPDATE SET http_status=200 RETURNING id"
            )
            wrong_url_id = cursor.fetchone()[0]
    with pytest.raises(psycopg2.errors.RaiseException, match="another site"):
        with psycopg2.connect(_dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO site_entity_publications(site_id,locale,model_id,publication_status,canonical_url_id,indexable,published_at,reviewed_at,reviewed_by) "
                    "VALUES(%s,'en',%s,'published',%s,true,now(),now(),'test') "
                    "ON CONFLICT(site_id,locale,entity_key) DO UPDATE SET canonical_url_id=EXCLUDED.canonical_url_id",
                    (contract["site_id"], model_id, wrong_url_id),
                )
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            for table in ("sites", "site_locales", "site_entity_publications"):
                cursor.execute("SELECT has_table_privilege('anon',%s,'SELECT,INSERT,UPDATE,DELETE')", (table,))
                assert cursor.fetchone()[0] is False
                cursor.execute("SELECT has_table_privilege('service_role',%s,'DELETE')", (table,))
                assert cursor.fetchone()[0] is False


def test_site_platform_rejects_production():
    with pytest.raises(ValueError, match="restricted to development"):
        SitePlatform(_dsn(), environment="production")
