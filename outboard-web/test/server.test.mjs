import test from 'node:test'
import assert from 'node:assert/strict'
import { once } from 'node:events'
import { resolveRequest, startServer } from '../server.mjs'

test('serves the OutboardRepairBase health contract', () => {
  return resolveRequest('/api/health').then((result) => {
    assert.deepEqual(result.body, { status: 'ok', service: 'outboardrepairbase-web', dataSource: 'fixture' })
  })
})

test('exposes only outboard demonstration models', async () => {
  const models = (await resolveRequest('/api/models')).body
  assert.deepEqual(models.map(({ name }) => name), ['Yamaha F150', 'Mercury 150 FourStroke'])
  assert.equal(models.some((model) => /washer|dishwasher|dryer/i.test(model.name)), false)
  assert.deepEqual(models[0].modelYears, [2020, 2021, 2022, 2023, 2024])
})

test('supports model routes and rejects unknown models', async () => {
  assert.equal((await resolveRequest('/models/yamaha-f150/')).file, 'index.html')
  assert.equal((await resolveRequest('/api/models/yamaha-f150')).body.model, 'F150')
  assert.equal((await resolveRequest('/api/models/unknown')).status, 404)
})

test('builds brand endpoints from published model records', async () => {
  const brands = (await resolveRequest('/api/brands')).body
  assert.deepEqual(brands, [
    { name: 'Yamaha', slug: 'yamaha', modelCount: 1 },
    { name: 'Mercury', slug: 'mercury', modelCount: 1 },
  ])
  assert.equal((await resolveRequest('/api/brands/yamaha')).body.models[0].model, 'F150')
  assert.equal((await resolveRequest('/api/brands/unknown')).status, 404)
  assert.equal((await resolveRequest('/brands/yamaha/')).file, 'index.html')
})

test('only returns error codes supplied by the publication-gated repository', async () => {
  const published = { slug: 'yamaha-33', code: '33', title: 'Ignition system fault', description: 'Verified description', brand: 'Yamaha' }
  const repository = {
    source: 'postgresql',
    async listPublishedFaultCodes() { return [published] },
    async findPublishedFaultCodeBySlug(slug) { return slug === published.slug ? published : null },
  }
  assert.deepEqual((await resolveRequest('/api/error-codes', repository)).body, [published])
  assert.deepEqual((await resolveRequest('/api/error-codes/yamaha-33', repository)).body, published)
  assert.equal((await resolveRequest('/api/error-codes/incomplete', repository)).status, 404)
})

test('serves staging safety headers', async (context) => {
  const server = startServer(0)
  context.after(() => server.close())
  await once(server, 'listening')
  const { port } = server.address()
  const response = await fetch(`http://127.0.0.1:${port}/api/health`)
  assert.equal(response.status, 200)
  assert.equal(response.headers.get('x-robots-tag'), 'noindex, nofollow')
  assert.equal(response.headers.get('x-frame-options'), 'DENY')
  assert.match(response.headers.get('content-security-policy'), /frame-ancestors 'none'/)
})
