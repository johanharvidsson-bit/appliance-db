import pg from 'pg'
import { hostname } from 'node:os'
import { fileURLToPath } from 'node:url'

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

export async function processWorkerJob(client, job, workerName) {
  if (job.job_type !== 'assess_fault_code_readiness' || job.entity_type !== 'fault_code') {
    throw new Error(`Unsupported job ${job.job_type}/${job.entity_type}`)
  }
  await client.query('SELECT rb_assess_fault_code_readiness($1)', [job.entity_id])
  await client.query('SELECT rb_complete_worker_job($1, $2)', [job.worker_job_id, workerName])
}

export async function runWorker({
  pool,
  workerName = `outboard-worker:${hostname()}:${process.pid}`,
  pollMilliseconds = Number(process.env.OUTBOARD_WORKER_POLL_MS || 5000),
  once = process.env.OUTBOARD_WORKER_ONCE === 'true',
  signal = { stopped: false },
} = {}) {
  if (!pool) throw new Error('A PostgreSQL pool is required')
  do {
    const client = await pool.connect()
    let job
    try {
      await client.query('BEGIN')
      const claimed = await client.query('SELECT * FROM rb_claim_worker_job($1, $2)', [workerName, 60])
      job = claimed.rows[0]
      await client.query('COMMIT')
    } catch (error) {
      await client.query('ROLLBACK').catch(() => {})
      client.release()
      throw error
    }
    if (job) {
      try {
        await processWorkerJob(client, job, workerName)
        console.log(`Completed worker job ${job.worker_job_id}`)
      } catch (error) {
        await client.query('SELECT rb_fail_worker_job($1, $2, $3)', [job.worker_job_id, workerName, error.message])
        console.error(`Failed worker job ${job.worker_job_id}: ${error.message}`)
      }
    }
    client.release()
    if (!job && !once && !signal.stopped) await sleep(pollMilliseconds)
  } while (!once && !signal.stopped)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const pool = new pg.Pool({ max: 2, connectionTimeoutMillis: 5000, idleTimeoutMillis: 10000 })
  const signal = { stopped: false }
  const shutdown = () => { signal.stopped = true }
  process.on('SIGTERM', shutdown)
  process.on('SIGINT', shutdown)
  runWorker({ pool, signal })
    .then(() => pool.end())
    .catch((error) => {
      console.error('Worker stopped', error.message)
      pool.end().finally(() => process.exit(1))
    })
}
