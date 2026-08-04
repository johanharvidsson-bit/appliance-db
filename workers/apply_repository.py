"""PostgreSQL boundary for allowlisted apply operations."""

from __future__ import annotations
from contextlib import contextmanager
import json
from psycopg2.extras import RealDictCursor


class ApplyRepository:
    WRITABLE_TABLES = frozenset(
        {
            "integration_apply_attempts",
            "integration_apply_changes",
            "model_specs",
            "model_content_translations",
            "error_code_translations",
            "fault_translations",
            "model_variants",
        }
    )

    def __init__(self, connection, run_id=None):
        self.connection, self.run_id = connection, run_id

    def begin_run(self, site, environment):
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO worker_runs(id,worker_name,worker_version,site_id,environment,dry_run,status) VALUES(%s,'apply-integration','1.0.0',%s,%s,false,'running')",
                (self.run_id, site, environment),
            )
        self.connection.commit()

    def finish_run(self, status, result):
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE worker_runs SET status=%s,result_json=%s::jsonb,finished_at=now() WHERE id=%s",
                (status, json.dumps(result), self.run_id),
            )
        self.connection.commit()

    def record_terminal_attempt(self, proposal_id, status, applied_by, failure_code):
        """Persist a failed/blocked/stale result after the domain transaction rolled back."""
        try:
            with self.connection.cursor() as cur:
                cur.execute(
                    """INSERT INTO integration_apply_attempts(
                         proposal_id,worker_run_id,attempt_number,status,applied_by,
                         failure_code,failure_summary,transaction_id,
                         proposal_input_hash,operation,finished_at)
                       SELECT p.id,%s,COALESCE(max(a.attempt_number),0)+1,%s,%s,
                              %s,%s,txid_current(),p.input_hash,
                              p.expected_apply_operation,now()
                       FROM integration_proposals p
                       LEFT JOIN integration_apply_attempts a ON a.proposal_id=p.id
                       WHERE p.id=%s
                       GROUP BY p.id,p.input_hash,p.expected_apply_operation
                       RETURNING id""",
                    (
                        self.run_id,
                        status,
                        applied_by,
                        failure_code,
                        failure_code,
                        proposal_id,
                    ),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("proposal_not_found")
            self.connection.commit()
            return row[0]
        except Exception:
            self.connection.rollback()
            raise

    def proposals(self, site, environment, *, limit, filters, retry_failed=False):
        sql = """SELECT p.id FROM integration_proposals p WHERE p.site_id=%s AND p.environment=%s AND p.status='approved'"""
        params = [site, environment]
        for column, key in (
            ("p.id", "proposal_id"),
            ("p.proposal_type", "proposal_type"),
            ("p.risk_level", "risk_level"),
            ("p.reviewed_by", "reviewed_by"),
        ):
            if filters.get(key) is not None:
                sql += f" AND {column}=%s"
                params.append(filters[key])
        if not retry_failed:
            sql += " AND NOT EXISTS(SELECT 1 FROM integration_apply_attempts a WHERE a.proposal_id=p.id AND a.status IN('succeeded','failed','stale'))"
        sql += " ORDER BY p.id LIMIT %s"
        params.append(limit)
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            return [r[0] for r in cur.fetchall()]

    @contextmanager
    def proposal_transaction(self, proposal_id):
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"apply-proposal:{proposal_id}",),
                )
                cur.execute(
                    """SELECT p.*,
                  (SELECT count(*) FROM integration_proposal_conflicts c WHERE c.proposal_id=p.id AND c.status='open' AND c.severity IN('high','safety_review')) blocking_conflicts,
                  COALESCE((SELECT jsonb_agg(to_jsonb(e)) FROM integration_proposal_evidence e WHERE e.proposal_id=p.id),'[]') evidence,
                  (SELECT to_jsonb(t) FROM integration_proposal_targets t WHERE t.proposal_id=p.id AND t.is_preferred) preferred_target,
                  EXISTS(SELECT 1 FROM integration_apply_attempts a WHERE a.proposal_id=p.id AND a.status='succeeded') successful_attempt
                FROM integration_proposals p WHERE p.id=%s FOR UPDATE""",
                    (proposal_id,),
                )
                proposal = cur.fetchone()
                if not proposal:
                    raise ValueError("proposal_not_found")
                yield dict(proposal)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def start_attempt(self, proposal, plan, applied_by):
        with self.connection.cursor() as cur:
            cur.execute(
                """INSERT INTO integration_apply_attempts(proposal_id,worker_run_id,attempt_number,status,applied_by,transaction_id,proposal_input_hash,operation)
              SELECT %s,%s,COALESCE(max(attempt_number),0)+1,'started',%s,txid_current(),%s,%s FROM integration_apply_attempts WHERE proposal_id=%s RETURNING id""",
                (
                    proposal["id"],
                    self.run_id,
                    applied_by,
                    proposal["input_hash"],
                    plan["operation"],
                    proposal["id"],
                ),
            )
            return cur.fetchone()[0]

    def validate_target(self, plan):
        entity_id = int(plan["target"].get("target_entity_id") or 0)
        op = plan["operation"]
        target_table = {
            "upsert_model_spec_field": "models",
            "update_model_content_field": "models",
            "update_error_code_content": "error_codes",
            "upsert_draft_fault_translation": "faults",
            "create_candidate_model_variant": "models",
        }[op]
        with self.connection.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {target_table} WHERE id=%s FOR KEY SHARE", (entity_id,)
            )
            if not cur.fetchone():
                raise ValueError("target_deleted")
            if op in {
                "update_model_content_field",
                "update_error_code_content",
                "upsert_draft_fault_translation",
            }:
                locale = plan.get("locale") or plan["proposed"].get("locale")
                cur.execute("SELECT 1 FROM locales WHERE code=%s", (locale,))
                if not cur.fetchone():
                    raise ValueError("locale_out_of_scope")

    def read_current(self, plan):
        target = plan["target"] or {}
        entity_id = int(target.get("target_entity_id") or 0)
        proposed = plan["proposed"]
        op = plan["operation"]
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            if op == "create_candidate_model_variant":
                code = proposed["variant_code"]
                cur.execute(
                    "SELECT to_jsonb(v) AS value FROM model_variants v WHERE model_id=%s AND normalized_variant_code=upper(regexp_replace(%s,'[^A-Za-z0-9]','','g')) FOR UPDATE",
                    (entity_id, code),
                )
                row = cur.fetchone()
                return row["value"] if row else None
            if op == "upsert_model_spec_field":
                cur.execute(
                    "SELECT specs->%s AS value FROM model_specs WHERE model_id=%s FOR UPDATE",
                    (proposed["field"], entity_id),
                )
                row = cur.fetchone()
                return row["value"] if row else None
            table, fk = {
                "update_model_content_field": (
                    "model_content_translations",
                    "model_id",
                ),
                "update_error_code_content": (
                    "error_code_translations",
                    "error_code_id",
                ),
                "upsert_draft_fault_translation": ("fault_translations", "fault_id"),
            }[op]
            field = proposed.get(
                "field",
                "overview"
                if op == "update_model_content_field"
                else "description"
                if op == "update_error_code_content"
                else "symptom_name",
            )
            allowed_fields = {
                "update_model_content_field": {"overview", "short_summary"},
                "update_error_code_content": {"description"},
                "upsert_draft_fault_translation": {
                    "symptom_name",
                    "meta_description",
                },
            }
            if field not in allowed_fields[op]:
                raise ValueError("field_not_allowlisted")
            cur.execute(
                f"SELECT {field} AS value FROM {table} WHERE {fk}=%s AND locale=%s FOR UPDATE",
                (entity_id, plan.get("locale") or proposed.get("locale") or "en"),
            )
            row = cur.fetchone()
            return row["value"] if row else None

    def mutate(self, plan):
        target = plan["target"] or {}
        entity_id = int(target.get("target_entity_id") or 0)
        proposed = plan["proposed"]
        op = plan["operation"]
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            if op == "upsert_model_spec_field":
                cur.execute(
                    "INSERT INTO model_specs(model_id,specs) VALUES(%s,jsonb_build_object(%s,%s::jsonb)) ON CONFLICT(model_id) DO UPDATE SET specs=COALESCE(model_specs.specs,'{}')||jsonb_build_object(%s,%s::jsonb) RETURNING specs->%s value",
                    (
                        entity_id,
                        proposed["field"],
                        json.dumps(proposed["value"]),
                        proposed["field"],
                        json.dumps(proposed["value"]),
                        proposed["field"],
                    ),
                )
                return cur.fetchone()["value"]
            if op == "create_candidate_model_variant":
                code = proposed["variant_code"]
                cur.execute(
                    "INSERT INTO model_variants(model_id,variant_code,normalized_variant_code,status) VALUES(%s,%s,upper(regexp_replace(%s,'[^A-Za-z0-9]','','g')),'candidate') ON CONFLICT(model_id,normalized_variant_code) DO NOTHING RETURNING to_jsonb(model_variants) value",
                    (entity_id, code, code),
                )
                row = cur.fetchone()
                return row["value"] if row else proposed
            locale = proposed.get("locale") or plan.get("locale") or "en"
            value = (
                proposed.get("value")
                or proposed.get("source_value")
                or proposed.get("overview")
                or proposed.get("description")
                or proposed.get("symptom_name")
            )
            if op == "update_model_content_field":
                field = proposed.get("field")
                if field == "overview":
                    cur.execute(
                        "INSERT INTO model_content_translations(model_id,locale,overview,publication_status) VALUES(%s,%s,%s,'draft') ON CONFLICT(model_id,locale) DO UPDATE SET overview=excluded.overview,publication_status='draft',updated_at=now() RETURNING overview value",
                        (entity_id, locale, value),
                    )
                elif field == "short_summary":
                    cur.execute(
                        "INSERT INTO model_content_translations(model_id,locale,short_summary,publication_status) VALUES(%s,%s,%s,'draft') ON CONFLICT(model_id,locale) DO UPDATE SET short_summary=excluded.short_summary,publication_status='draft',updated_at=now() RETURNING short_summary value",
                        (entity_id, locale, value),
                    )
                else:
                    raise ValueError("field_not_allowlisted")
            elif op == "update_error_code_content":
                cur.execute(
                    "INSERT INTO error_code_translations(error_code_id,locale,title,description,publication_status) SELECT e.id,%s,COALESCE(%s,e.code),%s,'draft' FROM error_codes e WHERE e.id=%s ON CONFLICT(error_code_id,locale) DO UPDATE SET description=excluded.description,publication_status='draft',updated_at=now() RETURNING description value",
                    (locale, proposed.get("title"), value, entity_id),
                )
            else:
                cur.execute(
                    "INSERT INTO fault_translations(fault_id,locale,symptom_name,meta_description,publication_status) VALUES(%s,%s,%s,%s,'draft') ON CONFLICT(fault_id,locale) DO UPDATE SET symptom_name=excluded.symptom_name,meta_description=excluded.meta_description,publication_status='draft',updated_at=now() RETURNING symptom_name value",
                    (
                        entity_id,
                        locale,
                        proposed.get("symptom_name") or value,
                        proposed.get("meta_description"),
                    ),
                )
            return cur.fetchone()["value"]

    def record_change(self, attempt_id, c):
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO integration_apply_changes(apply_attempt_id,entity_type,entity_id,table_name,operation,key_json,before_json,after_json,change_hash,rollback_payload_json) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb)",
                (
                    attempt_id,
                    c["entity_type"],
                    c["entity_id"],
                    c["table_name"],
                    c["operation"],
                    json.dumps(c["key"]),
                    json.dumps(c["before"]),
                    json.dumps(c["after"]),
                    c["change_hash"],
                    json.dumps(c["rollback_payload"]),
                ),
            )

    def finish_attempt(self, attempt_id, status):
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE integration_apply_attempts SET status=%s,finished_at=now() WHERE id=%s",
                (status, attempt_id),
            )
