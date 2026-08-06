"""Internal draft persistence boundary for PR 3A."""

from __future__ import annotations
import json
from psycopg2.extras import RealDictCursor


class AssemblyRepository:
    WRITABLE_TABLES = frozenset(
        {
            "worker_runs",
            "content_drafts",
            "content_draft_sections",
            "content_draft_evidence",
            "content_draft_issues",
            "content_backlog",
        }
    )

    def __init__(self, connection):
        self.connection = connection

    def lock(self, site, environment, key=None):
        value = (
            f"content-assembly:{site}:{environment}"
            if key is None
            else f"content-assembly:item:{key}"
        )
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (value,))
            return cur.fetchone()[0]

    def unlock(self, site, environment, key=None):
        value = (
            f"content-assembly:{site}:{environment}"
            if key is None
            else f"content-assembly:item:{key}"
        )
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (value,))

    def start_run(self, run_id, site, environment):
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO worker_runs(id,worker_name,worker_version,site_id,environment,dry_run,status) VALUES(%s,'content-assembly','1.0.0',%s,%s,false,'running')",
                (run_id, site, environment),
            )

    def finish_run(self, run_id, result):
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE worker_runs SET status='completed',result_json=%s::jsonb,finished_at=now() WHERE id=%s",
                (json.dumps(result), run_id),
            )

    def items(self, site, environment, limit, filters, reassemble=False):
        sql = """SELECT b.id backlog_id,b.entity_type,b.entity_id,b.locale,b.action_type,b.content_assembly_state,
   COALESCE(m.name,ec.code,f.canonical_name,g.canonical_title) entity_name,br.name brand_name,c.slug_en category_name,
   rg.id resolved_guide_id,rg.canonical_title resolved_guide_title,
   COALESCE(jsonb_agg(DISTINCT jsonb_build_object('source_evidence_id',se.id,'fact_type','canonical_context')) FILTER(WHERE se.id IS NOT NULL),'[]'::jsonb) entity_evidence,
   COALESCE(jsonb_agg(DISTINCT jsonb_build_object('candidate_fact_id',cf.id,'fact_type',cf.fact_type,'predicate',cf.predicate,'value',cf.value_json,'unit',cf.unit,
    'proposal_type',ip.proposal_type,'proposed_value',ip.proposed_value_json,'source_document_id',cf.source_document_id,'evidence_id',cfe.id,'locator',cfe.source_locator,'page_number',cfe.page_number)) FILTER(WHERE ip.id IS NOT NULL),'[]'::jsonb) integrated_facts
   FROM content_backlog b JOIN cube_scope_snapshots css ON css.id=b.scope_snapshot_id
   LEFT JOIN models m ON b.entity_type='model' AND b.entity_id~'^[0-9]+$' AND m.id=b.entity_id::integer
   LEFT JOIN error_codes ec ON b.entity_type='error_code' AND b.entity_id~'^[0-9]+$' AND ec.id=b.entity_id::integer
   LEFT JOIN faults f ON b.entity_type='fault' AND b.entity_id~'^[0-9]+$' AND f.id=b.entity_id::integer
   LEFT JOIN guides g ON b.entity_type='guide' AND b.entity_id~'^[0-9]+$' AND g.id=b.entity_id::bigint
   LEFT JOIN brands br ON br.id=COALESCE(m.brand_id,ec.brand_id,f.brand_id,g.brand_id)
   LEFT JOIN categories c ON c.id=COALESCE(m.category_id,ec.category_id,f.category_id,g.category_id)
   LEFT JOIN source_evidence se ON (b.entity_type='model' AND se.model_id=m.id) OR (b.entity_type='error_code' AND se.error_code_id=ec.id) OR (b.entity_type='fault' AND se.fault_id=f.id) OR (b.entity_type='guide' AND se.guide_id=g.id)
   LEFT JOIN integration_proposals ip ON ip.backlog_item_id=b.id AND ip.status='applied'
   LEFT JOIN integration_apply_attempts ia ON ia.proposal_id=ip.id AND ia.status='succeeded'
   LEFT JOIN candidate_facts cf ON cf.id=ip.candidate_fact_id LEFT JOIN candidate_fact_evidence cfe ON cfe.candidate_fact_id=cf.id
   -- create_reviewed_guide (apply_repository.py) names a new guide's slug
   -- deterministically from the *originating* backlog item's own entity, not
   -- the guide's own id (which does not exist until that operation runs).
   -- Resolve the same slug here so a guide created as a side effect of, say,
   -- a translate_error_code backlog item is attributed to the guide it
   -- actually became, not left mislabeled under the error_code that spawned it.
   LEFT JOIN guide_translations rgt ON rgt.locale=b.locale AND rgt.slug='guide-'||b.entity_type||'-'||b.entity_id||'-'||b.locale
   LEFT JOIN guides rg ON rg.id=rgt.guide_id
   WHERE b.site_id=%s AND b.environment=%s AND css.status='active' AND b.status IN('queued','in_progress','deferred')
    AND b.action_type IN('create_model_overview','translate_model_overview','describe_error_code','translate_error_code','translate_fault','enrich_fault','create_or_enrich_guide','create_faq_candidate')
    AND (b.content_assembly_state='ready_for_content_assembly' OR ia.id IS NOT NULL)"""
        params = [site, environment]
        for col, key in (
            ("b.id", "backlog_id"),
            ("b.entity_type", "entity_type"),
            ("b.entity_id", "entity_id"),
            ("b.locale", "locale"),
        ):
            if filters.get(key) is not None:
                sql += f" AND {col}=%s"
                params.append(filters[key])
        if not reassemble:
            sql += " AND NOT EXISTS(SELECT 1 FROM content_drafts d WHERE d.backlog_item_id=b.id AND d.review_state IN('unreviewed','approved') AND d.status<>'superseded')"
        sql += " GROUP BY b.id,m.name,ec.code,f.canonical_name,g.canonical_title,br.name,c.slug_en,rg.id,rg.canonical_title ORDER BY b.priority DESC,b.id LIMIT %s"
        params.append(limit)
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(sql, params)
            return [dict(x) for x in cur.fetchall()]

    def persist(self, site, environment, run_id, draft, reassemble=False):
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT id,review_state FROM content_drafts WHERE backlog_item_id=%s AND entity_type=%s AND entity_id=%s AND locale=%s AND draft_type=%s AND status<>'superseded' ORDER BY created_at DESC LIMIT 1",
                (
                    draft["backlog_item_id"],
                    draft["entity_type"],
                    draft["entity_id"],
                    draft["locale"],
                    draft["draft_type"],
                ),
            )
            previous = cur.fetchone()
            cur.execute(
                """INSERT INTO content_drafts(site_id,environment,worker_run_id,backlog_item_id,entity_type,entity_id,locale,draft_type,template_id,template_version,status,risk_level,comparison_class,source_input_hash,content_hash,rendered_content_json,assembler_version,validation_state,review_state,supersedes_draft_id)
    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
    ON CONFLICT(backlog_item_id,entity_type,entity_id,locale,draft_type,template_id,template_version,source_input_hash,assembler_version) DO NOTHING RETURNING id""",
                (
                    site,
                    environment,
                    run_id,
                    draft["backlog_item_id"],
                    draft["entity_type"],
                    draft["entity_id"],
                    draft["locale"],
                    draft["draft_type"],
                    draft["template_id"],
                    draft["template_version"],
                    draft["status"],
                    draft["risk_level"],
                    draft["comparison_class"],
                    draft["source_input_hash"],
                    draft["content_hash"],
                    json.dumps(draft["rendered_content"]),
                    draft["assembler_version"],
                    draft["validation_state"],
                    draft["review_state"],
                    previous[0] if previous and previous[1] == "unreviewed" else None,
                ),
            )
            row = cur.fetchone()
            if not row:
                return {
                    "created": 0,
                    "deduplicated": 1,
                    "superseded": 0,
                    "draft_id": None,
                }
            draft_id = row[0]
            section_ids = {}
            for s in draft["sections"]:
                cur.execute(
                    "INSERT INTO content_draft_sections(content_draft_id,section_key,sort_order,section_status,content_json,required,input_hash) VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s) RETURNING id",
                    (
                        draft_id,
                        s["section_key"],
                        s["sort_order"],
                        s["section_status"],
                        json.dumps(s["content"]),
                        s["required"],
                        s["input_hash"],
                    ),
                )
                section_ids[s["section_key"]] = cur.fetchone()[0]
                for e in s["evidence"]:
                    if not any(
                        e.get(k)
                        for k in (
                            "candidate_fact_id",
                            "source_evidence_id",
                            "source_document_id",
                        )
                    ):
                        continue
                    cur.execute(
                        "INSERT INTO content_draft_evidence(content_draft_id,content_draft_section_id,fact_type,entity_type,entity_id,candidate_fact_id,source_evidence_id,source_document_id,support_type,locator_json) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'direct_fact',%s::jsonb)",
                        (
                            draft_id,
                            section_ids[s["section_key"]],
                            e.get("fact_type", "integrated_fact"),
                            draft["entity_type"],
                            draft["entity_id"],
                            e.get("candidate_fact_id"),
                            e.get("source_evidence_id"),
                            e.get("source_document_id"),
                            json.dumps(e.get("locator", {})),
                        ),
                    )
            for i in draft["issues"]:
                cur.execute(
                    "INSERT INTO content_draft_issues(content_draft_id,section_key,issue_type,severity,details_json,status) VALUES(%s,%s,%s,%s,%s::jsonb,%s)",
                    (
                        draft_id,
                        i["section_key"],
                        i["issue_type"],
                        i["severity"],
                        json.dumps(i["details"]),
                        i["status"],
                    ),
                )
            superseded = 0
            if previous and previous[1] == "unreviewed":
                cur.execute(
                    "UPDATE content_drafts SET status='superseded',updated_at=now() WHERE id=%s",
                    (previous[0],),
                )
                superseded = 1
            cur.execute(
                "UPDATE content_backlog SET content_assembly_state=%s,updated_at=now() WHERE id=%s",
                (draft["processing_state"], draft["backlog_item_id"]),
            )
            return {
                "created": 1,
                "deduplicated": 0,
                "superseded": superseded,
                "draft_id": draft_id,
            }
