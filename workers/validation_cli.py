from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from uuid import uuid4

import psycopg2

from config.target_safety import assert_safe_target
from workers.content_validation import (
    RULESET_ID,
    RULESET_VERSION,
    ValidationEngine,
    _hash,
    _steps,
)
from workers.validation_repository import ValidationRepository


def run(args):
    if args.environment == "production":
        raise SystemExit("content validation production execution is not enabled")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    if args.ruleset != RULESET_ID:
        raise SystemExit(f"unsupported ruleset: {args.ruleset}")
    started = datetime.now(timezone.utc)
    run_id = str(uuid4())
    repo = connection = None
    locked = []
    if args.fixture:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        drafts = [_fixture_draft(x) for x in fixture["drafts"]]
        drafts = _filter(drafts, args)[: args.batch_size]
        dry_run = True
    else:
        dsn = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL", "").strip()
        if not dsn:
            raise SystemExit("REPAIRBASE_SECURITY_TEST_DB_URL is required")
        assert_safe_target(
            dsn, app_env=args.environment, operation="read" if args.dry_run else "write"
        )
        connection = psycopg2.connect(dsn)
        repo = ValidationRepository(connection)
        if not repo.lock(args.site, args.environment):
            raise SystemExit("content-validation lock is already held")
        drafts = repo.drafts(
            args.site,
            args.environment,
            args.batch_size,
            _filters(args),
            args.include_blocked,
        )
        connection.rollback()
        dry_run = args.dry_run
        if not dry_run:
            repo.start_worker_run(run_id, args.site, args.environment)
            connection.commit()
    rows = []
    try:
        for draft in drafts:
            key = f"{draft['id']}:{draft['content_hash']}:{RULESET_VERSION}"
            if repo and not repo.lock(args.site, args.environment, key):
                rows.append(
                    {"draft_id": draft["id"], "blocked": "validation_lock_held"}
                )
                continue
            if repo:
                locked.append(key)
            context = deepcopy(draft.pop("validation_context", {}))
            before = deepcopy(draft)
            if repo:
                context["existing_drafts"] = repo.existing_drafts(draft)
                connection.rollback()
            result = ValidationEngine().validate(draft, context)
            if draft != before:
                raise RuntimeError("validator mutated draft content")
            if args.result and result["overall_result"] != args.result:
                continue
            persistence = {"created": 0, "deduplicated": 0}
            if repo and not dry_run:
                persistence = repo.persist(
                    run_id, args.site, args.environment, draft, result
                )
                connection.commit()
            rows.append(
                {"draft_id": draft["id"], "result": result, "persistence": persistence}
            )
    finally:
        if repo:
            summary = _summary(rows, len(drafts))
            if not dry_run:
                repo.finish_worker_run(run_id, summary)
                connection.commit()
            for key in locked:
                repo.unlock(args.site, args.environment, key)
            repo.unlock(args.site, args.environment)
            connection.close()
    report = {
        "run_id": run_id,
        "worker": "content-validation",
        "version": "1.0.0",
        "ruleset": args.ruleset,
        "ruleset_version": RULESET_VERSION,
        "dry_run": dry_run,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        **_summary(rows, len(drafts)),
        "items": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{run_id}.json"
    md_path = args.output_dir / f"{run_id}.md"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        "# Content Validation & Safety\n\n"
        + "\n".join(
            f"- {key.replace('_', ' ').title()}: {value}"
            for key, value in _summary(rows, len(drafts)).items()
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                **_summary(rows, len(drafts)),
                "run_id": run_id,
                "dry_run": dry_run,
                "reports": [str(json_path), str(md_path)],
            },
            sort_keys=True,
        )
    )
    outcomes = [row["result"]["overall_result"] for row in rows if "result" in row]
    return (
        3
        if "fail" in outcomes
        else (
            2
            if "needs_review" in outcomes
            else (4 if any("blocked" in row for row in rows) else 0)
        )
    )


def _fixture_draft(value):
    draft = deepcopy(value)
    draft.setdefault("site_id", "fixture-site")
    draft.setdefault("environment", "development")
    draft.setdefault("backlog_item_id", draft["id"])
    draft.setdefault("entity_type", "model")
    draft.setdefault("entity_id", str(draft["id"]))
    draft.setdefault("locale", "en")
    draft.setdefault("template_version", "1.0.0")
    draft.setdefault("risk_level", "low")
    draft.setdefault("status", "assembled")
    draft["rendered_content"] = {
        s["section_key"]: s["content"] for s in draft["sections"]
    }
    draft["content_hash"] = draft.get("content_hash") or _hash(
        draft["rendered_content"]
    )
    for existing in draft.get("validation_context", {}).get("existing_drafts", []):
        if existing.get("procedure_hash") == "PLACEHOLDER":
            existing["procedure_hash"] = _hash(_steps(draft))
    return draft


def _filters(args):
    return {
        key: getattr(args, key)
        for key in (
            "draft_id",
            "backlog_id",
            "entity_type",
            "locale",
            "draft_type",
            "risk_level",
        )
    }


def _filter(drafts, args):
    return [
        draft
        for draft in drafts
        if all(
            value is None or str(draft.get(key)) == str(value)
            for key, value in _filters(args).items()
        )
    ]


def _summary(rows, read):
    results = [row["result"] for row in rows if "result" in row]
    counts = Counter(result["overall_result"] for result in results)
    reasons = Counter(
        issue["reason_code"] for result in results for issue in result["issues"]
    )
    return {
        "drafts_read": read,
        "drafts_validated": len(results),
        "passed": counts["pass"],
        "needs_review": counts["needs_review"],
        "failed": counts["fail"],
        "safety_findings": sum(len(result["safety_findings"]) for result in results),
        "duplication_findings": sum(
            len(result["duplication_findings"]) for result in results
        ),
        "unsupported_claims": reasons["missing_evidence"]
        + reasons["unsupported_claim"],
        "stale_translations": reasons["stale_translation"],
        "blocked": sum("blocked" in row for row in rows),
    }
