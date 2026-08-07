export const prerender = false

import { buildUrlset, xmlResponse } from '~/lib/sitemap'
import { siteConfig } from 'site-config'

const STATIC_PATHS = ['/', '/about/', '/affiliate-disclosure/', '/brands/', '/contact/', '/cookie-policy/', '/disclaimer/', '/privacy/', '/terms/']

export async function GET() {
  const siteUrl = `https://${siteConfig.domain}`
  const urls = [
    ...STATIC_PATHS.map((p) => `${siteUrl}${p}`),
    ...STATIC_PATHS.map((p) => `${siteUrl}/sv${p === '/' ? '/' : p}`),
  ]
  return xmlResponse(buildUrlset(urls))
}
