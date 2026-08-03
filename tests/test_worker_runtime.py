import os
from urllib.parse import urlparse
from uuid import uuid4

import psycopg2
import pytest

from pipeline.worker_runtime import WorkerRuntime


def _dsn() -> str:
    value = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not value:
        pytest.skip("explicit dev integration DSN not set")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 15432 or parsed.path != "/repair_appliance_dev":
        pytest.fail("worker tests require isolated loopback dev database")
    return value


def _observation(payload: dict) -> dict:
    return {
        "observation_key": payload["key"],
        "entity_type": "model",
        "normalized_key": payload["key"].upper(),
        "observed_data": {"name": payload["key"]},
    }


def test_batches_and_jobs_are_idempotent_and_dry_run_writes_no_candidate():
    runtime = WorkerRuntime(_dsn())
    token = uuid4().hex
    batch = runtime.create_batch(site_id="appliance-repair-base", job_type="synthetic", idempotency_key=token, scope={"brand": "test"}, dry_run=True)
    assert runtime.create_batch(site_id="appliance-repair-base", job_type="synthetic", idempotency_key=token, scope={"brand": "test"}, dry_run=True) == batch
    with pytest.raises(ValueError, match="different dry_run"):
        runtime.create_batch(site_id="appliance-repair-base", job_type="synthetic", idempotency_key=token, scope={"brand": "test"}, dry_run=False)
    first = runtime.enqueue(batch, [{"job_key": "one", "payload": {"key": token}}])
    assert runtime.enqueue(batch, [{"job_key": "one", "payload": {"key": token}}]) == first
    result = runtime.run_once(lease_owner="test-worker", handler=_observation)
    assert result["status"] == "completed" and result["dry_run"] is True
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM worker_observations WHERE job_id=%s", (first[0],))
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT status FROM worker_batches WHERE id=%s", (batch,))
            assert cursor.fetchone()[0] == "completed"


def test_non_dry_run_observation_retry_dead_letter_and_rollback_are_audited():
    runtime = WorkerRuntime(_dsn())
    token = uuid4().hex
    batch = runtime.create_batch(site_id="appliance-repair-base", job_type="synthetic", idempotency_key=token, scope={}, dry_run=False)
    jobs = runtime.enqueue(
        batch,
        [
            {"job_key": "success", "payload": {"key": token + "-ok"}},
            {"job_key": "retry", "payload": {"key": token + "-retry"}},
        ],
        max_attempts=2,
    )
    assert runtime.run_once(lease_owner="worker-a", handler=_observation)["observation_id"] is not None
    attempts = {"value": 0}

    def flaky(payload):
        attempts["value"] += 1
        if attempts["value"] == 1:
            raise RuntimeError("synthetic transient")
        return _observation(payload)

    assert runtime.run_once(lease_owner="worker-a", handler=flaky)["status"] == "retry"
    assert runtime.run_once(lease_owner="worker-b", handler=flaky)["status"] == "completed"
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM worker_observations WHERE job_id=ANY(%s)", (jobs,))
            assert cursor.fetchone()[0] == 2
            cursor.execute("SELECT status FROM worker_batches WHERE id=%s", (batch,))
            assert cursor.fetchone()[0] == "completed"
            cursor.execute("SELECT event_type FROM worker_events WHERE batch_id=%s", (batch,))
            events = {row[0] for row in cursor.fetchall()}
            assert {"job_retry", "job_completed", "batch_completed"} <= events
    rollback = runtime.rollback_batch(batch)
    assert rollback["observations_preserved"] == 2

    dead_batch = runtime.create_batch(site_id="appliance-repair-base", job_type="synthetic", idempotency_key=token + "-dead", scope={}, dry_run=False)
    runtime.enqueue(dead_batch, [{"job_key": "dead", "payload": {"key": token}}], max_attempts=1)
    result = runtime.run_once(lease_owner="worker-a", handler=lambda _: (_ for _ in ()).throw(ValueError("bad")))
    assert result["status"] == "dead_letter"


def test_worker_tables_are_internal_and_runtime_rejects_production():
    with psycopg2.connect(_dsn()) as connection:
        with connection.cursor() as cursor:
            for table in ("worker_batches", "worker_jobs", "worker_observations", "worker_events"):
                for role in ("anon", "authenticated"):
                    cursor.execute("SELECT has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE')", (role, table))
                    assert cursor.fetchone()[0] is False
                cursor.execute("SELECT has_table_privilege('service_role',%s,'DELETE')", (table,))
                assert cursor.fetchone()[0] is False
    with pytest.raises(ValueError, match="restricted to development"):
        WorkerRuntime(_dsn(), environment="production")
