export const prerender = false

import { buildSitemapIndex, xmlResponse } from '~/lib/sitemap'
import { siteConfig } from 'site-config'

const SUB_SITEMAPS = [
  'sitemap-static.xml',
  'sitemap-categories.xml',
  'sitemap-models-en.xml',
  'sitemap-models-sv.xml',
  'sitemap-articles.xml',
]

export async function GET() {
  const siteUrl = `https://${siteConfig.domain}`
  return xmlResponse(buildSitemapIndex(SUB_SITEMAPS.map((s) => `${siteUrl}/${s}`)))
}
