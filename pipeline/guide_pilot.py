"""Guarded, idempotent guide pilot for one explicit local brand/category/locale."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import psycopg2

from config.target_safety import assert_safe_target


def _require_dev(dsn: str, environment: str) -> None:
    if environment != "development":
        raise ValueError("guide pilot is restricted to development")
    assert_safe_target(dsn, app_env=environment, operation="write")


def load_pilot(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"brand_slug", "category_slug", "locale", "slug", "title", "steps", "error_code", "source_url", "source_locator"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"missing guide pilot fields: {', '.join(missing)}")
    if not isinstance(payload["steps"], list) or not payload["steps"]:
        raise ValueError("guide pilot requires at least one step")
    return payload


def persist_guide_pilot(payload: dict, *, dsn: str, environment: str = "development") -> dict:
    _require_dev(dsn, environment)
    created = {"source": False, "guide": False, "translation": False, "topic": False, "evidence": False}
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM brands WHERE slug=%s", (payload["brand_slug"],))
            brand = cursor.fetchone()
            cursor.execute("SELECT id FROM categories WHERE slug_en=%s", (payload["category_slug"],))
            category = cursor.fetchone()
            if not brand or not category:
                raise ValueError("pilot brand/category does not exist")
            brand_id, category_id = brand[0], category[0]
            cursor.execute(
                "SELECT id FROM error_codes WHERE brand_id=%s AND category_id=%s AND upper(btrim(code))=%s",
                (brand_id, category_id, payload["error_code"].strip().upper()),
            )
            error_code = cursor.fetchone()
            if not error_code:
                raise ValueError("pilot error code does not exist in selected scope")
            error_code_id = error_code[0]

            normalized_url = payload["source_url"].strip()
            content_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
            cursor.execute(
                "SELECT id FROM sources WHERE normalized_url=%s AND content_hash=%s",
                (normalized_url, content_hash),
            )
            row = cursor.fetchone()
            if row:
                source_id = row[0]
            else:
                cursor.execute(
                    "INSERT INTO sources(url,normalized_url,source_type,title,retrieved_at,content_hash) "
                    "VALUES(%s,%s,'dataset',%s,%s,%s) RETURNING id",
                    (payload["source_url"], normalized_url, "synthetic guide pilot", datetime.now(timezone.utc), content_hash),
                )
                source_id = cursor.fetchone()[0]
                created["source"] = True

            cursor.execute(
                "SELECT guide_id,id FROM guide_translations WHERE locale=%s AND slug=%s",
                (payload["locale"], payload["slug"]),
            )
            translation = cursor.fetchone()
            if translation:
                guide_id, translation_id = translation
                cursor.execute("SELECT category_id,brand_id FROM guides WHERE id=%s", (guide_id,))
                if cursor.fetchone() != (category_id, brand_id):
                    raise ValueError("guide slug already belongs to another scope")
            else:
                cursor.execute(
                    "INSERT INTO guides(category_id,brand_id,canonical_title,default_difficulty,default_estimated_minutes,safety_notes) "
                    "VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",
                    (category_id, brand_id, payload["title"], payload.get("difficulty"), payload.get("estimated_minutes"), payload.get("safety_notes")),
                )
                guide_id = cursor.fetchone()[0]
                created["guide"] = True
                cursor.execute(
                    "INSERT INTO guide_translations(guide_id,locale,slug,title,short_description,summary,steps_json,source_hash) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING id",
                    (guide_id, payload["locale"], payload["slug"], payload["title"], payload.get("short_description"), payload.get("summary"), json.dumps(payload["steps"]), content_hash),
                )
                translation_id = cursor.fetchone()[0]
                created["translation"] = True

            cursor.execute(
                "SELECT id FROM source_evidence WHERE source_id=%s AND guide_translation_id=%s "
                "AND field_name='steps_json' AND source_locator=%s",
                (source_id, translation_id, payload["source_locator"]),
            )
            evidence = cursor.fetchone()
            if evidence:
                evidence_id = evidence[0]
            else:
                cursor.execute(
                    "INSERT INTO source_evidence(source_id,guide_translation_id,field_name,source_locator,observed_value,confidence,observed_at) "
                    "VALUES(%s,%s,'steps_json',%s,%s::jsonb,%s,%s) RETURNING id",
                    (source_id, translation_id, payload["source_locator"], json.dumps(payload["steps"]), payload.get("confidence", 100), datetime.now(timezone.utc)),
                )
                evidence_id = cursor.fetchone()[0]
                created["evidence"] = True

            cursor.execute("SELECT id FROM guide_error_codes WHERE guide_id=%s AND error_code_id=%s", (guide_id, error_code_id))
            topic = cursor.fetchone()
            if topic:
                topic_id = topic[0]
            else:
                cursor.execute(
                    "INSERT INTO guide_error_codes(guide_id,error_code_id,is_primary,relation_status,confidence,source_evidence_id) "
                    "VALUES(%s,%s,true,'candidate',%s,%s) RETURNING id",
                    (guide_id, error_code_id, payload.get("confidence", 100), evidence_id),
                )
                topic_id = cursor.fetchone()[0]
                created["topic"] = True
    return {"guide_id": guide_id, "translation_id": translation_id, "topic_id": topic_id, "evidence_id": evidence_id, "created": created, "published": False}


def publish_reviewed_pilot(guide_id: int, *, reviewed_by: str, dsn: str, environment: str = "development") -> dict:
    _require_dev(dsn, environment)
    if not reviewed_by.strip():
        raise ValueError("reviewed_by is required")
    now = datetime.now(timezone.utc)
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM guide_error_codes WHERE guide_id=%s AND source_evidence_id IS NOT NULL", (guide_id,))
            if cursor.fetchone()[0] == 0:
                raise ValueError("guide pilot has no evidence-backed topic")
            cursor.execute(
                "UPDATE source_evidence SET verification_status='verified',verified_at=%s,verified_by=%s "
                "WHERE id IN(SELECT source_evidence_id FROM guide_error_codes WHERE guide_id=%s)",
                (now, reviewed_by, guide_id),
            )
            cursor.execute("UPDATE guide_error_codes SET relation_status='verified' WHERE guide_id=%s", (guide_id,))
            cursor.execute("UPDATE guide_translations SET publication_status='published',reviewed_at=%s WHERE guide_id=%s", (now, guide_id))
            cursor.execute("UPDATE guides SET content_status='published' WHERE id=%s", (guide_id,))
    return {"guide_id": guide_id, "published": True, "reviewed_by": reviewed_by}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="bounded synthetic/local guide pilot")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--environment", default="development")
    parser.add_argument("--database-url-env", default="REPAIRBASE_GUIDE_PILOT_DB_URL")
    parser.add_argument("--publish-reviewed-by")
    args = parser.parse_args(argv)
    dsn = os.getenv(args.database_url_env, "").strip()
    if not dsn:
        raise RuntimeError(f"missing database URL environment variable: {args.database_url_env}")
    result = persist_guide_pilot(load_pilot(args.input), dsn=dsn, environment=args.environment)
    if args.publish_reviewed_by:
        result["publication"] = publish_reviewed_pilot(result["guide_id"], reviewed_by=args.publish_reviewed_by, dsn=dsn, environment=args.environment)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
