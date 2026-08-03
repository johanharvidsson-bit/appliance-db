from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
from uuid import uuid4

import psycopg2

from config.target_safety import assert_safe_target
from workers.ingestion_repository import IngestionRepository
from workers.ingestion_safety import (
    FetchPolicyError,
    FetchResult,
    SafeFetcher,
)
from workers.ingestion_storage import DocumentStore
from workers.source_ingestion import extract_facts, parse_document


class FixtureFetcher:
    def __init__(self, responses):
        self.responses = responses

    def fetch(self, url, **_):
        entry = self.responses[url]
        if "error" in entry:
            raise FetchPolicyError(entry["error"]["status"], entry["error"]["reason"])
        body = (
            base64.b64decode(entry["body_base64"])
            if "body_base64" in entry
            else entry.get("body", "").encode()
        )
        return FetchResult(
            url,
            entry.get("final_url", url),
            entry.get("status", 200),
            entry["mime_type"],
            body,
            entry.get("headers", {}),
        )


def run(args):
    if args.environment == "production":
        raise SystemExit("source ingestion production execution is not enabled")
    if args.batch_size < 1 or args.max_document_bytes < 1 or args.retries < 0:
        raise SystemExit("invalid ingestion limits")
    started = datetime.now(timezone.utc)
    run_id = str(uuid4())
    connection = repo = None
    locked = []
    totals = {
        "accepted_scanned": 0,
        "fetched": 0,
        "not_modified": 0,
        "blocked": 0,
        "unsupported": 0,
        "failed": 0,
        "invalid_content": 0,
        "too_large": 0,
        "documents": 0,
        "candidate_facts": 0,
        "conflicted": 0,
        "deduplicated": 0,
    }
    details = []
    if args.fixture:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        items = [
            item
            for item in fixture["candidates"]
            if item.get("status", "accepted") == "accepted"
        ][: args.batch_size]
        fetcher = FixtureFetcher(fixture["responses"])
        dry_run = True
    else:
        dsn = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL", "").strip()
        if not dsn:
            raise SystemExit("REPAIRBASE_SECURITY_TEST_DB_URL is required")
        assert_safe_target(
            dsn, app_env=args.environment, operation="read" if args.dry_run else "write"
        )
        connection = psycopg2.connect(dsn)
        repo = IngestionRepository(connection)
        if not repo.lock(args.site, args.environment):
            raise SystemExit("source-ingestion lock is already held")
        items = repo.candidates(
            args.site,
            args.environment,
            limit=args.batch_size,
            filters={
                "source_candidate_id": args.source_candidate_id,
                "backlog_id": args.backlog_id,
                "source_type": args.source_type,
            },
        )
        connection.rollback()
        dry_run = args.dry_run
        if not dry_run:
            repo.start_run(run_id, args.site, args.environment)
            connection.commit()
        fetcher = SafeFetcher(
            timeout=args.timeout,
            retries=args.retries,
            rate_limit=args.rate_limit,
            max_bytes=args.max_document_bytes,
        )
    store = DocumentStore(args.storage_dir)
    try:
        for item in items:
            totals["accepted_scanned"] += 1
            url = item.get("normalized_url") or item.get("candidate_url")
            if not url:
                totals["invalid_content"] += 1
                details.append(
                    {
                        "source_candidate_id": item["source_candidate_id"],
                        "status": "invalid_content",
                        "reason": "missing_url",
                    }
                )
                continue
            if repo and not repo.lock(
                args.site, args.environment, item["source_candidate_id"]
            ):
                totals["failed"] += 1
                details.append(
                    {
                        "source_candidate_id": item["source_candidate_id"],
                        "status": "failed",
                        "reason": "candidate_lock_held",
                    }
                )
                continue
            if repo:
                locked.append(item["source_candidate_id"])
            try:
                cache = (
                    {}
                    if args.reprocess or not repo
                    else repo.cache_headers(item["source_candidate_id"])
                )
                result = fetcher.fetch(
                    url,
                    etag=cache.get("etag"),
                    last_modified=cache.get("last_modified"),
                )
                if result.status_code == 304:
                    totals["not_modified"] += 1
                    if repo and not dry_run:
                        repo.record_not_modified(item, run_id, result)
                        connection.commit()
                    details.append(
                        {
                            "source_candidate_id": item["source_candidate_id"],
                            "status": "not_modified",
                        }
                    )
                    continue
                document = parse_document(
                    result.final_url, result.mime_type, result.body
                )
                facts = extract_facts(
                    document,
                    subject_hint=f"{item['entity_type']}:{item['entity_id']}",
                    locale=item.get("locale"),
                    source_trust=item.get("confidence", 50),
                )
                totals["fetched"] += 1
                totals["documents"] += 1
                totals["candidate_facts"] += len(facts)
                totals["conflicted"] += sum(f.status == "conflicted" for f in facts)
                persisted = {"facts": 0, "deduplicated": 0}
                storage_ref = f"dry-run://sha256/{_hash(result.body)}"
                if not dry_run:
                    suffix = {
                        "application/pdf": ".pdf",
                        "text/html": ".html",
                        "application/json": ".json",
                        "text/plain": ".txt",
                    }[result.mime_type]
                    storage_ref, content_hash = store.put(result.body, suffix)
                    persisted = repo.persist(
                        item,
                        run_id,
                        result,
                        storage_ref,
                        content_hash,
                        document,
                        facts,
                        reprocess=args.reprocess,
                    )
                    connection.commit()
                totals["deduplicated"] += persisted["deduplicated"]
                details.append(
                    {
                        "source_candidate_id": item["source_candidate_id"],
                        "status": "fetched",
                        "document_type": document.document_type,
                        "facts": [
                            {
                                "type": f.fact_type,
                                "predicate": f.predicate,
                                "value": f.value,
                                "confidence": f.confidence,
                                "status": f.status,
                                "locator": f.locator,
                            }
                            for f in facts
                        ],
                        "storage_reference": storage_ref,
                    }
                )
            except FetchPolicyError as exc:
                totals[exc.status] += 1
                if repo and not dry_run:
                    repo.record_failure(item, run_id, exc.status, exc.reason, url)
                    connection.commit()
                details.append(
                    {
                        "source_candidate_id": item["source_candidate_id"],
                        "status": exc.status,
                        "reason": exc.reason,
                    }
                )
            except Exception as exc:
                totals["failed"] += 1
                if repo and not dry_run:
                    repo.record_failure(item, run_id, "failed", type(exc).__name__, url)
                    connection.commit()
                details.append(
                    {
                        "source_candidate_id": item["source_candidate_id"],
                        "status": "failed",
                        "reason": type(exc).__name__,
                    }
                )
    finally:
        if repo:
            if not dry_run:
                repo.finish_run(run_id, totals)
                connection.commit()
            for candidate_id in locked:
                repo.unlock(args.site, args.environment, candidate_id)
            repo.unlock(args.site, args.environment)
            connection.close()
    report = {
        "run_id": run_id,
        "worker": "source-ingestion",
        "version": "1.0.0",
        "status": "completed",
        "dry_run": dry_run,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        **totals,
        "items": details,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jp = args.output_dir / f"{run_id}.json"
    mp = args.output_dir / f"{run_id}.md"
    jp.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    mp.write_text(
        "# Source Ingestion & Enrichment\n\n"
        + "\n".join(f"- {k.replace('_', ' ').title()}: {v}" for k, v in totals.items())
        + "\n",
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


def _hash(body):
    from hashlib import sha256

    return sha256(body).hexdigest()
