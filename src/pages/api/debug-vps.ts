export const prerender = false

import type { APIRoute } from 'astro'

export const GET: APIRoute = async () => {
  const url = import.meta.env.PUBLIC_SUPABASE_URL
  const key = import.meta.env.PUBLIC_SUPABASE_ANON_KEY
  const result: Record<string, any> = {
    configuredUrl: url,
    keyPrefix: key ? key.slice(0, 20) + '...' : null,
  }

  try {
    const target = `${url}/rest/v1/brands?select=id,slug&limit=3`
    const start = Date.now()
    const res = await fetch(target, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
    })
    result.durationMs = Date.now() - start
    result.status = res.status
    result.statusText = res.statusText
    result.headers = Object.fromEntries(res.headers.entries())
    result.body = await res.text()
  } catch (err: any) {
    result.fetchError = {
      name: err?.name,
      message: err?.message,
      stack: err?.stack,
      cause: err?.cause ? String(err.cause) : undefined,
    }
  }

  return new Response(JSON.stringify(result, null, 2), {
    headers: { 'Content-Type': 'application/json' },
  })
}
