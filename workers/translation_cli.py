from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from uuid import uuid4

import psycopg2

from config.target_safety import (
    assert_configured_development_target,
    production_approval_from_env,
)
from workers.translation import (
    TRANSLATABLE_TABLES,
    TranslationEngine,
    build_slug,
    source_content_hash,
)
from workers.translation_repository import TranslationRepository


def _site_target_locales(cur, site):
    cur.execute(
        "SELECT locale FROM site_locales WHERE site_id=%s AND status='active' AND NOT is_default",
        (site,),
    )
    return [r[0] for r in cur.fetchall()]


def run(args):
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    started = datetime.now(timezone.utc)
    run_id = str(uuid4())
    entity_types = [args.entity_type] if args.entity_type else list(TRANSLATABLE_TABLES)
    rows = []
    totals = {"scanned": 0, "translated": 0, "skipped_empty": 0}
    if args.fixture:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        if fixture.get("site") and fixture["site"] != args.site:
            raise SystemExit("fixture site does not match --site")
        candidates = fixture["candidates"]
        target_locales = [fixture.get("target_locale", "sv")]
        repo = connection = engine = None
        dry_run = True
    else:
        dsn = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL", "").strip()
        if not dsn:
            raise SystemExit("REPAIRBASE_SECURITY_TEST_DB_URL is required")
        approval = None
        if args.environment == "production":
            approval = production_approval_from_env(
                command_flag=True, supplied_token=args.production_token
            )
        assert_configured_development_target(
            dsn,
            app_env=args.environment,
            operation="read" if args.dry_run else "write",
            approval=approval,
        )
        connection = psycopg2.connect(dsn)
        repo = TranslationRepository(connection)
        if not repo.lock(args.site, args.environment):
            raise SystemExit("translation lock is already held")
        if args.locale:
            target_locales = [args.locale]
        else:
            with connection.cursor() as cur:
                target_locales = _site_target_locales(cur, args.site)
        connection.rollback()
        dry_run = args.dry_run
        if not dry_run:
            import anthropic

            engine = TranslationEngine(anthropic.Anthropic())
            repo.start_run(run_id, args.site, args.environment)
            connection.commit()
    try:
        for target_locale in target_locales:
            for entity_type in entity_types:
                cfg = TRANSLATABLE_TABLES[entity_type]
                if args.fixture:
                    items = [
                        c
                        for c in candidates
                        if c["entity_type"] == entity_type
                    ]
                else:
                    items = repo.candidates(
                        entity_type,
                        source_locale=args.source_locale,
                        target_locale=target_locale,
                        limit=args.batch_size,
                        brand=args.brand,
                        category=args.category,
                    )
                for row in items:
                    totals["scanned"] += 1
                    entity_id = row["entity_id"]
                    src_hash = source_content_hash(row, cfg["fields"])
                    if dry_run:
                        rows.append(
                            {
                                "entity_type": entity_type,
                                "entity_id": entity_id,
                                "target_locale": target_locale,
                                "would_translate": True,
                            }
                        )
                        continue
                    if not repo.lock(
                        args.site, args.environment, f"{entity_type}:{entity_id}:{target_locale}"
                    ):
                        rows.append(
                            {
                                "entity_type": entity_type,
                                "entity_id": entity_id,
                                "target_locale": target_locale,
                                "status": "lock_conflict",
                            }
                        )
                        continue
                    try:
                        values = engine.translate(
                            row,
                            cfg["fields"],
                            source_locale=args.source_locale,
                            target_locale=target_locale,
                        )
                        if not values:
                            totals["skipped_empty"] += 1
                            rows.append(
                                {
                                    "entity_type": entity_type,
                                    "entity_id": entity_id,
                                    "target_locale": target_locale,
                                    "status": "skipped_empty_source",
                                }
                            )
                            continue
                        slug = (
                            build_slug(entity_type, entity_id, target_locale)
                            if cfg["has_slug"]
                            else None
                        )
                        repo.persist(
                            entity_type, entity_id, target_locale, values, src_hash, slug=slug
                        )
                        repo.publish_source_if_draft(entity_type, entity_id, args.source_locale)
                        repo.publish_guide_parent_if_ready(entity_type, entity_id)
                        connection.commit()
                        totals["translated"] += 1
                        rows.append(
                            {
                                "entity_type": entity_type,
                                "entity_id": entity_id,
                                "target_locale": target_locale,
                                "status": "translated",
                                "fields": list(values),
                            }
                        )
                    except Exception as error:
                        connection.rollback()
                        rows.append(
                            {
                                "entity_type": entity_type,
                                "entity_id": entity_id,
                                "target_locale": target_locale,
                                "status": "failed",
                                "error": f"{type(error).__name__}: {error}",
                            }
                        )
                    finally:
                        repo.unlock(
                            args.site, args.environment, f"{entity_type}:{entity_id}:{target_locale}"
                        )
    finally:
        if repo and not args.fixture:
            if not dry_run:
                repo.finish_run(run_id, totals)
                connection.commit()
            repo.unlock(args.site, args.environment)
            connection.close()
    report = {
        "run_id": run_id,
        "worker": "translation",
        "version": "1.0.0",
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "dry_run": dry_run,
        **totals,
        "items": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jp = args.output_dir / f"{run_id}.json"
    mp = args.output_dir / f"{run_id}.md"
    jp.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    mp.write_text(
        f"# Translation\n\nRun: `{run_id}`\n\n- Scanned: {totals['scanned']}\n- Translated: {totals['translated']}\n- Skipped (empty source): {totals['skipped_empty']}\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "run_id": run_id,
                "status": "completed",
                "dry_run": dry_run,
                **totals,
                "reports": [str(jp), str(mp)],
            },
            sort_keys=True,
        )
    )
    return 0
