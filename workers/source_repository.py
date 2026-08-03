"""Backlog read and source-candidate persistence boundary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from urllib.parse import urlsplit

from psycopg2.extras import RealDictCursor


class SourceRepository:
    def __init__(self, connection):
        self.connection = connection

    def lock(self, site: str, environment: str) -> bool:
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (f"source-discovery:{site}:{environment}",))
            return cur.fetchone()[0]

    def unlock(self, site: str, environment: str) -> None:
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (f"source-discovery:{site}:{environment}",))

    def backlog(self, site: str, environment: str, *, limit: int, filters: dict) -> list[dict]:
        sql = """
        SELECT b.id AS backlog_id,b.entity_type,b.entity_id,b.locale,b.action_type,b.priority,b.priority_band,
               COALESCE(br.name,model_brand.name,error_brand.name,guide_brand.name) AS brand_name,
               COALESCE(m.name,e.code,f.canonical_name,g.canonical_title,b.entity_type||':'||b.entity_id) AS entity_name,
               ARRAY_REMOVE(ARRAY[br.support_url,br.manual_base_url,model_brand.support_url,model_brand.manual_base_url,
                                  error_brand.support_url,error_brand.manual_base_url,guide_brand.support_url,guide_brand.manual_base_url],NULL) AS official_urls
        FROM content_backlog b
        LEFT JOIN models m ON b.entity_type='model' AND m.id=CASE WHEN b.entity_id~'^[0-9]+$' THEN b.entity_id::integer END
        LEFT JOIN brands model_brand ON model_brand.id=m.brand_id
        LEFT JOIN error_codes e ON b.entity_type='error_code' AND e.id=CASE WHEN b.entity_id~'^[0-9]+$' THEN b.entity_id::integer END
        LEFT JOIN brands error_brand ON error_brand.id=e.brand_id
        LEFT JOIN faults f ON b.entity_type='fault' AND f.id=CASE WHEN b.entity_id~'^[0-9]+$' THEN b.entity_id::integer END
        LEFT JOIN brands br ON br.id=f.brand_id
        LEFT JOIN guides g ON b.entity_type='guide' AND g.id=CASE WHEN b.entity_id~'^[0-9]+$' THEN b.entity_id::integer END
        LEFT JOIN brands guide_brand ON guide_brand.id=g.brand_id
        WHERE b.site_id=%s AND b.environment=%s AND b.status='queued'
        """
        params: list = [site,environment]
        for column,key in (("b.locale","locale"),("b.action_type","action_type"),("b.entity_type","entity_type")):
            if filters.get(key):
                sql += f" AND {column}=%s"
                params.append(filters[key])
        sql += " ORDER BY b.priority DESC,b.id LIMIT %s"
        params.append(limit)
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(sql,params)
            rows=[]
            for raw in cur.fetchall():
                row=dict(raw)
                row["official_domains"] = sorted({urlsplit(x).hostname.lower().removeprefix("www.") for x in row.pop("official_urls",[]) if urlsplit(x).hostname})
                rows.append(row)
            return rows

    def cached(self, provider: str, query: str) -> list[dict] | None:
        digest=hashlib.sha256(query.encode()).hexdigest()
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT response_json FROM source_discovery_cache WHERE provider=%s AND query_hash=%s AND expires_at>now()",(provider,digest))
            row=cur.fetchone()
            return row["response_json"] if row else None

    def store_cache(self, provider: str, query: str, response: list[dict], *, ttl_hours: int=168) -> None:
        digest=hashlib.sha256(query.encode()).hexdigest()
        with self.connection.cursor() as cur:
            cur.execute("INSERT INTO source_discovery_cache(provider,query_hash,query_text,response_json,expires_at) VALUES(%s,%s,%s,%s::jsonb,%s) ON CONFLICT(provider,query_hash) DO UPDATE SET response_json=EXCLUDED.response_json,fetched_at=now(),expires_at=EXCLUDED.expires_at",(provider,digest,query,json.dumps(response),datetime.now(timezone.utc)+timedelta(hours=ttl_hours)))

    def persist(self, site: str, environment: str, item: dict, candidates: list[dict]) -> dict:
        created=updated=0
        with self.connection.cursor() as cur:
            if not candidates:
                cur.execute("INSERT INTO source_candidates(site_id,environment,backlog_id,entity_type,entity_id,locale,source_type,confidence,status,discovery_method,details_json) VALUES(%s,%s,%s,%s,%s,%s,'other',0,'not_found','search',%s::jsonb) ON CONFLICT(site_id,environment,backlog_id,candidate_key) DO UPDATE SET last_seen_at=now(),updated_at=now() RETURNING (xmax=0)",(site,environment,item["backlog_id"],item["entity_type"],item["entity_id"],item.get("locale"),json.dumps({"query_completed":True})))
                created += bool(cur.fetchone()[0])
            else:
                cur.execute("UPDATE source_candidates SET status='rejected',details_json=details_json||'{\"reason\":\"sources_discovered_later\"}'::jsonb,updated_at=now() WHERE site_id=%s AND environment=%s AND backlog_id=%s AND status='not_found'",(site,environment,item["backlog_id"]))
            for c in candidates:
                cur.execute("INSERT INTO source_candidates(site_id,environment,backlog_id,entity_type,entity_id,locale,source_type,candidate_url,normalized_url,publisher,title,confidence,status,discovery_method,details_json) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'candidate',%s,%s::jsonb) ON CONFLICT(site_id,environment,backlog_id,candidate_key) DO UPDATE SET source_type=CASE WHEN source_candidates.status='candidate' THEN EXCLUDED.source_type ELSE source_candidates.source_type END,publisher=CASE WHEN source_candidates.status='candidate' THEN EXCLUDED.publisher ELSE source_candidates.publisher END,title=CASE WHEN source_candidates.status='candidate' THEN EXCLUDED.title ELSE source_candidates.title END,confidence=CASE WHEN source_candidates.status='candidate' THEN EXCLUDED.confidence ELSE source_candidates.confidence END,last_seen_at=now(),updated_at=now() RETURNING (xmax=0)",(site,environment,c["backlog_id"],c["entity_type"],c["entity_id"],c["locale"],c["source_type"],c["candidate_url"],c["normalized_url"],c["publisher"],c["title"],c["confidence"],c["discovery_method"],json.dumps(c["details"])))
                was_created=bool(cur.fetchone()[0]); created+=was_created; updated+=not was_created
        return {"created":created,"updated":updated,"not_found":int(not candidates)}
