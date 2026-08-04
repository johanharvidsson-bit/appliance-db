import pg from 'pg'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const allowedSourceTypes = new Set([
  'owner_manual', 'service_manual', 'parts_catalog', 'rigging_manual',
  'service_bulletin', 'manufacturer_webpage', 'dealer_document',
  'regulatory_document', 'other',
])

export function validateSourceCandidate(candidate) {
  if (!candidate || typeof candidate !== 'object') throw new Error('Source candidate must be an object')
  if (!allowedSourceTypes.has(candidate.sourceType)) throw new Error('Unsupported sourceType')
  for (const field of ['title', 'publisher', 'sourceUrl', 'languageCode', 'retrievedAt', 'observedText']) {
    if (typeof candidate[field] !== 'string' || !candidate[field].trim()) throw new Error(`${field} is required`)
  }
  const url = new URL(candidate.sourceUrl)
  if (url.protocol !== 'https:') throw new Error('sourceUrl must use HTTPS')
  const retrievedAt = new Date(candidate.retrievedAt)
  if (Number.isNaN(retrievedAt.valueOf())) throw new Error('retrievedAt must be an ISO timestamp')
  if (candidate.sourceAuthority != null && (candidate.sourceAuthority < 0 || candidate.sourceAuthority > 1)) {
    throw new Error('sourceAuthority must be between 0 and 1')
  }
  return {
    sourceType: candidate.sourceType,
    title: candidate.title.trim(),
    publisher: candidate.publisher.trim(),
    sourceUrl: url.toString(),
    languageCode: candidate.languageCode.trim(),
    sourceAuthority: candidate.sourceAuthority ?? null,
    retrievedAt: retrievedAt.toISOString(),
    observedText: candidate.observedText.trim(),
  }
}

export function sourceContentHash(candidate) {
  const normalized = validateSourceCandidate(candidate)
  return createHash('sha256').update(JSON.stringify({
    sourceUrl: normalized.sourceUrl,
    title: normalized.title,
    observedText: normalized.observedText,
  })).digest('hex')
}

export async function importSourceCandidate(client, candidate) {
  const source = validateSourceCandidate(candidate)
  const contentHash = sourceContentHash(source)
  await client.query('BEGIN')
  try {
    await client.query('SELECT pg_advisory_xact_lock(hashtextextended($1, 0))', [source.sourceUrl])
    const existing = await client.query(
      'SELECT source_id FROM rb_sources WHERE source_url = $1 ORDER BY source_id LIMIT 1',
      [source.sourceUrl],
    )
    let sourceId = existing.rows[0]?.source_id
    if (!sourceId) {
      const inserted = await client.query(`
        INSERT INTO rb_sources(source_type, title, publisher, source_url, language_code, source_authority)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING source_id`,
      [source.sourceType, source.title, source.publisher, source.sourceUrl, source.languageCode, source.sourceAuthority])
      sourceId = inserted.rows[0].source_id
    }
    const existingRevision = await client.query(
      'SELECT source_revision_id FROM rb_source_revisions WHERE source_id = $1 AND content_hash = $2',
      [sourceId, contentHash],
    )
    const revision = existingRevision.rows[0]
      ? existingRevision
      : await client.query(`
          INSERT INTO rb_source_revisions(source_id, content_hash, retrieved_at)
          VALUES ($1, $2, $3)
          RETURNING source_revision_id`, [sourceId, contentHash, source.retrievedAt])
    await client.query('COMMIT')
    return { sourceId, sourceRevisionId: revision.rows[0].source_revision_id, contentHash }
  } catch (error) {
    await client.query('ROLLBACK')
    throw error
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const fileIndex = process.argv.indexOf('--file')
  if (fileIndex < 0 || !process.argv[fileIndex + 1]) throw new Error('Usage: node source-import.mjs --file candidate.json [--dry-run]')
  const candidate = JSON.parse(await readFile(process.argv[fileIndex + 1], 'utf8'))
  const validated = validateSourceCandidate(candidate)
  if (process.argv.includes('--dry-run')) {
    console.log(JSON.stringify({ status: 'valid', contentHash: sourceContentHash(validated) }))
  } else {
    const pool = new pg.Pool({ max: 1, connectionTimeoutMillis: 5000 })
    try {
      console.log(JSON.stringify({ status: 'imported', ...await importSourceCandidate(pool, validated) }))
    } finally {
      await pool.end()
    }
  }
}
