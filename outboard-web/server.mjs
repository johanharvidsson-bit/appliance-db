import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { extname, join, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createModelRepository } from './database.mjs'

const root = fileURLToPath(new URL('.', import.meta.url))
const publicRoot = join(root, 'public')
const port = Number(process.env.OUTBOARD_PORT || 4323)
const host = process.env.OUTBOARD_HOST || '127.0.0.1'
const repository = createModelRepository()

const types = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
}

export async function resolveRequest(pathname, modelsRepository = repository) {
  if (pathname === '/api/health') {
    if (modelsRepository.health) await modelsRepository.health()
    return { type: 'json', body: { status: 'ok', service: 'outboardrepairbase-web', dataSource: modelsRepository.source } }
  }
  if (pathname === '/api/models') return { type: 'json', body: await modelsRepository.listPublished() }
  if (pathname === '/api/brands') {
    const models = await modelsRepository.listPublished()
    const brands = [...new Set(models.map((model) => model.brand))].map((brand) => ({
      name: brand,
      slug: brand.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
      modelCount: models.filter((model) => model.brand === brand).length,
    }))
    return { type: 'json', body: brands }
  }
  const brandMatch = pathname.match(/^\/api\/brands\/([^/]+)$/)
  if (brandMatch) {
    const models = await modelsRepository.listPublished()
    const brandModels = models.filter((model) => model.brand.toLowerCase().replace(/[^a-z0-9]+/g, '-') === brandMatch[1])
    return brandModels.length
      ? { type: 'json', body: { name: brandModels[0].brand, slug: brandMatch[1], models: brandModels } }
      : { type: 'json', status: 404, body: { error: 'Brand not found' } }
  }
  const match = pathname.match(/^\/api\/models\/([^/]+)$/)
  if (match) {
    const model = await modelsRepository.findPublishedBySlug(match[1])
    return model ? { type: 'json', body: model } : { type: 'json', status: 404, body: { error: 'Model not found' } }
  }
  if (pathname === '/' || /^\/(models|brands)\/[^/]+\/?$/.test(pathname)) return { type: 'file', file: 'index.html' }
  const safePath = normalize(pathname).replace(/^(\.\.[/\\])+/, '').replace(/^[/\\]+/, '')
  return { type: 'file', file: safePath }
}

export function startServer(listenPort = port) {
  return createServer(async (req, res) => {
    const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`)
    let result
    try {
      result = await resolveRequest(url.pathname)
    } catch (error) {
      console.error('Request failed', error.message)
      res.writeHead(503, { 'Content-Type': 'application/json; charset=utf-8' })
      return res.end(JSON.stringify({ error: 'Data source unavailable' }))
    }
    res.setHeader('X-Content-Type-Options', 'nosniff')
    res.setHeader('X-Frame-Options', 'DENY')
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin')
    res.setHeader('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
    res.setHeader('X-Robots-Tag', 'noindex, nofollow')
    res.setHeader('Cache-Control', 'no-store')
    if (result.type === 'json') {
      res.writeHead(result.status || 200, { 'Content-Type': 'application/json; charset=utf-8' })
      return res.end(JSON.stringify(result.body))
    }
    try {
      const file = await readFile(join(publicRoot, result.file))
      res.writeHead(200, { 'Content-Type': types[extname(result.file)] || 'application/octet-stream' })
      res.end(file)
    } catch {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
      res.end('Not found')
    }
  }).listen(listenPort, host)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const server = startServer()
  server.on('listening', () => {
    console.log(`OutboardRepairBase test site: http://${host}:${port}`)
  })
  const shutdown = () => server.close(() => repository.close().finally(() => process.exit(0)))
  process.on('SIGTERM', shutdown)
  process.on('SIGINT', shutdown)
}
