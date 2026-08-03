from datetime import datetime, timedelta, timezone
import os
from urllib.parse import urlparse

import psycopg2
import pytest

from pipeline.url_inventory import URLCandidate, inventory, persist_observations

TEST_URL = "http://127.0.0.1:18080/test-category/test-brand/test-model/"
TEST_SITE_ID = "appliance-repair-base"


def _dsn() -> str:
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value:
        pytest.skip("explicit dev integration DSN not set")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 15432:
        pytest.fail("persistence tests require loopback port 15432")
    if parsed.path != "/repair_appliance_dev":
        pytest.fail("persistence tests require repair_appliance_dev")
    return value


def _seed_model() -> int:
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO brands(name,slug) VALUES('Test Brand','test-brand') "
                "ON CONFLICT(slug) DO UPDATE SET name=EXCLUDED.name RETURNING id"
            )
            brand_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO categories(slug_en) VALUES('test-category') "
                "ON CONFLICT(slug_en) DO UPDATE SET slug_en=EXCLUDED.slug_en RETURNING id"
            )
            category_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO models(brand_id,category_id,name,slug) "
                "VALUES(%s,%s,'Test Model','test-model') "
                "ON CONFLICT(brand_id,category_id,slug) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                (brand_id, category_id),
            )
            return cursor.fetchone()[0]


def _delete_test_observation() -> None:
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM entity_url_bindings WHERE url_id IN ("
                "SELECT id FROM url_registry WHERE site_id=%s "
                "AND environment='development' AND normalized_url=%s)",
                (TEST_SITE_ID, TEST_URL),
            )
            cursor.execute(
                "DELETE FROM url_registry WHERE site_id=%s "
                "AND environment='development' AND normalized_url=%s",
                (TEST_SITE_ID, TEST_URL),
            )


def _counts() -> tuple[int, int]:
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM url_registry WHERE site_id=%s "
                "AND environment='development' AND normalized_url=%s",
                (TEST_SITE_ID, TEST_URL),
            )
            registry = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count(*) FROM entity_url_bindings b JOIN url_registry u "
                "ON u.id=b.url_id WHERE u.site_id=%s "
                "AND u.environment='development' AND u.normalized_url=%s",
                (TEST_SITE_ID, TEST_URL),
            )
            return registry, cursor.fetchone()[0]


def test_persistence_is_idempotent_and_preserves_classification():
    _delete_test_observation()
    model_id = _seed_model()
    first = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)
    candidate = URLCandidate(
        TEST_URL,
        "model",
        "model",
        model_id,
        sitemap_present=True,
        internal_incoming_links=3,
    )
    rows = inventory([candidate], environment="development", now=first)
    persist_observations(rows, dsn=_dsn(), environment="development")

    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE url_registry SET classification='retain_200', "
                "classification_reason='reviewed test' "
                "WHERE site_id=%s AND environment='development' "
                "AND normalized_url=%s",
                (TEST_SITE_ID, TEST_URL),
            )
        connection.commit()

    later = inventory([candidate], environment="development", now=first + timedelta(hours=1))
    persist_observations(later, dsn=_dsn(), environment="development")

    assert _counts() == (1, 1)
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT classification,classification_reason,first_observed_at,"
                "last_observed_at FROM url_registry WHERE site_id=%s "
                "AND environment='development' AND normalized_url=%s",
                (TEST_SITE_ID, TEST_URL),
            )
            classification, reason, observed_first, observed_last = cursor.fetchone()
            assert classification == "retain_200"
            assert reason == "reviewed test"
            assert observed_first == first
            assert observed_last == first + timedelta(hours=1)
            cursor.execute(
                "SELECT mapping_status,binding_role,model_id FROM entity_url_bindings"
                " WHERE url_id=(SELECT id FROM url_registry WHERE site_id=%s "
                "AND environment='development' AND normalized_url=%s)",
                (TEST_SITE_ID, TEST_URL),
            )
            assert cursor.fetchone() == ("candidate", "primary", model_id)


def test_persistence_rejects_non_development_environment():
    with pytest.raises(ValueError):
        persist_observations([], dsn=_dsn(), environment="production")


def test_public_roles_have_no_access_and_service_role_has_no_delete():
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            for role in ("anon", "authenticated"):
                cursor.execute(
                    "SELECT has_table_privilege(%s,'url_registry','SELECT,INSERT,UPDATE,DELETE')",
                    (role,),
                )
                assert cursor.fetchone()[0] is False
            cursor.execute("SELECT has_table_privilege('service_role','url_registry','SELECT,INSERT,UPDATE')")
            assert cursor.fetchone()[0] is True
            cursor.execute("SELECT has_table_privilege('service_role','url_registry','DELETE')")
            assert cursor.fetchone()[0] is False
