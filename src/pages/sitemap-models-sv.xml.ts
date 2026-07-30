export const prerender = false

import { buildUrlset, xmlResponse } from '~/lib/sitemap'
import { getAllModelSlugsForSitemap } from '~/lib/queries'
import { siteConfig } from 'site-config'

export async function GET() {
  const siteUrl = `https://${siteConfig.domain}`
  const models = await getAllModelSlugsForSitemap()
  const urls = models.map((m) => `${siteUrl}/sv/${m.category_slug_sv}/${m.brand_slug}/${m.slug}/`)
  return xmlResponse(buildUrlset(urls))
}
