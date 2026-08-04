from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import json
import os
from uuid import uuid4
import psycopg2
from config.target_safety import assert_configured_development_target
from workers.apply_integration import ApplyBlocked, ApplyEngine, StaleProposal
from workers.apply_repository import ApplyRepository

EXIT = {"succeeded": 0, "blocked": 2, "stale": 3, "failed": 4}


class FixtureRepository:
    def __init__(self, proposals):
        self.items = {p["id"]: p for p in proposals}

    def proposals(self, *_, limit, filters, **__):
        rows = [p for p in self.items.values() if p.get("status") == "approved"]
        return [
            p["id"]
            for p in rows
            if all(v is None or str(p.get(k)) == str(v) for k, v in filters.items())
        ][:limit]

    from contextlib import contextmanager

    @contextmanager
    def proposal_transaction(self, pid):
        yield self.items[pid]


def run(args):
    if args.environment == "production":
        raise SystemExit("apply-integration production execution is not enabled")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    if not args.dry_run and not args.confirm:
        raise SystemExit("non-dry-run requires --confirm")
    run_id = str(uuid4())
    started = datetime.now(timezone.utc)
    connection = None
    if args.fixture:
        data = json.loads(args.fixture.read_text(encoding="utf-8"))
        repo = FixtureRepository(data["proposals"])
        dry_run = True
    else:
        dsn = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL", "").strip()
        if not dsn:
            raise SystemExit("REPAIRBASE_SECURITY_TEST_DB_URL is required")
        assert_configured_development_target(
            dsn, app_env=args.environment, operation="read" if args.dry_run else "write"
        )
        connection = psycopg2.connect(dsn)
        repo = ApplyRepository(connection, run_id)
        dry_run = args.dry_run
        if not dry_run:
            repo.begin_run(args.site, args.environment)
    ids = repo.proposals(
        args.site,
        args.environment,
        limit=args.batch_size,
        filters={
            "proposal_id": args.proposal_id,
            "proposal_type": args.proposal_type,
            "risk_level": args.risk_level,
            "reviewed_by": args.reviewed_by,
        },
        retry_failed=args.retry_failed,
    )
    results = []
    engine = ApplyEngine(repo)
    applied_by = args.reviewed_by or "apply-integration-worker"

    def failure_result(proposal_id, status, failure_code):
        result = {
            "proposal_id": proposal_id,
            "status": status,
            "failure_code": failure_code,
        }
        if connection and not dry_run:
            try:
                result["apply_attempt_id"] = repo.record_terminal_attempt(
                    proposal_id, status, applied_by, failure_code
                )
            except Exception as audit_error:
                result["audit_error"] = type(audit_error).__name__
        return result

    for pid in ids:
        try:
            results.append(
                {
                    "proposal_id": pid,
                    **engine.apply(
                        pid,
                        applied_by=applied_by,
                        max_risk=args.max_risk,
                        dry_run=dry_run,
                        retry_failed=args.retry_failed,
                    ),
                }
            )
        except StaleProposal as exc:
            results.append(failure_result(pid, "stale", exc.code))
        except ApplyBlocked as exc:
            results.append(failure_result(pid, "blocked", exc.code))
        except Exception as exc:
            results.append(failure_result(pid, "failed", type(exc).__name__))
    counts = Counter(x["status"] for x in results)
    types = Counter(
        x.get("plan", {}).get("proposal_type") for x in results if x.get("plan")
    )
    report = {
        "run_id": run_id,
        "worker": "apply-integration",
        "version": "1.0.0",
        "dry_run": dry_run,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "approved_proposals_read": len(ids),
        "dry_run_plans": counts["dry_run"],
        "apply_attempts": sum(x["status"] != "dry_run" for x in results),
        "succeeded": counts["succeeded"],
        "blocked": counts["blocked"],
        "stale": counts["stale"],
        "failed": counts["failed"],
        "unsupported": sum(
            x.get("failure_code") == "unsupported_apply_operation" for x in results
        ),
        "changes_written": sum(bool(x.get("changed")) for x in results),
        "evidence_links_created": 0,
        "rollback_payloads_created": sum("change" in x for x in results),
        "risk_distribution": {},
        "proposal_type_distribution": dict(types),
        "warnings": [],
        "errors": [],
        "items": results,
    }
    if connection and not dry_run:
        repo.finish_run("failed" if counts["failed"] else "completed", report)
    if connection:
        connection.close()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jp = args.output_dir / f"{run_id}.json"
    mp = args.output_dir / f"{run_id}.md"
    jp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mp.write_text(
        "# Apply Integration\n\n"
        + "\n".join(
            f"- {k.replace('_', ' ').title()}: {report[k]}"
            for k in (
                "approved_proposals_read",
                "dry_run_plans",
                "succeeded",
                "blocked",
                "stale",
                "failed",
                "changes_written",
                "rollback_payloads_created",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "run_id",
                    "dry_run",
                    "approved_proposals_read",
                    "dry_run_plans",
                    "succeeded",
                    "blocked",
                    "stale",
                    "failed",
                )
            }
            | {"reports": [str(jp), str(mp)]},
            sort_keys=True,
        )
    )
    if counts["failed"]:
        return EXIT["failed"]
    if counts["stale"]:
        return EXIT["stale"]
    if counts["blocked"]:
        return EXIT["blocked"]
    return 0
