import pg from 'pg'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL is required')
if (process.env.ALLOW_TEST_SEED !== 'true') throw new Error('Set ALLOW_TEST_SEED=true to confirm staging test data')

const sql = await readFile(fileURLToPath(new URL('./sql/seed-staging.sql', import.meta.url)), 'utf8')
const client = new pg.Client({ connectionString: process.env.DATABASE_URL })
await client.connect()
try {
  await client.query(sql)
  console.log('OutboardRepairBase staging seed applied')
} finally {
  await client.end()
}
