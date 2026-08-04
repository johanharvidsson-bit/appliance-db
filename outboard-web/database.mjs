import pg from 'pg'
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('.', import.meta.url))
const fixtureModels = JSON.parse(await readFile(join(root, 'data', 'models.json'), 'utf8'))

function toPublicModel(row) {
  const snapshot = row.publication_snapshot || {}
  return {
    slug: String(row.slug),
    brand: row.brand,
    model: row.model_name,
    name: `${row.brand} ${row.model_name}`,
    family: snapshot.family || 'Outboard engine',
    horsepower: Number(row.horsepower_hp),
    fuel: row.fuel_type[0].toUpperCase() + row.fuel_type.slice(1),
    years: snapshot.years || 'Model years pending verification',
    generation: snapshot.generation || 'Generation pending verification',
    modelYears: snapshot.modelYears || [],
    status: 'Published test data',
    accent: snapshot.accent || '#087ea4',
    summary: row.short_description,
    specifications: snapshot.specifications || [
      ['Rated output', `${Number(row.horsepower_hp)} hp`],
      ['Fuel', row.fuel_type],
      ['Model code', row.normalized_model_code],
    ],
    sources: snapshot.sources || [],
  }
}

export function createModelRepository({ connectionString = process.env.DATABASE_URL, usePostgres = Boolean(process.env.PGHOST) } = {}) {
  if (!connectionString && !usePostgres) {
    return {
      source: 'fixture',
      async listPublished() { return fixtureModels },
      async findPublishedBySlug(slug) { return fixtureModels.find((model) => model.slug === slug) || null },
      async close() {},
    }
  }

  const pool = new pg.Pool({
    ...(connectionString ? { connectionString } : {}),
    max: 5,
    connectionTimeoutMillis: 3000,
    idleTimeoutMillis: 10000,
  })
  const baseQuery = `
    SELECT p.slug, b.canonical_name AS brand, mt.name AS model_name,
           mt.short_description, m.normalized_model_code, m.horsepower_hp,
           m.fuel_type, pr.publication_snapshot
    FROM rb_pages p
    JOIN rb_sites s ON s.site_id = p.site_id
    JOIN rb_engine_models m ON m.engine_model_id = p.engine_model_id
    JOIN rb_brands b ON b.brand_id = m.brand_id
    JOIN rb_engine_model_translations mt
      ON mt.engine_model_id = m.engine_model_id
     AND mt.language_code = p.language_code
     AND mt.translation_state = 'approved'
    JOIN rb_page_revisions pr ON pr.page_revision_id = p.published_revision_id
    WHERE s.site_key = 'outboard-repair-base'
      AND s.publication_state = 'published'
      AND p.page_type = 'engine_model'
      AND p.language_code = 'en'
      AND p.publication_state = 'published'
      AND p.archived_at IS NULL
      AND m.archived_at IS NULL`

  return {
    source: 'postgresql',
    async listPublished() {
      const result = await pool.query(`${baseQuery} ORDER BY b.canonical_name, mt.name`)
      return result.rows.map(toPublicModel)
    },
    async findPublishedBySlug(slug) {
      const result = await pool.query(`${baseQuery} AND p.slug = $1 LIMIT 1`, [slug])
      return result.rows[0] ? toPublicModel(result.rows[0]) : null
    },
    async health() {
      await pool.query('SELECT 1')
      return true
    },
    async close() { await pool.end() },
  }
}
