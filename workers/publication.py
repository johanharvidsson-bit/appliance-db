"""Shared "this content is proven ready to be public" logic.

Two places in the pipeline currently prove that: a successful translation
(workers/translation_repository.py's publish_source_if_draft/
publish_guide_parent_if_ready) and a passing content-validation result
(this module, called from validation_repository.py). Kept as a small
duplication rather than a shared refactor of the already-verified
translation worker path, to avoid touching tested, production-proven code.
"""
from __future__ import annotations

from workers.translation import TRANSLATABLE_TABLES


def publish_entity_content(connection, entity_type: str, entity_id, locale: str) -> None:
    """Publish an entity's locale-specific content row, and if it's a guide,
    the parent guides row + its topic link too (same gate a DB trigger
    enforces - see translation_repository.py's publish_guide_parent_if_ready
    for the full rationale)."""
    cfg = TRANSLATABLE_TABLES[entity_type]
    table, id_col = cfg["table"], cfg["id_column"]
    with connection.cursor() as cur:
        cur.execute(
            f"UPDATE {table} SET publication_status='published',updated_at=now() "
            f"WHERE {id_col}=%s AND locale=%s AND publication_status='draft'",
            (entity_id, locale),
        )
        if entity_type != "guide":
            return
        cur.execute(
            "UPDATE guide_error_codes SET relation_status='verified',updated_at=now() "
            "WHERE guide_id=%s AND relation_status='candidate'",
            (entity_id,),
        )
        cur.execute(
            "UPDATE guide_faults SET relation_status='verified',updated_at=now() "
            "WHERE guide_id=%s AND relation_status='candidate'",
            (entity_id,),
        )
        cur.execute(
            "UPDATE guides SET content_status='published',updated_at=now() "
            "WHERE id=%s AND content_status='draft'",
            (entity_id,),
        )
