from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from uuid import uuid4

import psycopg2

from config.target_safety import assert_safe_target
from workers.integration_repository import IntegrationRepository
from workers.knowledge_integration import ResolutionEngine


def run(args):
    if args.environment == "production":
        raise SystemExit("knowledge integration production execution is not enabled")
    if args.batch_size < 1 or not 0 <= args.min_confidence <= 100:
        raise SystemExit("invalid knowledge integration limits")
    started = datetime.now(timezone.utc)
    run_id = str(uuid4())
    repo = connection = None
    locked = []
    results = []
    if args.fixture:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        if fixture.get("site") and fixture["site"] != args.site:
            raise SystemExit("fixture site does not match --site")
        facts = [
            x
            for x in fixture["facts"]
            if x["extraction_status"] in {"candidate", "needs_review", "conflicted"}
            and x.get("confidence", 0) >= args.min_confidence
        ]
        facts = _filter_facts(facts, args)[: args.batch_size]
        catalog = fixture["catalog"]
        dry_run = True
    else:
        dsn = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL", "").strip()
        if not dsn:
            raise SystemExit("REPAIRBASE_SECURITY_TEST_DB_URL is required")
        assert_safe_target(
            dsn, app_env=args.environment, operation="read" if args.dry_run else "write"
        )
        connection = psycopg2.connect(dsn)
        repo = IntegrationRepository(connection)
        if not repo.lock(args.site, args.environment):
            raise SystemExit("knowledge-integration lock is already held")
        facts = repo.facts(
            args.site,
            args.environment,
            limit=args.batch_size,
            filters={
                "candidate_fact_id": args.candidate_fact_id,
                "backlog_id": args.backlog_id,
                "fact_type": args.fact_type,
                "locale": args.locale,
                "brand": args.brand,
                "category": args.category,
                "min_confidence": args.min_confidence,
            },
            reprocess=args.reprocess,
        )
        catalog = repo.catalog(facts)
        connection.rollback()
        dry_run = args.dry_run
        if not dry_run:
            repo.start_run(run_id, args.site, args.environment)
            connection.commit()
    try:
        for fact in facts:
            if repo and not repo.lock(args.site, args.environment, fact["id"]):
                results.append(
                    {
                        "candidate_fact_id": fact["id"],
                        "backlog_item_id": fact["backlog_item_id"],
                        "processing_state": "lock_conflict",
                        "proposals": [],
                        "error": "fact_lock_held",
                    }
                )
                continue
            if repo:
                locked.append(fact["id"])
            result = ResolutionEngine().resolve(fact, catalog, args.proposal_type)
            persisted = {
                "created": 0,
                "deduplicated": 0,
                "conflicts": sum(len(x["conflicts"]) for x in result["proposals"]),
                "proposal_ids": [],
            }
            if repo and not dry_run:
                persisted = repo.persist(args.site, args.environment, run_id, result)
                connection.commit()
            result["persistence"] = persisted
            results.append(result)
    finally:
        if repo:
            summary = _summarize(results)
            if not dry_run:
                repo.finish_run(run_id, summary)
                connection.commit()
            for fact_id in locked:
                repo.unlock(args.site, args.environment, fact_id)
            repo.unlock(args.site, args.environment)
            connection.close()
    report = {
        "run_id": run_id,
        "worker": "knowledge-integration",
        "version": "1.0.0",
        "status": "completed",
        "dry_run": dry_run,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        **_summarize(results),
        "items": results,
        "warnings": [],
        "errors": [x["error"] for x in results if x.get("error")],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jp = args.output_dir / f"{run_id}.json"
    mp = args.output_dir / f"{run_id}.md"
    jp.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    keys = (
        "candidate_facts_read",
        "candidate_facts_matched",
        "unresolved_facts",
        "proposals_created",
        "proposals_needing_review",
        "blocked_proposals",
        "conflicts_created",
        "same_as_existing",
        "out_of_scope",
    )
    mp.write_text(
        "# Knowledge Integration\n\n"
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
                "proposals_generated": report["proposals_generated"],
                **{k: report[k] for k in keys},
                "reports": [str(jp), str(mp)],
            },
            sort_keys=True,
        )
    )
    return 0


def _filter_facts(facts, args):
    mapping = (
        ("id", args.candidate_fact_id),
        ("backlog_item_id", args.backlog_id),
        ("fact_type", args.fact_type),
        ("locale", args.locale),
        ("brand_id", args.brand),
        ("category_id", args.category),
    )
    return [
        fact
        for fact in facts
        if all(
            value is None or str(fact.get(key)) == str(value) for key, value in mapping
        )
    ]


def _summarize(results):
    proposals = [p for r in results for p in r["proposals"]]
    proposal_types = Counter(p["proposal_type"] for p in proposals)
    targets = Counter(t["target_entity_type"] for p in proposals for t in p["targets"])
    confidence = Counter(
        "95-100"
        if p["confidence"] >= 95
        else "80-94"
        if p["confidence"] >= 80
        else "60-79"
        if p["confidence"] >= 60
        else "below-60"
        for p in proposals
    )
    risk = Counter(p["risk_level"] for p in proposals)
    return {
        "candidate_facts_read": len(results),
        "candidate_facts_matched": sum(
            any(t["is_preferred"] for p in r["proposals"] for t in p["targets"])
            for r in results
        ),
        "unresolved_facts": sum(
            r["processing_state"]
            in {"no_matching_entity", "blocked_by_conflict", "needs_review"}
            for r in results
        ),
        "proposals_created": sum(r["persistence"]["created"] for r in results)
        if results and all("persistence" in r for r in results)
        else 0,
        "proposals_generated": len(proposals),
        "proposals_needing_review": sum(
            p["status"] == "needs_review" for p in proposals
        ),
        "blocked_proposals": sum(p["status"] == "blocked" for p in proposals),
        "conflicts_created": sum(len(p["conflicts"]) for p in proposals),
        "same_as_existing": sum(
            r["processing_state"] == "same_as_existing" for r in results
        ),
        "out_of_scope": sum(r["processing_state"] == "out_of_scope" for r in results),
        "proposal_types": dict(proposal_types),
        "target_entity_types": dict(targets),
        "confidence_distribution": dict(confidence),
        "risk_distribution": dict(risk),
        "deduplicated": sum(
            r.get("persistence", {}).get("deduplicated", 0) for r in results
        ),
    }
