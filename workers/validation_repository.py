"""Persistence boundary for immutable content-validation observations."""

from __future__ import annotations

import json
from psycopg2.extras import RealDictCursor


class ValidationRepository:
    WRITABLE_TABLES = frozenset(
        {
            "worker_runs",
            "content_validation_runs",
            "content_validation_results",
            "content_claim_checks",
            "content_safety_findings",
            "content_duplication_findings",
            "content_drafts",  # validation_state only
            "content_backlog",  # content_validation_state only
        }
    )

    def __init__(self, connection):
        self.connection = connection

    def lock(self, site, environment, key=None):
        value = f"content-validation:{site}:{environment}:{key or 'global'}"
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (value,))
            return cur.fetchone()[0]

    def unlock(self, site, environment, key=None):
        value = f"content-validation:{site}:{environment}:{key or 'global'}"
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (value,))

    def drafts(self, site, environment, limit, filters, include_blocked=False):
        sql = """SELECT d.*, COALESCE(jsonb_agg(DISTINCT jsonb_build_object(
          'id',s.id,'section_key',s.section_key,'section_status',s.section_status,
          'content',s.content_json,'required',s.required,'evidence',(
            SELECT COALESCE(jsonb_agg(jsonb_build_object('id',e.id,'candidate_fact_id',e.candidate_fact_id,
              'source_evidence_id',e.source_evidence_id,'source_document_id',e.source_document_id,
              'entity_id',e.entity_id,'fact_type',e.fact_type,'locator',e.locator_json)),'[]'::jsonb)
            FROM content_draft_evidence e WHERE e.content_draft_section_id=s.id)))
          FILTER (WHERE s.id IS NOT NULL), '[]'::jsonb) AS draft_sections
        FROM content_drafts d LEFT JOIN content_draft_sections s ON s.content_draft_id=d.id
        WHERE d.site_id=%s AND d.environment=%s AND d.status<>'superseded'"""
        params = [site, environment]
        if not include_blocked:
            sql += " AND d.status IN('assembled','partial')"
        for column, key in (
            ("d.id", "draft_id"),
            ("d.backlog_item_id", "backlog_id"),
            ("d.entity_type", "entity_type"),
            ("d.locale", "locale"),
            ("d.draft_type", "draft_type"),
            ("d.risk_level", "risk_level"),
        ):
            if filters.get(key) is not None:
                sql += f" AND {column}=%s"
                params.append(filters[key])
        sql += " GROUP BY d.id ORDER BY d.created_at,d.id LIMIT %s"
        params.append(limit)
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(sql, params)
            rows = [dict(row) for row in cur.fetchall()]
        for row in rows:
            row["sections"] = row.pop("draft_sections")
            row["rendered_content"] = {
                section["section_key"]: section["content"]
                for section in row["sections"]
                if section["section_status"] in {"assembled", "needs_review"}
            }
        return rows

    def existing_drafts(self, draft):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id,entity_type,entity_id,content_hash FROM content_drafts
                WHERE site_id=%s AND environment=%s AND id<>%s AND status<>'superseded'""",
                (draft["site_id"], draft["environment"], draft["id"]),
            )
            return [dict(row) for row in cur.fetchall()]

    def start_worker_run(self, run_id, site, environment):
        with self.connection.cursor() as cur:
            cur.execute(
                """INSERT INTO worker_runs(id,worker_name,worker_version,site_id,environment,dry_run,status)
                VALUES(%s,'content-validation','1.0.0',%s,%s,false,'running')""",
                (run_id, site, environment),
            )

    def finish_worker_run(self, run_id, summary):
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE worker_runs SET status='completed',result_json=%s::jsonb,finished_at=now() WHERE id=%s",
                (json.dumps(summary), run_id),
            )

    def persist(self, worker_run_id, site, environment, draft, result):
        """Insert history idempotently and mutate only the two allowed state columns."""
        with self.connection.cursor() as cur:
            cur.execute(
                """INSERT INTO content_validation_runs(site_id,environment,worker_run_id,content_draft_id,
                validator_version,ruleset_id,ruleset_version,input_content_hash,evidence_hash,
                validation_identity_hash,status,finished_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'completed',now())
                ON CONFLICT(validation_identity_hash) DO NOTHING RETURNING id""",
                (
                    site,
                    environment,
                    worker_run_id,
                    draft["id"],
                    result["validator_version"],
                    result["ruleset_id"],
                    result["ruleset_version"],
                    result["input_content_hash"],
                    result["evidence_hash"],
                    result["validation_identity_hash"],
                ),
            )
            row = cur.fetchone()
            if not row:
                return {"created": 0, "deduplicated": 1}
            validation_run_id = row[0]
            cur.execute(
                """INSERT INTO content_validation_results(validation_run_id,content_draft_id,overall_result,
                claim_result,structure_result,translation_result,duplication_result,safety_result,
                publication_readiness_result,risk_level,summary_json)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    validation_run_id,
                    draft["id"],
                    result["overall_result"],
                    result["claim_result"],
                    result["structure_result"],
                    result["translation_result"],
                    result["duplication_result"],
                    result["safety_result"],
                    result["publication_readiness_result"],
                    result["risk_level"],
                    json.dumps({"issues": result["issues"], **result["summary"]}),
                ),
            )
            for check in result["claim_checks"]:
                cur.execute(
                    """INSERT INTO content_claim_checks(validation_run_id,content_draft_section_id,claim_key,
                    claim_text_hash,claim_type,result,supporting_evidence_count,reason_code,details_json)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                    (
                        validation_run_id,
                        check["content_draft_section_id"],
                        check["claim_key"],
                        check["claim_text_hash"],
                        check["claim_type"],
                        check["result"],
                        check["supporting_evidence_count"],
                        check["reason_code"],
                        json.dumps(check["details"]),
                    ),
                )
            self._insert_findings(
                cur,
                "content_safety_findings",
                validation_run_id,
                result["safety_findings"],
            )
            self._insert_findings(
                cur,
                "content_duplication_findings",
                validation_run_id,
                result["duplication_findings"],
            )
            cur.execute(
                "UPDATE content_drafts SET validation_state=%s WHERE id=%s",
                (result["draft_validation_state"], draft["id"]),
            )
            cur.execute(
                "UPDATE content_backlog SET content_validation_state=%s,updated_at=now() WHERE id=%s",
                (result["backlog_validation_state"], draft["backlog_item_id"]),
            )
            return {
                "created": 1,
                "deduplicated": 0,
                "validation_run_id": validation_run_id,
            }

    @staticmethod
    def _insert_findings(cur, table, validation_run_id, findings):
        for finding in findings:
            if table == "content_safety_findings":
                cur.execute(
                    f"INSERT INTO {table}(validation_run_id,content_draft_section_id,safety_type,severity,review_required,details_json) VALUES(%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        validation_run_id,
                        finding.get("content_draft_section_id"),
                        finding["safety_type"],
                        finding["severity"],
                        finding["review_required"],
                        json.dumps(finding["details"]),
                    ),
                )
            else:
                cur.execute(
                    f"INSERT INTO {table}(validation_run_id,content_draft_section_id,matched_entity_type,matched_entity_id,match_type,similarity_value,severity,details_json) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        validation_run_id,
                        finding.get("content_draft_section_id"),
                        finding.get("matched_entity_type"),
                        finding.get("matched_entity_id"),
                        finding["match_type"],
                        finding["similarity_value"],
                        finding["severity"],
                        json.dumps(finding["details"]),
                    ),
                )
