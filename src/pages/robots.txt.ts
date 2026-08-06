export const prerender = false

import { siteConfig } from 'site-config'

export async function GET() {
  const body = `User-agent: *\nDisallow:\n\nSitemap: https://${siteConfig.domain}/sitemap-index.xml\n`

  return new Response(body, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=0, s-maxage=86400, stale-while-revalidate=604800',
    },
  })
}
