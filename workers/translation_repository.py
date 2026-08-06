"""PostgreSQL boundary for the translation worker."""
from __future__ import annotations

import json
from psycopg2.extras import RealDictCursor

from workers.translation import TRANSLATABLE_TABLES, needs_translation

_ENTITY_TABLE = {
    "model": "models",
    "error_code": "error_codes",
    "fault": "faults",
    "guide": "guides",
}


class TranslationRepository:
    WRITABLE_TABLES = frozenset(
        {
            "worker_runs",
            "model_content_translations",
            "error_code_translations",
            "fault_translations",
            "guide_translations",
        }
    )

    def __init__(self, connection):
        self.connection = connection

    def lock(self, site, environment, key=None):
        value = (
            f"translation:{site}:{environment}"
            if key is None
            else f"translation:item:{key}"
        )
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (value,))
            return cur.fetchone()[0]

    def unlock(self, site, environment, key=None):
        value = (
            f"translation:{site}:{environment}"
            if key is None
            else f"translation:item:{key}"
        )
        with self.connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (value,))

    def start_run(self, run_id, site, environment):
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO worker_runs(id,worker_name,worker_version,site_id,environment,dry_run,status) VALUES(%s,'translation','1.0.0',%s,%s,false,'running')",
                (run_id, site, environment),
            )

    def finish_run(self, run_id, result):
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE worker_runs SET status='completed',result_json=%s::jsonb,finished_at=now() WHERE id=%s",
                (json.dumps(result), run_id),
            )

    def candidates(self, entity_type, *, source_locale, target_locale, limit, brand=None, category=None):
        # Every one of the seven upstream workers only ever writes
        # draft/review - by design, publication is a deliberately separate,
        # later stage that nothing in this pipeline performs yet. Requiring
        # publication_status='published' here would mean this worker could
        # never select anything at all. Evidenced content_status is what
        # actually establishes trustworthiness (apply-integration only
        # writes evidenced facts); draft here means "not yet exposed
        # publicly", not "unverified".
        cfg = TRANSLATABLE_TABLES[entity_type]
        table, id_col = cfg["table"], cfg["id_column"]
        entity_table = _ENTITY_TABLE[entity_type]
        field_cols = ",".join(f"src.{f.name}" for f in cfg["fields"])
        sql = f"""
        SELECT src.{id_col} AS entity_id, {field_cols},
               tgt.source_hash AS target_source_hash, tgt.locale AS target_locale_present
        FROM {table} src
        JOIN {entity_table} e ON e.id = src.{id_col}
        JOIN brands b ON b.id = e.brand_id
        JOIN categories c ON c.id = e.category_id
        LEFT JOIN {table} tgt ON tgt.{id_col} = src.{id_col} AND tgt.locale = %s
        WHERE src.locale = %s AND src.publication_status IN ('draft','review','published')
          AND b.is_active AND c.is_active
        """
        params = [target_locale, source_locale]
        if brand is not None:
            sql += " AND b.slug = %s"
            params.append(brand)
        if category is not None:
            sql += " AND c.slug_en = %s"
            params.append(category)
        sql += f" ORDER BY src.{id_col} LIMIT %s"
        params.append(limit)
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
        # SET TRANSACTION READ ONLY applies to the whole transaction, not just
        # this cursor - without closing it here, the next write on this
        # connection (persist()) fails with ReadOnlySqlTransaction.
        self.connection.rollback()
        selected = []
        for row in rows:
            target_row = (
                {"source_hash": row["target_source_hash"]}
                if row["target_locale_present"] is not None
                else None
            )
            if needs_translation(row, target_row, cfg["fields"]):
                selected.append(row)
        return selected

    def persist(self, entity_type, entity_id, target_locale, values, source_hash, *, slug=None):
        cfg = TRANSLATABLE_TABLES[entity_type]
        table, id_col = cfg["table"], cfg["id_column"]
        columns = [id_col, "locale", "source_hash", "publication_status"]
        placeholders = ["%s", "%s", "%s", "'published'"]
        params = [entity_id, target_locale, source_hash]
        for f in cfg["fields"]:
            if f.name not in values:
                continue
            columns.append(f.name)
            if f.is_list:
                placeholders.append("%s::jsonb")
                params.append(json.dumps(values[f.name]))
            else:
                placeholders.append("%s")
                params.append(values[f.name])
        if cfg["has_slug"]:
            columns.append("slug")
            placeholders.append("%s")
            params.append(slug)
            if "title" not in values:
                raise ValueError("guide_translation_requires_title")
        update_clause = ",".join(
            f"{c}=EXCLUDED.{c}" for c in columns if c not in (id_col, "locale")
        )
        update_clause += ",updated_at=now()"
        sql = (
            f"INSERT INTO {table}({','.join(columns)}) VALUES({','.join(placeholders)}) "
            f"ON CONFLICT({id_col},locale) DO UPDATE SET {update_clause} "
            f"RETURNING {id_col}"
        )
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]

    def publish_source_if_draft(self, entity_type, entity_id, source_locale):
        """A source row just proven complete enough to translate from is, by
        the same standard, complete enough to publish in its own locale -
        nothing else in this pipeline currently performs that transition."""
        cfg = TRANSLATABLE_TABLES[entity_type]
        table, id_col = cfg["table"], cfg["id_column"]
        with self.connection.cursor() as cur:
            cur.execute(
                f"UPDATE {table} SET publication_status='published',updated_at=now() "
                f"WHERE {id_col}=%s AND locale=%s AND publication_status='draft'",
                (entity_id, source_locale),
            )
