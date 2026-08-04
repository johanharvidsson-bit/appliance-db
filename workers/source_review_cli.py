from __future__ import annotations
from datetime import date, datetime
import json
import os
import psycopg2
from config.target_safety import assert_configured_development_target
from workers.source_review import SourceReviewRepository


def run(args):
    if args.environment != "development":
        raise SystemExit("source review is development-only")
    if args.review_action == "decide" and not args.confirm and not args.dry_run:
        raise SystemExit("source-review decide requires --confirm or --dry-run")
    if args.review_action == "decide" and (
        not args.reviewer.strip() or not args.reason.strip()
    ):
        raise SystemExit("--reviewer and --reason are required")
    dsn = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL", "").strip()
    if not dsn:
        raise SystemExit("REPAIRBASE_SECURITY_TEST_DB_URL is required")
    assert_configured_development_target(
        dsn,
        app_env=args.environment,
        operation="read" if args.review_action != "decide" or args.dry_run else "write",
    )
    with psycopg2.connect(dsn) as connection:
        repo = SourceReviewRepository(connection)
        if args.review_action == "list":
            result = {"candidates": repo.list(args.site, args.environment, args.limit)}
        elif args.review_action == "show":
            result = repo.show(args.site, args.environment, args.source_candidate_id)
        elif args.dry_run:
            shown = repo.show(args.site, args.environment, args.source_candidate_id)
            result = {
                "candidate_id": shown["candidate"]["id"],
                "decision": args.decision,
                "dry_run": True,
            }
            connection.rollback()
        else:
            result = repo.decide(
                args.site,
                args.environment,
                args.source_candidate_id,
                args.decision,
                args.reviewer,
                args.reason,
            )
            connection.commit()
    print(
        json.dumps(
            result,
            default=lambda v: v.isoformat()
            if isinstance(v, (datetime, date))
            else str(v),
            sort_keys=True,
        )
    )
    return 0
