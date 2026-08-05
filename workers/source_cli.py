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
from workers.source_discovery import (
    DiscoveryEngine,
    RateLimitedRetryProvider,
    SearchResult,
    SerperSearchProvider,
    build_query,
    candidate_dicts,
)
from workers.source_repository import SourceRepository


def run(args) -> int:
    started = datetime.now(timezone.utc)
    run_id = str(uuid4())
    rows = []
    totals = {"scanned": 0, "created": 0, "updated": 0, "not_found": 0, "auto_accepted": 0}
    if args.fixture:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        items = fixture["backlog"]
        fixture_results = {
            key: [SearchResult(**x) for x in value]
            for key, value in fixture["results"].items()
        }
        repo = connection = None
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
        repo = SourceRepository(connection)
        if not repo.lock(args.site, args.environment):
            raise SystemExit("source-discovery lock is already held")
        items = repo.backlog(
            args.site,
            args.environment,
            limit=args.batch_size,
            filters={
                "locale": args.locale,
                "action_type": args.action_type,
                "entity_type": args.entity_type,
            },
        )
        connection.rollback()
        dry_run = args.dry_run
        provider = RateLimitedRetryProvider(
            SerperSearchProvider(os.getenv("SERPER_API_KEY", "")),
            delay_seconds=args.rate_limit,
            retries=args.retries,
        )
    try:
        for item in items:
            query = build_query(item)
            cache_hit = False
            if args.fixture:
                results = fixture_results.get(str(item["backlog_id"]), [])
                method = "fixture"
            else:
                cached = repo.cached(provider.name, query)
                if cached is not None:
                    results = [SearchResult(**x) for x in cached]
                    cache_hit = True
                    method = f"{provider.name}:cache"
                else:
                    results = provider.search(query, timeout=args.timeout)
                    method = provider.name
                    if not dry_run:
                        repo.store_cache(
                            provider.name, query, [x.__dict__ for x in results]
                        )
                        connection.commit()
            candidates = candidate_dicts(
                DiscoveryEngine().discover(item, results, method=method)
            )
            stats = (
                {"created": 0, "updated": 0, "not_found": int(not candidates)}
                if dry_run
                else repo.persist(args.site, args.environment, item, candidates)
            )
            if not dry_run:
                connection.commit()
            totals["scanned"] += 1
            for key in ("created", "updated", "not_found"):
                totals[key] += stats[key]
            totals["auto_accepted"] += stats.get("auto_accepted", 0)
            rows.append(
                {
                    "backlog_id": item["backlog_id"],
                    "query": query,
                    "cache_hit": cache_hit,
                    "candidates": candidates,
                    "not_found": not candidates,
                }
            )
    finally:
        if connection:
            repo.unlock(args.site, args.environment)
            connection.close()
    report = {
        "run_id": run_id,
        "worker": "source-discovery",
        "version": "1.0.0",
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "dry_run": dry_run,
        "backlog_scanned": totals["scanned"],
        "source_candidates": sum(len(x["candidates"]) for x in rows),
        "accepted": totals["auto_accepted"],
        "rejected": 0,
        "not_found": totals["not_found"],
        "created": totals["created"],
        "updated": totals["updated"],
        "items": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jp = args.output_dir / f"{run_id}.json"
    mp = args.output_dir / f"{run_id}.md"
    jp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mp.write_text(
        f"# Source Discovery\n\nRun: `{run_id}`\n\n- Backlog scanned: {report['backlog_scanned']}\n- Candidates: {report['source_candidates']}\n- Accepted: {report['accepted']}\n- Rejected: 0\n- Not found: {report['not_found']}\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "run_id": run_id,
                "status": "completed",
                "dry_run": dry_run,
                "backlog_scanned": report["backlog_scanned"],
                "source_candidates": report["source_candidates"],
                "not_found": report["not_found"],
                "reports": [str(jp), str(mp)],
            },
            sort_keys=True,
        )
    )
    return 0
