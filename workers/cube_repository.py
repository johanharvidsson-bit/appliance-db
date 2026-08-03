"""Database boundary for cube coverage; content reads and worker-owned writes are separated."""
from __future__ import annotations

import json
from psycopg2.extras import RealDictCursor


CONTENT_TABLES = {
    "brands", "categories", "locales", "models", "model_variants", "product_codes",
    "model_content_translations", "model_specs", "error_codes", "error_code_translations",
    "faults", "fault_translations", "guides", "guide_translations", "guide_error_codes",
    "guide_faults", "legacy_model_mapping_candidates", "source_evidence",
}
WORKER_TABLES = {"worker_runs", "cube_scope_snapshots", "cube_coverage_observations", "findings", "content_backlog"}


class CubeRepository:
    def __init__(self, connection):
        self.connection = connection

    def lock(self, site_id: str, environment: str, snapshot_id: int) -> bool:
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (f"cube-coverage:{site_id}:{environment}:{snapshot_id}",))
            return cur.fetchone()[0]

    def unlock(self, site_id: str, environment: str, snapshot_id: int) -> None:
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (f"cube-coverage:{site_id}:{environment}:{snapshot_id}",))

    def snapshot(self, site_id: str, environment: str, *, create: bool, force_new: bool = False) -> dict:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM cube_scope_snapshots WHERE site_id=%s AND environment=%s AND status='active'", (site_id, environment))
            row = cur.fetchone()
            if row and not force_new:
                return dict(row)
            if not create:
                raise ValueError("no active scope snapshot")
            if row and force_new:
                cur.execute("UPDATE cube_scope_snapshots SET status='superseded' WHERE id=%s", (row["id"],))
            cur.execute("SELECT id,slug,name FROM brands WHERE is_active ORDER BY id")
            brands = [dict(x) for x in cur.fetchall()]
            cur.execute("SELECT id,slug_en AS slug FROM categories WHERE is_active ORDER BY id")
            categories = [dict(x) for x in cur.fetchall()]
            cur.execute("SELECT locale FROM site_locales WHERE site_id=%s AND status='active' ORDER BY locale", (site_id,))
            locales = [x["locale"] for x in cur.fetchall()]
            cur.execute("SELECT COALESCE(max(scope_version),0)+1 AS next_version FROM cube_scope_snapshots WHERE site_id=%s AND environment=%s", (site_id, environment))
            version = cur.fetchone()["next_version"]
            cur.execute("INSERT INTO cube_scope_snapshots(scope_version,site_id,environment,brands_json,categories_json,locales_json,status) VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,'active') RETURNING *",
                        (version, site_id, environment, json.dumps(brands), json.dumps(categories), json.dumps(locales)))
            return dict(cur.fetchone())

    def read_content(self, snapshot: dict) -> dict:
        """Read-only transaction; unavailable optional tables are reported, never converted to zero."""
        result = {"scope": {"id": snapshot["id"], "brands": snapshot["brands_json"], "categories": snapshot["categories_json"], "locales": snapshot["locales_json"]}, "data_sources": {}}
        queries = {
            "models": "SELECT m.id,m.brand_id,m.category_id,true AS is_active,EXISTS(SELECT 1 FROM api_public_identities i WHERE i.resource_type='model' AND i.source_id=m.id) AS has_active_identity FROM models m",
            "model_content": "SELECT model_id,locale,overview,short_summary,publication_status FROM model_content_translations",
            "model_specs": "SELECT model_id,specs AS specs_json FROM model_specs",
            "variant_candidates": "SELECT id,legacy_model_id,candidate_status AS status FROM legacy_model_mapping_candidates",
            "product_codes": "SELECT p.id,p.model_id,p.model_variant_id,m.brand_id,m.category_id,EXISTS(SELECT 1 FROM api_public_identities i WHERE i.resource_type='model' AND i.source_id=p.model_id) AS has_active_model_identity FROM product_codes p JOIN models m ON m.id=p.model_id",
            "error_codes": "SELECT id,brand_id,category_id,code FROM error_codes",
            "error_code_translations": "SELECT error_code_id,locale,title,description,publication_status FROM error_code_translations",
            "faults": "SELECT id,brand_id,category_id FROM faults",
            "fault_translations": "SELECT fault_id,locale,symptom_name,description,publication_status FROM fault_translations",
            "guides": "SELECT id,brand_id,category_id,is_general,content_status FROM guides",
            "guide_translations": "SELECT guide_id,locale,title,summary,steps_json,publication_status FROM guide_translations",
            "guide_topics": "SELECT guide_id,relation_status AS status FROM guide_error_codes UNION ALL SELECT guide_id,relation_status FROM guide_faults",
            "evidence_required_relations": "SELECT 'guide' AS entity_type,guide_id::text AS entity_id,relation_status AS status,source_evidence_id FROM guide_error_codes WHERE relation_status='verified'",
        }
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            for key, sql in queries.items():
                try:
                    cur.execute("SAVEPOINT coverage_source")
                    cur.execute(sql)
                    result[key] = [dict(x) for x in cur.fetchall()]
                    result["data_sources"][key] = "available"
                    cur.execute("RELEASE SAVEPOINT coverage_source")
                except Exception:
                    cur.execute("ROLLBACK TO SAVEPOINT coverage_source")
                    result[key] = []
                    result["data_sources"][key] = "not_available"
        # Page expectation is an explicit site publication, never all models by default.
        published = set()
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT model_id,locale FROM site_entity_publications WHERE site_id=%s AND publication_status='published'", (snapshot["site_id"],))
            for row in cur.fetchall():
                published.add((row["model_id"], row["locale"]))
        for model in result.get("models", []):
            model["expected_locales"] = [locale for locale in snapshot["locales_json"] if (model["id"], locale) in published]
            model["public"] = bool(model["expected_locales"])
        return result

    def persist(self, run_id: str, snapshot: dict, report: dict, *, site_id: str, environment: str, rebuild_backlog: bool) -> dict:
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("INSERT INTO worker_runs(id,worker_name,worker_version,site_id,environment,scope_snapshot_id,dry_run,status) VALUES(%s,'cube-coverage','1.0.0',%s,%s,%s,false,'running')", (run_id, site_id, environment, snapshot["id"]))
            observed_hashes = []
            created = reopened = 0
            finding_ids = {}
            for f in report["findings"]:
                observed_hashes.append(f["finding_hash"])
                cur.execute("SELECT id,status,detector_version FROM findings WHERE finding_hash=%s", (f["finding_hash"],))
                old = cur.fetchone()
                if old:
                    status = old["status"]
                    new_status = "open" if status == "resolved" else status
                    reopened += status == "resolved"
                    cur.execute("UPDATE findings SET last_seen_at=now(),status=%s,resolved_at=NULL,source_run_id=%s,details_json=%s::jsonb,updated_at=now() WHERE id=%s", (new_status, run_id, json.dumps(f["details"]), old["id"]))
                    finding_ids[f["finding_hash"]] = old["id"]
                    if status == "resolved":
                        cur.execute("UPDATE content_backlog SET status='queued',updated_at=now() WHERE finding_id=%s AND status='deferred'", (old["id"],))
                else:
                    cur.execute("INSERT INTO findings(site_id,environment,scope_snapshot_id,entity_type,entity_id,locale,finding_type,severity,details_json,detector_name,detector_version,finding_hash,source_run_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'cube-coverage','1.0.0',%s,%s) RETURNING id", (site_id,environment,snapshot["id"],f["entity_type"],f["entity_id"],f["locale"],f["finding_type"],f["severity"],json.dumps(f["details"]),f["finding_hash"],run_id))
                    finding_ids[f["finding_hash"]] = cur.fetchone()["id"]
                    created += 1
            if observed_hashes:
                cur.execute("UPDATE findings SET status='resolved',resolved_at=now(),updated_at=now() WHERE site_id=%s AND environment=%s AND scope_snapshot_id=%s AND detector_name='cube-coverage' AND status IN('open','acknowledged') AND NOT(finding_hash=ANY(%s))", (site_id,environment,snapshot["id"],observed_hashes))
            else:
                cur.execute("UPDATE findings SET status='resolved',resolved_at=now(),updated_at=now() WHERE site_id=%s AND environment=%s AND scope_snapshot_id=%s AND detector_name='cube-coverage' AND status IN('open','acknowledged')", (site_id,environment,snapshot["id"]))
            resolved = cur.rowcount
            cur.execute("UPDATE content_backlog b SET status='deferred',updated_at=now() FROM findings f WHERE b.finding_id=f.id AND f.status='resolved' AND b.status IN('queued','blocked')")
            backlog_created = 0
            for item in report["backlog"]:
                finding_id = finding_ids[item["finding_hash"]]
                cur.execute("SELECT id FROM content_backlog WHERE finding_id=%s AND action_type=%s AND status IN('queued','blocked','in_progress','deferred')", (finding_id,item["action_type"]))
                if not cur.fetchone():
                    cur.execute("INSERT INTO content_backlog(site_id,environment,scope_snapshot_id,finding_id,entity_type,entity_id,locale,action_type,priority,priority_band,risk_level,status,reason_json) SELECT %s,%s,%s,id,entity_type,entity_id,locale,%s,%s,%s,%s,%s,%s::jsonb FROM findings WHERE id=%s", (site_id,environment,snapshot["id"],item["action_type"],item["priority"],item["priority_band"],item["risk_level"],item["status"],json.dumps(item["reason"]),finding_id))
                    backlog_created += 1
            for metric in report["metrics"]:
                cur.execute("INSERT INTO cube_coverage_observations(run_id,scope_snapshot_id,site_id,environment,brand_id,category_id,locale,metric_name,numerator,denominator,percentage,availability,definition) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (run_id,snapshot["id"],site_id,environment,metric["brand_id"],metric["category_id"],metric["locale"],metric["name"],metric["numerator"],metric["denominator"],metric["percentage"],metric["availability"],metric["definition"]))
            stats = {"findings_created":created,"findings_reopened":reopened,"findings_resolved":resolved,"backlog_created":backlog_created}
            cur.execute("UPDATE worker_runs SET status='completed',finished_at=now(),result_json=%s::jsonb WHERE id=%s", (json.dumps(stats),run_id))
            return stats
