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

test('staging seed remains noindex and contains only outboard records', async () => {
  const seed = await read('../sql/seed-staging.sql')
  assert.match(seed, /outboard-repair-base/)
  assert.match(seed, /index_state = 'noindex'/)
  assert.match(seed, /editorial_hold/)
  assert.doesNotMatch(seed, /washing.machine|dishwasher|dryer/i)
})
