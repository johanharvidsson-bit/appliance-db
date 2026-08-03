"""Guarded local registration and publication helpers for a new site."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.parse import urlparse

import psycopg2

from config.site_contract import validate_site_contract
from config.target_safety import assert_safe_target


class SitePlatform:
    def __init__(self, dsn: str, *, environment: str = "development"):
        if environment != "development":
            raise ValueError("site platform writes are restricted to development")
        assert_safe_target(dsn, app_env=environment, operation="write")
        self.dsn = dsn
        self.environment = environment

    def register(self, contract: dict, *, activate: bool = False) -> str:
        contract = validate_site_contract(contract)
        status = "active" if activate else "draft"
        with psycopg2.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sites(id,name,domain,vertical_key,default_locale,status,contract_json) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET "
                    "name=EXCLUDED.name,domain=EXCLUDED.domain,vertical_key=EXCLUDED.vertical_key,"
                    "default_locale=EXCLUDED.default_locale,contract_json=EXCLUDED.contract_json,"
                    "status=CASE WHEN %s THEN 'active' ELSE sites.status END "
                    "RETURNING id",
                    (contract["site_id"], contract["name"], contract["domain"], contract["vertical_key"], contract["default_locale"], status, json.dumps(contract), activate),
                )
                site_id = cursor.fetchone()[0]
                for locale in contract["locales"]:
                    cursor.execute(
                        "INSERT INTO site_locales(site_id,locale,is_default,status) VALUES(%s,%s,%s,'active') "
                        "ON CONFLICT(site_id,locale) DO UPDATE SET is_default=EXCLUDED.is_default,status='active'",
                        (site_id, locale, locale == contract["default_locale"]),
                    )
                return site_id

    def publish_model(self, *, site_id: str, locale: str, model_id: int, normalized_url: str, path: str, reviewed_by: str, indexable: bool = True) -> dict:
        if not reviewed_by.strip():
            raise ValueError("reviewed_by is required")
        parsed_url = urlparse(normalized_url)
        if parsed_url.hostname not in {"127.0.0.1", "localhost"} or parsed_url.port != 18080:
            raise ValueError("development publication URL must use loopback port 18080")
        now = datetime.now(timezone.utc)
        with psycopg2.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT status FROM sites WHERE id=%s", (site_id,))
                site = cursor.fetchone()
                if not site or site[0] != "active":
                    raise ValueError("site must be active before publication")
                cursor.execute(
                    "INSERT INTO url_registry(site_id,environment,url,normalized_url,path,page_type,http_status,canonical_url,classification,first_observed_at,last_observed_at) "
                    "VALUES(%s,'development',%s,%s,%s,'model',200,%s,'retain_200_with_new_data_model',%s,%s) "
                    "ON CONFLICT(site_id,environment,normalized_url) DO UPDATE SET http_status=200,canonical_url=EXCLUDED.canonical_url,last_observed_at=EXCLUDED.last_observed_at "
                    "RETURNING id",
                    (site_id, normalized_url, normalized_url, path, normalized_url, now, now),
                )
                url_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO site_entity_publications(site_id,locale,model_id,publication_status,canonical_url_id,indexable,published_at,reviewed_at,reviewed_by) "
                    "VALUES(%s,%s,%s,'published',%s,%s,%s,%s,%s) ON CONFLICT(site_id,locale,entity_key) DO UPDATE SET "
                    "publication_status='published',canonical_url_id=EXCLUDED.canonical_url_id,indexable=EXCLUDED.indexable,"
                    "published_at=EXCLUDED.published_at,reviewed_at=EXCLUDED.reviewed_at,reviewed_by=EXCLUDED.reviewed_by RETURNING id",
                    (site_id, locale, model_id, url_id, indexable, now, now, reviewed_by),
                )
                publication_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO entity_url_bindings(url_id,model_id,binding_role,mapping_status,valid_from) "
                    "VALUES(%s,%s,'primary','verified',%s) ON CONFLICT(url_id,entity_key) "
                    "WHERE valid_to IS NULL AND mapping_status IN('candidate','verified') DO UPDATE SET mapping_status='verified'",
                    (url_id, model_id, now),
                )
                return {"site_id": site_id, "publication_id": publication_id, "url_id": url_id, "model_id": model_id}
