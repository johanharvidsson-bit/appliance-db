"""The only database write boundary for PR 2B."""

from __future__ import annotations

import json
from psycopg2.extras import RealDictCursor

from workers.source_ingestion import EXTRACTOR_VERSION, PARSER_VERSION


class IngestionRepository:
    WRITABLE_TABLES = frozenset(
        {
            "worker_runs",
            "sources",
            "source_fetches",
            "source_documents",
            "candidate_facts",
            "candidate_fact_evidence",
        }
    )

    def __init__(self, connection):
        self.connection = connection

    def start_run(self, run_id, site, environment):
        with self.connection.cursor() as cur:
            cur.execute(
                """INSERT INTO worker_runs(id,worker_name,worker_version,site_id,environment,dry_run,status)
                VALUES(%s,'source-ingestion','1.0.0',%s,%s,false,'running')""",
                (run_id, site, environment),
            )

    def finish_run(self, run_id, result):
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE worker_runs SET status='completed',result_json=%s::jsonb,finished_at=now() WHERE id=%s",
                (json.dumps(result), run_id),
            )

    def lock(self, site, environment, candidate_id=None):
        key = (
            f"source-ingestion:{site}:{environment}"
            if candidate_id is None
            else f"source-ingestion:candidate:{candidate_id}"
        )
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (key,))
            return cur.fetchone()[0]

    def unlock(self, site, environment, candidate_id=None):
        key = (
            f"source-ingestion:{site}:{environment}"
            if candidate_id is None
            else f"source-ingestion:candidate:{candidate_id}"
        )
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (key,))

    def candidates(self, site, environment, *, limit, filters):
        sql = """
        SELECT sc.id AS source_candidate_id,sc.backlog_id,sc.candidate_url,sc.normalized_url,sc.source_type,
               sc.publisher,sc.title,sc.confidence,sc.entity_type,sc.entity_id,sc.locale,b.action_type,
               CASE WHEN sc.entity_type='error_code' THEN ec.code ELSE NULL END AS subject_identifier
        FROM source_candidates sc JOIN content_backlog b ON b.id=sc.backlog_id
        JOIN cube_scope_snapshots css ON css.id=b.scope_snapshot_id
        LEFT JOIN error_codes ec ON sc.entity_type='error_code'
          AND sc.entity_id~'^[0-9]+$' AND ec.id=sc.entity_id::integer
        WHERE sc.site_id=%s AND sc.environment=%s AND sc.status='accepted'
          AND b.status IN('queued','in_progress','deferred') AND css.status='active'
          AND b.site_id=sc.site_id AND b.environment=sc.environment
        """
        params = [site, environment]
        for col, key in (
            ("sc.id", "source_candidate_id"),
            ("sc.backlog_id", "backlog_id"),
            ("sc.source_type", "source_type"),
        ):
            if filters.get(key) is not None:
                sql += f" AND {col}=%s"
                params.append(filters[key])
        sql += " ORDER BY b.priority DESC,sc.id LIMIT %s"
        params.append(limit)
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(sql, params)
            return [dict(x) for x in cur.fetchall()]

    def cache_headers(self, candidate_id):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT etag,last_modified,content_hash FROM source_fetches WHERE source_candidate_id=%s AND fetch_status='fetched' ORDER BY retrieved_at DESC LIMIT 1",
                (candidate_id,),
            )
            return dict(cur.fetchone() or {})

    def record_failure(self, item, run_id, status, reason, requested_url):
        with self.connection.cursor() as cur:
            cur.execute(
                """INSERT INTO source_fetches(source_candidate_id,backlog_id,worker_run_id,requested_url,fetch_status,processing_state,failure_reason)
            VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (
                    item["source_candidate_id"],
                    item["backlog_id"],
                    run_id,
                    requested_url,
                    status,
                    "needs_manual_review"
                    if status in {"blocked", "unsupported", "invalid_content"}
                    else "fetch_pending",
                    reason,
                ),
            )
            return cur.fetchone()[0]

    def record_not_modified(self, item, run_id, result):
        with self.connection.cursor() as cur:
            cur.execute(
                """INSERT INTO source_fetches(source_candidate_id,backlog_id,worker_run_id,requested_url,final_url,http_status,
                etag,last_modified,fetch_status,processing_state,metadata_json)
                VALUES(%s,%s,%s,%s,%s,304,%s,%s,'not_modified','source_material_fetched',%s::jsonb) RETURNING id""",
                (
                    item["source_candidate_id"],
                    item["backlog_id"],
                    run_id,
                    result.requested_url,
                    result.final_url,
                    result.headers.get("etag"),
                    result.headers.get("last-modified"),
                    json.dumps({"safe_headers": result.headers}),
                ),
            )
            return cur.fetchone()[0]

    def persist(
        self,
        item,
        run_id,
        result,
        storage_reference,
        content_hash,
        document,
        facts,
        reprocess=False,
    ):
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT id FROM source_fetches WHERE source_candidate_id=%s AND content_hash=%s AND fetch_status='fetched'",
                (item["source_candidate_id"], content_hash),
            )
            existing = cur.fetchone()
            if existing and not reprocess:
                return {"deduplicated": 1, "fetch_id": existing[0], "facts": 0}
            cur.execute(
                "SELECT id FROM sources WHERE normalized_url=%s AND content_hash=%s",
                (result.final_url, content_hash),
            )
            source_row = cur.fetchone()
            if source_row:
                source_id = source_row[0]
            else:
                cur.execute(
                    """INSERT INTO sources(url,normalized_url,source_type,publisher,title,retrieved_at,content_hash)
                    VALUES(%s,%s,%s,%s,%s,now(),%s) RETURNING id""",
                    (
                        result.final_url,
                        result.final_url,
                        _source_type(item["source_type"], result.mime_type),
                        item.get("publisher"),
                        document.title or item.get("title"),
                        content_hash,
                    ),
                )
                source_id = cur.fetchone()[0]
            if existing:
                fetch_id = existing[0]
            else:
                cur.execute(
                    """INSERT INTO source_fetches(source_id,source_candidate_id,backlog_id,worker_run_id,requested_url,final_url,http_status,mime_type,content_length,etag,last_modified,fetch_status,processing_state,content_hash,metadata_json)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'fetched','source_material_fetched',%s,%s::jsonb) RETURNING id""",
                    (
                        source_id,
                        item["source_candidate_id"],
                        item["backlog_id"],
                        run_id,
                        result.requested_url,
                        result.final_url,
                        result.status_code,
                        result.mime_type,
                        len(result.body),
                        result.headers.get("etag"),
                        result.headers.get("last-modified"),
                        content_hash,
                        json.dumps({"safe_headers": result.headers}),
                    ),
                )
                fetch_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO source_documents(source_fetch_id,document_type,language,raw_storage_reference,normalized_text,normalized_text_hash,page_count,parser_name,parser_version,parse_status,metadata_json)
            VALUES(%s,%s,%s,%s,%s,%s,%s,'repairbase_deterministic',%s,'parsed',%s::jsonb)
            ON CONFLICT(source_fetch_id,parser_name,parser_version) DO UPDATE SET source_fetch_id=EXCLUDED.source_fetch_id RETURNING id""",
                (
                    fetch_id,
                    document.document_type,
                    document.language,
                    storage_reference,
                    document.text,
                    _hash(document.text),
                    document.page_count,
                    PARSER_VERSION,
                    json.dumps(document.metadata),
                ),
            )
            document_id = cur.fetchone()[0]
            inserted = 0
            for fact in facts:
                cur.execute(
                    """INSERT INTO candidate_facts(source_document_id,source_candidate_id,backlog_item_id,fact_type,subject_hint,predicate,value_json,unit,locale,confidence,extraction_status,extractor_name,extractor_version,input_hash,conflict_key,conflict_metadata)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,'repairbase_deterministic',%s,%s,%s,%s::jsonb)
                ON CONFLICT(source_document_id,extractor_name,extractor_version,input_hash) DO NOTHING RETURNING id""",
                    (
                        document_id,
                        item["source_candidate_id"],
                        item["backlog_id"],
                        fact.fact_type,
                        fact.subject_hint,
                        fact.predicate,
                        json.dumps(fact.value),
                        fact.unit,
                        fact.locale,
                        fact.confidence,
                        fact.status,
                        EXTRACTOR_VERSION,
                        fact.input_hash,
                        fact.conflict_key,
                        json.dumps(fact.conflict_metadata),
                    ),
                )
                row = cur.fetchone()
                if not row:
                    continue
                inserted += 1
                conflict_key = _hash(
                    json.dumps(
                        [
                            fact.subject_hint,
                            fact.fact_type,
                            fact.predicate,
                            fact.locale,
                            fact.value.get("step_number")
                            if fact.fact_type == "guide_step"
                            and isinstance(fact.value, dict)
                            else None,
                        ],
                        sort_keys=True,
                    )
                )
                step_number = (
                    str(fact.value.get("step_number"))
                    if fact.fact_type == "guide_step"
                    and isinstance(fact.value, dict)
                    else None
                )
                cur.execute(
                    """SELECT id FROM candidate_facts
                    WHERE id<>%s AND subject_hint IS NOT DISTINCT FROM %s AND fact_type=%s AND predicate=%s
                      AND locale IS NOT DISTINCT FROM %s AND value_json IS DISTINCT FROM %s::jsonb
                      AND (%s IS NULL OR value_json->>'step_number'=%s)
                      AND extraction_status IN('candidate','needs_review','conflicted')""",
                    (
                        row[0],
                        fact.subject_hint,
                        fact.fact_type,
                        fact.predicate,
                        fact.locale,
                        json.dumps(fact.value),
                        step_number,
                        step_number,
                    ),
                )
                conflicting_ids = [x[0] for x in cur.fetchall()]
                if conflicting_ids:
                    all_ids = conflicting_ids + [row[0]]
                    cur.execute(
                        """UPDATE candidate_facts SET extraction_status='conflicted',conflict_key=%s,
                        conflict_metadata=%s::jsonb,updated_at=now() WHERE id=ANY(%s)""",
                        (
                            conflict_key,
                            json.dumps(
                                {
                                    "reason": "different_values_same_subject_predicate",
                                    "candidate_count": len(all_ids),
                                }
                            ),
                            all_ids,
                        ),
                    )
                cur.execute(
                    """INSERT INTO candidate_fact_evidence(candidate_fact_id,source_document_id,source_locator,quoted_excerpt,page_number,section_heading,json_path)
                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        row[0],
                        document_id,
                        fact.locator,
                        fact.excerpt,
                        fact.page,
                        fact.heading,
                        fact.json_path,
                    ),
                )
            state = "needs_entity_resolution" if inserted else "needs_manual_review"
            cur.execute(
                "UPDATE source_fetches SET processing_state=%s WHERE id=%s",
                (state, fetch_id),
            )
            return {"deduplicated": 0, "fetch_id": fetch_id, "facts": inserted}


def _hash(text):
    from hashlib import sha256

    return sha256(text.encode()).hexdigest()


def _source_type(candidate_type, mime):
    if mime == "application/pdf":
        return "service_document" if candidate_type == "service_manual" else "manual"
    return "website" if mime == "text/html" else "other"
