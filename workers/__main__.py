from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import psycopg2

from config.target_safety import assert_safe_target
from workers.cube_coverage import CoverageEngine, WORKER_NAME, WORKER_VERSION, write_report
from workers.cube_repository import CubeRepository


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m workers")
    sub = root.add_subparsers(dest="worker", required=True)
    cmd = sub.add_parser("cube-coverage", help="inventory the frozen content cube and build backlog")
    cmd.add_argument("--site", required=True)
    cmd.add_argument("--environment", default="development", choices=("development", "staging", "production"))
    cmd.add_argument("--scope", default="active", choices=("active", "new"))
    cmd.add_argument("--dry-run", action="store_true")
    cmd.add_argument("--batch-size", type=int, default=500)
    cmd.add_argument("--locale")
    cmd.add_argument("--brand")
    cmd.add_argument("--category")
    cmd.add_argument("--finding-type")
    cmd.add_argument("--rebuild-backlog", action="store_true")
    cmd.add_argument("--fixture", type=Path, help="offline deterministic input; implies no database writes")
    cmd.add_argument("--output-dir", type=Path, default=Path("reports/cube-coverage"))
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    if args.environment == "production":
        raise SystemExit("cube-coverage production execution is not enabled")
    if args.dry_run and args.scope == "new" and not args.fixture:
        raise SystemExit("--scope new is a persistent operation and cannot be combined with --dry-run")
    started = datetime.now(timezone.utc)
    run_id = str(uuid4())
    filters = {"locale":args.locale,"brand":args.brand,"category":args.category,"finding_type":args.finding_type}
    if args.fixture:
        data = json.loads(args.fixture.read_text(encoding="utf-8"))
        persisted = {"findings_created":0,"findings_reopened":0,"findings_resolved":0,"backlog_created":0}
        dry_run = True
    else:
        dsn = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL", "").strip()
        if not dsn:
            raise SystemExit("REPAIRBASE_SECURITY_TEST_DB_URL is required")
        assert_safe_target(dsn, app_env=args.environment, operation="write" if not args.dry_run else "read")
        connection = psycopg2.connect(dsn)
        repo = CubeRepository(connection)
        try:
            snapshot = repo.snapshot(args.site, args.environment, create=args.scope == "new", force_new=args.scope == "new")
            connection.commit()
            if not repo.lock(args.site,args.environment,snapshot["id"]):
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
        persisted = repo.persist(run_id, snapshot, evaluated, site_id=args.site, environment=args.environment, rebuild_backlog=args.rebuild_backlog)
        connection.commit()
    if not args.fixture:
        repo.unlock(args.site,args.environment,snapshot["id"])
        connection.close()
    report = {"run_id":run_id,"worker_name":WORKER_NAME,"worker_version":WORKER_VERSION,"started_at":started.isoformat(),
              "finished_at":datetime.now(timezone.utc).isoformat(),"status":"completed","dry_run":dry_run,
              **evaluated, **(persisted or {}), "errors":[], "warnings":[]}
    report["scope_snapshot"] = report.pop("scope")
    report["coverage_before"] = report["metrics"]
    report["coverage_after"] = report["metrics"]
    report["backlog_blocked"] = sum(x["status"] == "blocked" for x in report["backlog"])
    report["backlog_queued"] = sum(x["status"] == "queued" for x in report["backlog"])
    paths = write_report(report,args.output_dir)
    print(json.dumps({"run_id":run_id,"status":"completed","dry_run":dry_run,"reports":[str(x) for x in paths],
                      "findings":len(report["findings"]),"backlog":len(report["backlog"])},sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
