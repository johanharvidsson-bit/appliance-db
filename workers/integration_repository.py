"""Proposal-only persistence boundary for PR 2C."""

from __future__ import annotations

import json
from psycopg2.extras import RealDictCursor


class IntegrationRepository:
    WRITABLE_TABLES = frozenset(
        {
            "worker_runs",
            "integration_proposals",
            "integration_proposal_targets",
            "integration_proposal_evidence",
            "integration_proposal_conflicts",
            "candidate_facts",
        }
    )

    def __init__(self, connection):
        self.connection = connection

    def lock(self, site, environment, fact_id=None):
        key = (
            f"knowledge-integration:{site}:{environment}"
            if fact_id is None
            else f"knowledge-integration:fact:{fact_id}"
        )
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (key,))
            return cur.fetchone()[0]

    def unlock(self, site, environment, fact_id=None):
        key = (
            f"knowledge-integration:{site}:{environment}"
            if fact_id is None
            else f"knowledge-integration:fact:{fact_id}"
        )
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (key,))

    def start_run(self, run_id, site, environment):
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO worker_runs(id,worker_name,worker_version,site_id,environment,dry_run,status) VALUES(%s,'knowledge-integration','1.0.0',%s,%s,false,'running')",
                (run_id, site, environment),
            )

    def finish_run(self, run_id, result):
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE worker_runs SET status='completed',result_json=%s::jsonb,finished_at=now() WHERE id=%s",
                (json.dumps(result), run_id),
            )

    def facts(self, site, environment, *, limit, filters, reprocess=False):
        sql = """
        SELECT cf.id,cf.source_document_id,cf.source_candidate_id,cf.backlog_item_id,cf.fact_type,cf.subject_hint,
          cf.predicate,cf.value_json AS value,cf.unit,cf.locale,cf.confidence,cf.extraction_status,
          cf.conflict_metadata,cf.integration_state,b.entity_type AS backlog_entity_type,b.entity_id AS backlog_entity_id,
          COALESCE(m.brand_id,ec.brand_id,f.brand_id,g.brand_id) AS brand_id,
          COALESCE(m.category_id,ec.category_id,f.category_id,g.category_id) AS category_id,
          COALESCE(jsonb_agg(jsonb_build_object('id',cfe.id,'source_document_id',cfe.source_document_id,'locator',cfe.source_locator,
            'page_number',cfe.page_number,'section_heading',cfe.section_heading,'json_path',cfe.json_path)) FILTER(WHERE cfe.id IS NOT NULL),'[]'::jsonb) AS evidence
        FROM candidate_facts cf JOIN content_backlog b ON b.id=cf.backlog_item_id
        JOIN cube_scope_snapshots css ON css.id=b.scope_snapshot_id
        LEFT JOIN models m ON b.entity_type='model' AND b.entity_id~'^[0-9]+$' AND m.id=b.entity_id::integer
        LEFT JOIN error_codes ec ON b.entity_type='error_code' AND b.entity_id~'^[0-9]+$' AND ec.id=b.entity_id::integer
        LEFT JOIN faults f ON b.entity_type='fault' AND b.entity_id~'^[0-9]+$' AND f.id=b.entity_id::integer
        LEFT JOIN guides g ON b.entity_type='guide' AND b.entity_id~'^[0-9]+$' AND g.id=b.entity_id::bigint
        LEFT JOIN candidate_fact_evidence cfe ON cfe.candidate_fact_id=cf.id
        WHERE b.site_id=%s AND b.environment=%s AND css.status='active'
          AND cf.extraction_status IN('candidate','needs_review','conflicted')
          AND b.status IN('queued','in_progress','deferred')
        """
        params = [site, environment]
        if not reprocess:
            sql += " AND cf.integration_state='unprocessed'"
        mapping = (
            ("cf.id", "candidate_fact_id"),
            ("cf.backlog_item_id", "backlog_id"),
            ("cf.fact_type", "fact_type"),
            ("cf.locale", "locale"),
            ("COALESCE(m.brand_id,ec.brand_id,f.brand_id,g.brand_id)", "brand"),
            (
                "COALESCE(m.category_id,ec.category_id,f.category_id,g.category_id)",
                "category",
            ),
        )
        for column, key in mapping:
            if filters.get(key) is not None:
                sql += f" AND {column}=%s"
                params.append(filters[key])
        if filters.get("min_confidence") is not None:
            sql += " AND cf.confidence>=%s"
            params.append(filters["min_confidence"])
        sql += " GROUP BY cf.id,b.entity_type,b.entity_id,m.brand_id,m.category_id,ec.brand_id,ec.category_id,f.brand_id,f.category_id,g.brand_id,g.category_id,b.priority ORDER BY b.priority DESC,cf.id LIMIT %s"
        params.append(limit)
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(sql, params)
            return [dict(x) for x in cur.fetchall()]

    def catalog(self, facts):
        brand_ids = sorted(
            {x["brand_id"] for x in facts if x.get("brand_id") is not None}
        )
        category_ids = sorted(
            {x["category_id"] for x in facts if x.get("category_id") is not None}
        )
        if not brand_ids or not category_ids:
            return {
                "models": [],
                "variants": [],
                "product_codes": [],
                "error_codes": [],
                "faults": [],
                "guides": [],
                "model_specs": {},
                "model_overviews": {},
                "model_aliases": [],
            }
        out = {}
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id,brand_id,category_id,name,slug,base_model FROM models WHERE brand_id=ANY(%s) AND category_id=ANY(%s)",
                (brand_ids, category_ids),
            )
            out["models"] = [dict(x) for x in cur.fetchall()]
            model_ids = [x["id"] for x in out["models"]] or [-1]
            cur.execute(
                "SELECT id,model_id,variant_code,normalized_variant_code,status FROM model_variants WHERE model_id=ANY(%s)",
                (model_ids,),
            )
            out["variants"] = [dict(x) for x in cur.fetchall()]
            cur.execute(
                "SELECT id,model_id,model_variant_id,code,normalized_code FROM product_codes WHERE model_id=ANY(%s)",
                (model_ids,),
            )
            out["product_codes"] = [dict(x) for x in cur.fetchall()]
            cur.execute(
                "SELECT id,brand_id,category_id,code,short_description,description FROM error_codes WHERE brand_id=ANY(%s) AND category_id=ANY(%s)",
                (brand_ids, category_ids),
            )
            out["error_codes"] = [dict(x) for x in cur.fetchall()]
            cur.execute(
                "SELECT id,brand_id,category_id,canonical_name FROM faults WHERE brand_id=ANY(%s) AND category_id=ANY(%s)",
                (brand_ids, category_ids),
            )
            out["faults"] = [dict(x) for x in cur.fetchall()]
            cur.execute(
                "SELECT id,brand_id,category_id,canonical_title FROM guides WHERE (brand_id IS NULL OR brand_id=ANY(%s)) AND category_id=ANY(%s)",
                (brand_ids, category_ids),
            )
            out["guides"] = [dict(x) for x in cur.fetchall()]
            cur.execute(
                "SELECT model_id,specs FROM model_specs WHERE model_id=ANY(%s)",
                (model_ids,),
            )
            out["model_specs"] = {
                str(x["model_id"]): x["specs"] for x in cur.fetchall()
            }
            cur.execute(
                "SELECT model_id,locale,overview,short_summary FROM model_content_translations WHERE model_id=ANY(%s)",
                (model_ids,),
            )
            out["model_overviews"] = {
                f"{x['model_id']}:{x['locale']}": x["overview"] or x["short_summary"]
                for x in cur.fetchall()
            }
        out["model_aliases"] = []
        out["default_locale"] = "en"
        return out

    def persist(self, site, environment, run_id, result):
        created = deduplicated = conflicts = 0
        proposal_ids = []
        with self.connection.cursor() as cur:
            for p in result["proposals"]:
                cur.execute(
                    """INSERT INTO integration_proposals(site_id,environment,worker_run_id,backlog_item_id,candidate_fact_id,proposal_type,entity_type,entity_id,locale,status,confidence,risk_level,difference_class,reason_json,current_value_json,proposed_value_json,expected_apply_operation,input_hash,detector_name,detector_version)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,'repairbase_deterministic_resolver','1.0.0')
                ON CONFLICT(input_hash) DO NOTHING RETURNING id""",
                    (
                        site,
                        environment,
                        run_id,
                        p["backlog_item_id"],
                        p["candidate_fact_id"],
                        p["proposal_type"],
                        p["entity_type"],
                        p["entity_id"],
                        p["locale"],
                        p["status"],
                        p["confidence"],
                        p["risk_level"],
                        p["difference_class"],
                        json.dumps(p["reason"]),
                        json.dumps(p["current_value"]),
                        json.dumps(p["proposed_value"]),
                        p["expected_apply_operation"],
                        p["input_hash"],
                    ),
                )
                row = cur.fetchone()
                if not row:
                    deduplicated += 1
                    continue
                proposal_id = row[0]
                proposal_ids.append(proposal_id)
                created += 1
                for t in p["targets"]:
                    cur.execute(
                        "INSERT INTO integration_proposal_targets(proposal_id,target_entity_type,target_entity_id,match_type,match_score,is_preferred,reason_json) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)",
                        (
                            proposal_id,
                            t["target_entity_type"],
                            t["target_entity_id"],
                            t["match_type"],
                            t["match_score"],
                            t["is_preferred"],
                            json.dumps(t["reason"]),
                        ),
                    )
                for e in p["evidence"]:
                    cur.execute(
                        "INSERT INTO integration_proposal_evidence(proposal_id,candidate_fact_id,candidate_fact_evidence_id,source_document_id,support_type) VALUES(%s,%s,%s,%s,'supports')",
                        (
                            proposal_id,
                            p["candidate_fact_id"],
                            e.get("id"),
                            e.get("source_document_id"),
                        ),
                    )
                for c in p["conflicts"]:
                    cur.execute(
                        "INSERT INTO integration_proposal_conflicts(proposal_id,conflict_type,conflicting_entity_type,conflicting_entity_id,conflicting_value_json,severity,details_json,status) VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s)",
                        (
                            proposal_id,
                            c["conflict_type"],
                            c.get("entity_type"),
                            c.get("entity_id"),
                            json.dumps(c.get("value")),
                            c["severity"],
                            json.dumps(c["details"]),
                            c["status"],
                        ),
                    )
                    conflicts += 1
            cur.execute(
                "UPDATE candidate_facts SET integration_state=%s,updated_at=now() WHERE id=%s",
                (result["processing_state"], result["candidate_fact_id"]),
            )
        return {
            "created": created,
            "deduplicated": deduplicated,
            "conflicts": conflicts,
            "proposal_ids": proposal_ids,
        }
