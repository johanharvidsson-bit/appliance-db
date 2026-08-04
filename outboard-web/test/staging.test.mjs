import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8')

test('staging runtime keeps PostgreSQL private and the app read-only', async () => {
  const compose = await read('../compose.staging.yaml')
  const postgresService = compose.split('\n  web:')[0]
  assert.doesNotMatch(postgresService, /\n\s+ports:/)
  assert.match(compose, /read_only: true/)
  assert.match(compose, /cap_drop: \[ALL\]/)
  assert.match(compose, /database:\s*\n\s*internal: true/)
  assert.match(compose, /PGUSER: outboard_app/)
})

test('runtime database role receives select but no mutation grants', async () => {
  const grants = await read('../sql/030-runtime-grants.sql')
  assert.match(grants, /GRANT SELECT ON/)
  assert.doesNotMatch(grants, /GRANT (INSERT|UPDATE|DELETE)/)
  assert.doesNotMatch(grants, /rb_redirects/)
  assert.doesNotMatch(grants, /rb_audit_events/)
})

test('fresh PostgreSQL initialization creates migration tracking first', async () => {
  const compose = await read('../compose.staging.yaml')
  const tracking = await read('../sql/001-migration-tracking.sql')
  assert.match(compose, /001-migration-tracking\.sql/)
  assert.match(tracking, /CREATE TABLE IF NOT EXISTS schema_migrations/)
})

test('staging seed remains noindex and contains only outboard records', async () => {
  const seed = await read('../sql/seed-staging.sql')
  assert.match(seed, /outboard-repair-base/)
  assert.match(seed, /index_state = 'noindex'/)
  assert.match(seed, /editorial_hold/)
  assert.doesNotMatch(seed, /washing.machine|dishwasher|dryer/i)
})

test('staging compose bounds logs and keeps restart policies', async () => {
  const compose = await read('../compose.staging.yaml')
  assert.match(compose, /max-size: "10m"/)
  assert.match(compose, /max-file: "3"/)
  assert.equal((compose.match(/restart: unless-stopped/g) ?? []).length, 4)
})

test('fault-code publication is gated and workers use a private role', async () => {
  const compose = await read('../compose.staging.yaml')
  const migration = await read('../../db/migrations/014_outboard_fault_code_workflow.sql')
  assert.match(compose, /PGUSER: outboard_worker/)
  assert.match(compose, /014-outboard-fault-code-workflow\.sql/)
  assert.match(migration, /missing_description/)
  assert.match(migration, /verified_source_required/)
  assert.match(migration, /applicability_required/)
  assert.match(migration, /editorial_approval_required/)
  assert.match(migration, /FOR UPDATE SKIP LOCKED/)
  assert.match(migration, /idempotency_key TEXT NOT NULL UNIQUE/)
  assert.match(migration, /REVOKE ALL ON FUNCTION rb_claim_worker_job/)
})

test('production operations include backup, restore and health timers', async () => {
  for (const name of ['backup.sh', 'restore-check.sh', 'healthcheck.sh']) {
    const script = await read(`../ops/${name}`)
    assert.match(script, /^#!\/bin\/sh/)
    assert.match(script, /set -eu/)
  }

  for (const name of ['outboard-backup.timer', 'outboard-restore-check.timer', 'outboard-health.timer']) {
    const timer = await read(`../ops/systemd/${name}`)
    assert.match(timer, /\[Timer\]/)
    assert.match(timer, /Persistent=true/)
  }
})
