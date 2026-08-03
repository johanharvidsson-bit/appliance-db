"""Minimal guarded worker runtime with idempotent batches, retries and audit events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Callable

import psycopg2

from config.target_safety import assert_safe_target


ObservationHandler = Callable[[dict], dict]


class WorkerRuntime:
    def __init__(self, dsn: str, *, environment: str = "development"):
        if environment != "development":
            raise ValueError("local worker runtime is restricted to development")
        assert_safe_target(dsn, app_env=environment, operation="write")
        self.dsn = dsn

    def create_batch(self, *, site_id: str, job_type: str, idempotency_key: str, scope: dict, dry_run: bool) -> int:
        with psycopg2.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO worker_batches(site_id,job_type,idempotency_key,scope_json,dry_run) "
                    "VALUES(%s,%s,%s,%s::jsonb,%s) ON CONFLICT(site_id,job_type,idempotency_key) "
                    "DO UPDATE SET idempotency_key=EXCLUDED.idempotency_key RETURNING id,dry_run",
                    (site_id, job_type, idempotency_key, json.dumps(scope), dry_run),
                )
                batch_id, persisted_dry_run = cursor.fetchone()
                if persisted_dry_run is not dry_run:
                    raise ValueError("idempotency key already exists with a different dry_run mode")
                cursor.execute(
                    "INSERT INTO worker_events(batch_id,event_type,details_json) "
                    "SELECT %s,'batch_created',%s::jsonb WHERE NOT EXISTS(" 
                    "SELECT 1 FROM worker_events WHERE batch_id=%s AND event_type='batch_created')",
                    (batch_id, json.dumps({"dry_run": dry_run}), batch_id),
                )
                return batch_id

    def enqueue(self, batch_id: int, jobs: list[dict], *, max_attempts: int = 3) -> list[int]:
        ids: list[int] = []
        with psycopg2.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                for job in jobs:
                    cursor.execute(
                        "INSERT INTO worker_jobs(batch_id,job_key,payload_json,max_attempts) "
                        "VALUES(%s,%s,%s::jsonb,%s) ON CONFLICT(batch_id,job_key) "
                        "DO UPDATE SET job_key=EXCLUDED.job_key RETURNING id",
                        (batch_id, job["job_key"], json.dumps(job.get("payload", {})), max_attempts),
                    )
                    job_id = cursor.fetchone()[0]
                    ids.append(job_id)
                    cursor.execute(
                        "INSERT INTO worker_events(batch_id,job_id,event_type) "
                        "SELECT %s,%s,'job_queued' WHERE NOT EXISTS(" 
                        "SELECT 1 FROM worker_events WHERE job_id=%s AND event_type='job_queued')",
                        (batch_id, job_id, job_id),
                    )
        return ids

    def run_once(self, *, lease_owner: str, handler: ObservationHandler, retry_delay_seconds: int = 0) -> dict | None:
        if not lease_owner.strip():
            raise ValueError("lease_owner is required")
        with psycopg2.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT j.id,j.batch_id,j.payload_json,j.attempts,j.max_attempts,b.dry_run "
                    "FROM worker_jobs j JOIN worker_batches b ON b.id=j.batch_id "
                    "WHERE j.status IN('queued','retry') AND j.available_at<=now() "
                    "ORDER BY j.id FOR UPDATE OF j SKIP LOCKED LIMIT 1"
                )
                row = cursor.fetchone()
                if not row:
                    return None
                job_id, batch_id, payload, attempts, max_attempts, dry_run = row
                cursor.execute(
                    "UPDATE worker_jobs SET status='running',attempts=attempts+1,leased_at=now(),lease_owner=%s WHERE id=%s",
                    (lease_owner, job_id),
                )
                cursor.execute("UPDATE worker_batches SET status='running' WHERE id=%s AND status='planned'", (batch_id,))
                cursor.execute("INSERT INTO worker_events(batch_id,job_id,event_type) VALUES(%s,%s,'job_claimed')", (batch_id, job_id))
                try:
                    observation = handler(payload)
                    required = {"observation_key", "entity_type", "normalized_key", "observed_data"}
                    if required - observation.keys():
                        raise ValueError("handler returned an incomplete observation")
                    if not dry_run:
                        cursor.execute(
                            "INSERT INTO worker_observations(job_id,observation_key,entity_type,normalized_key,observed_data) "
                            "VALUES(%s,%s,%s,%s,%s::jsonb) ON CONFLICT(job_id,observation_key) "
                            "DO UPDATE SET observed_data=EXCLUDED.observed_data RETURNING id",
                            (job_id, observation["observation_key"], observation["entity_type"], observation["normalized_key"], json.dumps(observation["observed_data"])),
                        )
                        observation_id = cursor.fetchone()[0]
                    else:
                        observation_id = None
                    cursor.execute(
                        "UPDATE worker_jobs SET status='completed',completed_at=now(),leased_at=NULL,lease_owner=NULL,last_error=NULL WHERE id=%s",
                        (job_id,),
                    )
                    cursor.execute(
                        "INSERT INTO worker_events(batch_id,job_id,event_type,details_json) VALUES(%s,%s,'job_completed',%s::jsonb)",
                        (batch_id, job_id, json.dumps({"dry_run": dry_run, "observation_id": observation_id})),
                    )
                    self._finish_batch(cursor, batch_id)
                    return {"job_id": job_id, "status": "completed", "dry_run": dry_run, "observation_id": observation_id, "observation": observation}
                except Exception as error:  # handler boundary intentionally records failure
                    next_attempt = attempts + 1
                    if next_attempt >= max_attempts:
                        status, event = "dead_letter", "job_dead_letter"
                    else:
                        status, event = "retry", "job_retry"
                    available_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, retry_delay_seconds))
                    cursor.execute(
                        "UPDATE worker_jobs SET status=%s,available_at=%s,leased_at=NULL,lease_owner=NULL,last_error=%s WHERE id=%s",
                        (status, available_at, f"{type(error).__name__}: {error}", job_id),
                    )
                    cursor.execute(
                        "INSERT INTO worker_events(batch_id,job_id,event_type,details_json) VALUES(%s,%s,%s,%s::jsonb)",
                        (batch_id, job_id, event, json.dumps({"error_type": type(error).__name__})),
                    )
                    self._finish_batch(cursor, batch_id)
                    return {"job_id": job_id, "status": status, "error_type": type(error).__name__}

    @staticmethod
    def _finish_batch(cursor, batch_id: int) -> None:
        cursor.execute(
            "SELECT count(*) FILTER(WHERE status IN('queued','retry','running')),"
            "count(*) FILTER(WHERE status='dead_letter') FROM worker_jobs WHERE batch_id=%s",
            (batch_id,),
        )
        remaining, dead = cursor.fetchone()
        if remaining:
            return
        status = "failed" if dead else "completed"
        completed = status == "completed"
        cursor.execute(
            "UPDATE worker_batches SET status=%s,completed_at=CASE WHEN %s THEN now() ELSE NULL END WHERE id=%s",
            (status, completed, batch_id),
        )
        cursor.execute(
            "INSERT INTO worker_events(batch_id,event_type,details_json) VALUES(%s,%s,%s::jsonb)",
            (batch_id, "batch_failed" if dead else "batch_completed", json.dumps({"dead_letter_jobs": dead})),
        )

    def rollback_batch(self, batch_id: int) -> dict:
        with psycopg2.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE worker_jobs SET status='cancelled' WHERE batch_id=%s AND status IN('queued','retry')", (batch_id,))
                cancelled = cursor.rowcount
                cursor.execute("UPDATE worker_batches SET status='rolled_back',completed_at=now() WHERE id=%s RETURNING id", (batch_id,))
                if not cursor.fetchone():
                    raise ValueError("unknown batch")
                cursor.execute(
                    "INSERT INTO worker_events(batch_id,event_type,details_json) VALUES(%s,'batch_rolled_back',%s::jsonb)",
                    (batch_id, json.dumps({"cancelled_jobs": cancelled, "observations_preserved": True})),
                )
                cursor.execute("SELECT count(*) FROM worker_observations o JOIN worker_jobs j ON j.id=o.job_id WHERE j.batch_id=%s", (batch_id,))
                observations = cursor.fetchone()[0]
                return {"batch_id": batch_id, "cancelled_jobs": cancelled, "observations_preserved": observations}
