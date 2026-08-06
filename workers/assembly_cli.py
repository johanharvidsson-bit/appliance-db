from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import json
import os
from uuid import uuid4
import psycopg2
from config.target_safety import (
    assert_configured_development_target,
    production_approval_from_env,
)
from workers.assembly_repository import AssemblyRepository
from workers.content_assembly import AssemblyEngine


def run(args):
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    started = datetime.now(timezone.utc)
    run_id = str(uuid4())
    repo = connection = None
    locked = []
    rows = []
    if args.fixture:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        if fixture.get("site") and fixture["site"] != args.site:
            raise SystemExit("fixture site does not match --site")
        items = [
            x
            for x in fixture["items"]
            if x.get("eligible", True)
            and x.get("upstream_state")
            in {"facts_integrated", "ready_for_content_assembly", "apply_succeeded"}
        ]
        items = _filters(items, args)[: args.batch_size]
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
        repo = AssemblyRepository(connection)
        if not repo.lock(args.site, args.environment):
            raise SystemExit("content-assembly lock is already held")
        raw = repo.items(
            args.site,
            args.environment,
            args.batch_size,
            {
                "backlog_id": args.backlog_id,
                "entity_type": args.entity_type,
                "entity_id": args.entity_id,
                "locale": args.locale,
            },
            args.reassemble,
        )
        items = [_domain_item(x) for x in raw]
        connection.rollback()
        dry_run = args.dry_run
        if not dry_run:
            repo.start_run(run_id, args.site, args.environment)
            connection.commit()
    try:
        for item in items:
            lock_key = f"{item['backlog_id']}:{item['entity_type']}:{item['entity_id']}:{item['locale']}:{args.draft_type or item['action_type']}"
            if repo and not repo.lock(args.site, args.environment, lock_key):
                rows.append({"item": item, "error": "assembly_lock_held"})
                continue
            if repo:
                locked.append(lock_key)
            try:
                draft = AssemblyEngine().assemble(item, args.template_id)
                if args.draft_type and draft["draft_type"] != args.draft_type:
                    continue
                if args.risk_level and draft["risk_level"] != args.risk_level:
                    continue
                persisted = {
                    "created": 0,
                    "deduplicated": 0,
                    "superseded": 0,
                    "draft_id": None,
                }
                if repo and not dry_run:
                    persisted = repo.persist(
                        args.site, args.environment, run_id, draft, args.reassemble
                    )
                    connection.commit()
                rows.append(
                    {
                        "backlog_id": item["backlog_id"],
                        "draft": draft,
                        "persistence": persisted,
                    }
                )
            except Exception as exc:
                if connection:
                    connection.rollback()
                rows.append({"backlog_id": item["backlog_id"], "error": str(exc)})
    finally:
        if repo:
            if not dry_run:
                repo.finish_run(run_id, _summary(rows))
                connection.commit()
            for key in locked:
                repo.unlock(args.site, args.environment, key)
            repo.unlock(args.site, args.environment)
            connection.close()
    report = {
        "run_id": run_id,
        "worker": "content-assembly",
        "version": "1.0.0",
        "status": "completed",
        "dry_run": dry_run,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        **_summary(rows),
        "items": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jp = args.output_dir / f"{run_id}.json"
    mp = args.output_dir / f"{run_id}.md"
    jp.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    keys = (
        "backlog_items_read",
        "eligible_items",
        "drafts_created",
        "drafts_partial",
        "drafts_blocked",
        "sections_created",
        "sections_omitted",
        "missing_fact_issues",
        "conflict_issues",
        "safety_review_drafts",
        "same_as_existing",
        "superseded_drafts",
    )
    mp.write_text(
        "# Content Assembly\n\n"
        + "\n".join(f"- {k.replace('_', ' ').title()}: {report[k]}" for k in keys)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "run_id": run_id,
                "status": "completed",
                "dry_run": dry_run,
                **{k: report[k] for k in keys},
                "reports": [str(jp), str(mp)],
            },
            sort_keys=True,
        )
    )
    if any(r.get("error") for r in rows):
        return 4
    drafts = [r["draft"] for r in rows if "draft" in r]
    return (
        3
        if drafts and all(d["status"] == "blocked" for d in drafts)
        else (
            2
            if drafts and all(d["status"] in {"blocked", "partial"} for d in drafts)
            else 0
        )
    )


def _filters(items, args):
    mapping = (
        ("backlog_id", args.backlog_id),
        ("entity_type", args.entity_type),
        ("entity_id", args.entity_id),
        ("locale", args.locale),
    )
    return [
        x
        for x in items
        if all(v is None or str(x.get(k)) == str(v) for k, v in mapping)
    ]


def _domain_item(row):
    facts = []

    def add(key, value, evidence=None):
        if value not in (None, "", [], {}):
            facts.append(
                {
                    "key": key,
                    "value": value,
                    "integration_status": "integrated",
                    "evidence": evidence or [],
                }
            )

    # A guide created via apply-integration's create_reviewed_guide is
    # attached to whichever backlog item happened to spawn it (e.g. a
    # translate_error_code item) - that item's own entity is not what this
    # draft is actually about once a guide exists. Reattribute to the guide
    # itself so the resulting draft, and its "title" fact, describe the
    # guide rather than the originating error_code/fault.
    guide_step_facts = [
        f for f in row.get("integrated_facts", []) if f.get("fact_type") == "guide_step"
    ]
    is_guide_resolution = row.get("resolved_guide_id") is not None and bool(guide_step_facts)
    entity_type = "guide" if is_guide_resolution else row["entity_type"]
    entity_id = str(row["resolved_guide_id"]) if is_guide_resolution else row["entity_id"]
    entity_name = row["resolved_guide_title"] if is_guide_resolution else row.get("entity_name")
    name_key = {
        "model": "model_name",
        "error_code": "code",
        "fault": "symptom",
        "guide": "title",
    }.get(entity_type, "title")
    # The guide's title is a generated label, not an extracted fact - it makes
    # no claim beyond "this is a guide for X", already established by the
    # evidence backing its steps. Reuse that evidence rather than the
    # generally-empty legacy entity_evidence, so the label isn't blocked as
    # an unevidenced claim while still never inventing anything unevidenced.
    context_evidence = (
        [
            {
                "candidate_fact_id": f.get("candidate_fact_id"),
                "source_document_id": f.get("source_document_id"),
                "fact_type": f.get("fact_type"),
                "locator": {
                    "source_locator": f.get("locator"),
                    "page_number": f.get("page_number"),
                },
            }
            for f in guide_step_facts
        ]
        if is_guide_resolution
        else (row.get("entity_evidence") or [])
    )
    add(name_key, entity_name, context_evidence)
    add("brand", row.get("brand_name"), context_evidence)
    add("category", row.get("category_name"), context_evidence)
    specs = {}
    specs_evidence = []
    variants = []
    variants_evidence = []
    steps = []
    steps_evidence = []
    for fact in row.get("integrated_facts", []):
        evidence = [
            {
                "candidate_fact_id": fact.get("candidate_fact_id"),
                "source_document_id": fact.get("source_document_id"),
                "fact_type": fact.get("fact_type"),
                "locator": {
                    "source_locator": fact.get("locator"),
                    "page_number": fact.get("page_number"),
                },
            }
        ]
        value = fact.get("value")
        proposed = fact.get("proposed_value") or {}
        if fact.get("fact_type") == "specification":
            specs[fact.get("predicate") or proposed.get("field")] = proposed.get(
                "value", value
            )
            specs_evidence.extend(evidence)
        elif fact.get("predicate") == "variant_code":
            variants.append(value)
            variants_evidence.extend(evidence)
        elif fact.get("fact_type") == "guide_step":
            steps.append(value)
            steps_evidence.extend(evidence)
        elif fact.get("fact_type") == "error_code" and isinstance(value, dict):
            add("code", value.get("code"), evidence)
            add("meaning", value.get("meaning"), evidence)
        elif proposed.get("field") in {"overview", "short_summary"}:
            add(
                proposed["field"],
                proposed.get("value") or proposed.get("source_value"),
                evidence,
            )
        elif proposed.get("field") == "description":
            add("meaning", proposed.get("value"), evidence)
    if specs:
        add("specifications", specs, specs_evidence)
    if variants:
        add("variants", variants, variants_evidence)
    if steps:
        add(
            "steps",
            sorted(
                steps,
                key=lambda x: x.get("step_number", 0) if isinstance(x, dict) else 0,
            ),
            steps_evidence,
        )
    return {
        "backlog_id": row["backlog_id"],
        "entity_type": entity_type,
        "entity_id": entity_id,
        "locale": row.get("locale") or "en",
        "action_type": row["action_type"],
        "upstream_state": "apply_succeeded",
        "facts": facts,
    }


def _summary(rows):
    drafts = [r["draft"] for r in rows if "draft" in r]
    sections = [s for d in drafts for s in d["sections"]]
    issues = [i for d in drafts for i in d["issues"]]
    return {
        "backlog_items_read": len(rows),
        "eligible_items": len(drafts),
        "drafts_created": sum(r.get("persistence", {}).get("created", 0) for r in rows),
        "drafts_generated": len(drafts),
        "drafts_partial": sum(d["status"] == "partial" for d in drafts),
        "drafts_blocked": sum(d["status"] == "blocked" for d in drafts),
        "sections_created": sum(
            s["section_status"] in {"assembled", "needs_review"} for s in sections
        ),
        "sections_omitted": sum(
            s["section_status"] == "omitted_no_data" for s in sections
        ),
        "missing_fact_issues": sum(
            i["issue_type"]
            in {
                "missing_required_fact",
                "insufficient_procedure",
                "missing_locale_source",
            }
            for i in issues
        ),
        "conflict_issues": sum(i["issue_type"] == "conflicting_fact" for i in issues),
        "safety_review_drafts": sum(d["risk_level"] == "safety_review" for d in drafts),
        "same_as_existing": sum(
            d["comparison_class"] == "same_as_existing" for d in drafts
        ),
        "superseded_drafts": sum(
            r.get("persistence", {}).get("superseded", 0) for r in rows
        ),
        "draft_types": dict(Counter(d["draft_type"] for d in drafts)),
        "locales": dict(Counter(d["locale"] for d in drafts)),
        "warnings": [],
        "errors": [r["error"] for r in rows if r.get("error")],
    }
