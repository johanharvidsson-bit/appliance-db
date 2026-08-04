from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg2

from config.target_safety import assert_configured_development_target
from workers.cube_coverage import (
    CoverageEngine,
    WORKER_NAME,
    WORKER_VERSION,
    write_report,
)
from workers.cube_repository import CubeRepository


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m workers")
    sub = root.add_subparsers(dest="worker", required=True)
    cmd = sub.add_parser(
        "cube-coverage", help="inventory the frozen content cube and build backlog"
    )
    cmd.add_argument("--site", required=True)
    cmd.add_argument(
        "--environment",
        default="development",
        choices=("development", "staging", "production"),
    )
    cmd.add_argument("--scope", default="active", choices=("active", "new"))
    cmd.add_argument("--dry-run", action="store_true")
    cmd.add_argument("--batch-size", type=int, default=500)
    cmd.add_argument("--locale")
    cmd.add_argument("--brand")
    cmd.add_argument("--category")
    cmd.add_argument("--finding-type")
    cmd.add_argument("--rebuild-backlog", action="store_true")
    cmd.add_argument(
        "--fixture",
        type=Path,
        help="offline deterministic input; implies no database writes",
    )
    cmd.add_argument("--output-dir", type=Path, default=Path("reports/cube-coverage"))
    discovery = sub.add_parser(
        "source-discovery", help="discover source URLs for queued backlog items"
    )
    discovery.add_argument("--site", required=True)
    discovery.add_argument(
        "--environment",
        default="development",
        choices=("development", "staging", "production"),
    )
    discovery.add_argument("--dry-run", action="store_true")
    discovery.add_argument("--batch-size", type=int, default=25)
    discovery.add_argument("--locale")
    discovery.add_argument("--action-type")
    discovery.add_argument("--entity-type")
    discovery.add_argument("--timeout", type=float, default=10.0)
    discovery.add_argument("--retries", type=int, default=2)
    discovery.add_argument("--rate-limit", type=float, default=1.0)
    discovery.add_argument("--fixture", type=Path)
    discovery.add_argument(
        "--output-dir", type=Path, default=Path("reports/source-discovery")
    )
    ingestion = sub.add_parser(
        "source-ingestion", help="fetch accepted sources and extract candidate facts"
    )
    ingestion.add_argument("--site", required=True)
    ingestion.add_argument(
        "--environment",
        default="development",
        choices=("development", "staging", "production"),
    )
    ingestion.add_argument("--dry-run", action="store_true")
    ingestion.add_argument("--batch-size", type=int, default=10)
    ingestion.add_argument("--timeout", type=float, default=15.0)
    ingestion.add_argument("--retries", type=int, default=2)
    ingestion.add_argument("--rate-limit", type=float, default=1.0)
    ingestion.add_argument("--source-candidate-id", type=int)
    ingestion.add_argument("--backlog-id", type=int)
    ingestion.add_argument("--source-type")
    ingestion.add_argument("--max-document-bytes", type=int, default=15_000_000)
    ingestion.add_argument("--reprocess", action="store_true")
    ingestion.add_argument("--fixture", type=Path)
    ingestion.add_argument(
        "--storage-dir", type=Path, default=Path("data/source-ingestion")
    )
    ingestion.add_argument(
        "--output-dir", type=Path, default=Path("reports/source-ingestion")
    )
    integration = sub.add_parser(
        "knowledge-integration",
        help="resolve candidate facts into reviewable proposals",
    )
    integration.add_argument("--site", required=True)
    integration.add_argument(
        "--environment",
        default="development",
        choices=("development", "staging", "production"),
    )
    integration.add_argument("--dry-run", action="store_true")
    integration.add_argument("--batch-size", type=int, default=50)
    integration.add_argument("--candidate-fact-id", type=int)
    integration.add_argument("--backlog-id", type=int)
    integration.add_argument("--fact-type")
    integration.add_argument("--proposal-type")
    integration.add_argument("--locale")
    integration.add_argument("--brand", type=int)
    integration.add_argument("--category", type=int)
    integration.add_argument("--min-confidence", type=int, default=0)
    integration.add_argument("--reprocess", action="store_true")
    integration.add_argument("--fixture", type=Path)
    integration.add_argument(
        "--output-dir", type=Path, default=Path("reports/knowledge-integration")
    )
    apply_cmd = sub.add_parser(
        "apply-integration", help="apply manually approved integration proposals"
    )
    apply_cmd.add_argument("--site", required=True)
    apply_cmd.add_argument(
        "--environment",
        default="development",
        choices=("development", "staging", "production"),
    )
    apply_cmd.add_argument("--dry-run", action="store_true")
    apply_cmd.add_argument("--batch-size", type=int, default=1)
    apply_cmd.add_argument("--proposal-id", type=int)
    apply_cmd.add_argument("--proposal-type")
    apply_cmd.add_argument("--risk-level")
    apply_cmd.add_argument("--reviewed-by")
    apply_cmd.add_argument("--max-risk", default="medium", choices=("low", "medium"))
    apply_cmd.add_argument("--retry-failed", action="store_true")
    apply_cmd.add_argument("--confirm", action="store_true")
    apply_cmd.add_argument("--fixture", type=Path)
    apply_cmd.add_argument(
        "--output-dir", type=Path, default=Path("reports/apply-integration")
    )
    assembly = sub.add_parser(
        "content-assembly", help="assemble integrated facts into internal drafts"
    )
    assembly.add_argument("--site", required=True)
    assembly.add_argument(
        "--environment",
        default="development",
        choices=("development", "staging", "production"),
    )
    assembly.add_argument("--dry-run", action="store_true")
    assembly.add_argument("--batch-size", type=int, default=25)
    assembly.add_argument("--backlog-id", type=int)
    assembly.add_argument("--entity-type")
    assembly.add_argument("--entity-id")
    assembly.add_argument("--locale")
    assembly.add_argument("--draft-type")
    assembly.add_argument("--template-id")
    assembly.add_argument(
        "--risk-level", choices=("low", "medium", "high", "safety_review")
    )
    assembly.add_argument("--reassemble", action="store_true")
    assembly.add_argument("--fixture", type=Path)
    assembly.add_argument(
        "--output-dir", type=Path, default=Path("reports/content-assembly")
    )
    validation = sub.add_parser(
        "content-validation", help="validate immutable content drafts"
    )
    validation.add_argument("--site", required=True)
    validation.add_argument(
        "--environment",
        default="development",
        choices=("development", "staging", "production"),
    )
    validation.add_argument("--dry-run", action="store_true")
    validation.add_argument("--batch-size", type=int, default=25)
    validation.add_argument("--draft-id", type=int)
    validation.add_argument("--backlog-id", type=int)
    validation.add_argument("--entity-type")
    validation.add_argument("--locale")
    validation.add_argument("--draft-type")
    validation.add_argument(
        "--risk-level", choices=("low", "medium", "high", "safety_review")
    )
    validation.add_argument("--result", choices=("pass", "needs_review", "fail"))
    validation.add_argument("--ruleset", default="content_validation_v1")
    validation.add_argument("--revalidate", action="store_true")
    validation.add_argument("--include-blocked", action="store_true")
    validation.add_argument("--fixture", type=Path)
    validation.add_argument(
        "--output-dir", type=Path, default=Path("reports/content-validation")
    )
    review = sub.add_parser(
        "source-review", help="manually review one source candidate"
    )
    review.add_argument("--site", required=True)
    review.add_argument(
        "--environment",
        default="development",
        choices=("development", "staging", "production"),
    )
    actions = review.add_subparsers(dest="review_action", required=True)
    listing = actions.add_parser("list")
    listing.add_argument("--limit", type=int, default=25)
    showing = actions.add_parser("show")
    showing.add_argument("--source-candidate-id", type=int, required=True)
    deciding = actions.add_parser("decide")
    deciding.add_argument("--source-candidate-id", type=int, required=True)
    deciding.add_argument("--decision", required=True, choices=("accepted", "rejected"))
    deciding.add_argument("--reviewer", required=True)
    deciding.add_argument("--reason", required=True)
    deciding.add_argument("--dry-run", action="store_true")
    deciding.add_argument("--confirm", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.worker == "source-discovery":
        from workers.source_cli import run

        return run(args)
    if args.worker == "source-ingestion":
        from workers.ingestion_cli import run

        return run(args)
    if args.worker == "knowledge-integration":
        from workers.integration_cli import run

        return run(args)
    if args.worker == "apply-integration":
        from workers.apply_cli import run

        return run(args)
    if args.worker == "content-assembly":
        from workers.assembly_cli import run

        return run(args)
    if args.worker == "content-validation":
        from workers.validation_cli import run

        return run(args)
    if args.worker == "source-review":
        from workers.source_review_cli import run

        return run(args)
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    if args.environment == "production":
        raise SystemExit("cube-coverage production execution is not enabled")
    if args.dry_run and args.scope == "new" and not args.fixture:
        raise SystemExit(
            "--scope new is a persistent operation and cannot be combined with --dry-run"
        )
    started = datetime.now(timezone.utc)
    run_id = str(uuid4())
    filters = {
        "locale": args.locale,
        "brand": args.brand,
        "category": args.category,
        "finding_type": args.finding_type,
    }
    if args.fixture:
        data = json.loads(args.fixture.read_text(encoding="utf-8"))
        persisted = {
            "findings_created": 0,
            "findings_reopened": 0,
            "findings_resolved": 0,
            "backlog_created": 0,
        }
        dry_run = True
    else:
        dsn = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL", "").strip()
        if not dsn:
            raise SystemExit("REPAIRBASE_SECURITY_TEST_DB_URL is required")
        assert_configured_development_target(
            dsn,
            app_env=args.environment,
            operation="write" if not args.dry_run else "read",
        )
        connection = psycopg2.connect(dsn)
        repo = CubeRepository(connection)
        try:
            snapshot = repo.snapshot(
                args.site,
                args.environment,
                create=args.scope == "new",
                force_new=args.scope == "new",
            )
            connection.commit()
            if not repo.lock(args.site, args.environment, snapshot["id"]):
                raise SystemExit("cube-coverage lock is already held")
            data = repo.read_content(snapshot)
            connection.rollback()
            dry_run = args.dry_run
            persisted = None
        except Exception:
            connection.close()
            raise
    evaluated = CoverageEngine().evaluate(data, filters=filters)
    if not args.fixture and not dry_run:
        persisted = repo.persist(
            run_id,
            snapshot,
            evaluated,
            site_id=args.site,
            environment=args.environment,
            rebuild_backlog=args.rebuild_backlog,
        )
        connection.commit()
    if not args.fixture:
        repo.unlock(args.site, args.environment, snapshot["id"])
        connection.close()
    report = {
        "run_id": run_id,
        "worker_name": WORKER_NAME,
        "worker_version": WORKER_VERSION,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "dry_run": dry_run,
        **evaluated,
        **(persisted or {}),
        "errors": [],
        "warnings": [],
    }
    report["scope_snapshot"] = report.pop("scope")
    report["coverage_before"] = report["metrics"]
    report["coverage_after"] = report["metrics"]
    report["backlog_blocked"] = sum(x["status"] == "blocked" for x in report["backlog"])
    report["backlog_queued"] = sum(x["status"] == "queued" for x in report["backlog"])
    paths = write_report(report, args.output_dir)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "status": "completed",
                "dry_run": dry_run,
                "reports": [str(x) for x in paths],
                "findings": len(report["findings"]),
                "backlog": len(report["backlog"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
