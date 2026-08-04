import test from 'node:test'
import assert from 'node:assert/strict'
import { processWorkerJob } from '../worker.mjs'

test('readiness worker assesses and completes a supported fault-code job', async () => {
  const calls = []
  const client = { async query(text, values) { calls.push({ text, values }) } }
  const job = { worker_job_id: 7, job_type: 'assess_fault_code_readiness', entity_type: 'fault_code', entity_id: 42 }
  await processWorkerJob(client, job, 'test-worker')
  assert.deepEqual(calls.map(({ values }) => values), [[42], [7, 'test-worker']])
  assert.match(calls[0].text, /rb_assess_fault_code_readiness/)
  assert.match(calls[1].text, /rb_complete_worker_job/)
})

test('readiness worker rejects unknown jobs so they enter retry handling', async () => {
  await assert.rejects(
    processWorkerJob({ query: async () => {} }, { job_type: 'publish', entity_type: 'fault_code' }, 'test-worker'),
    /Unsupported job/,
  )
})
