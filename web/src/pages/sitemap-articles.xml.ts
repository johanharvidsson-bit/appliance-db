export const prerender = false

import { buildUrlset, xmlResponse } from '~/lib/sitemap'
import { getAllArticleSlugs, getAllFaultArticleSlugs } from '~/lib/queries'
import { siteConfig } from 'site-config'

/** Error-code articles + fault (symptom) articles, both locales. */
export async function GET() {
  const siteUrl = `https://${siteConfig.domain}`

  const [{ data: ecEn }, { data: ecSv }, { data: faultEn }, { data: faultSv }] = await Promise.all([
    getAllArticleSlugs('en'),
    getAllArticleSlugs('sv'),
    getAllFaultArticleSlugs('en'),
    getAllFaultArticleSlugs('sv'),
  ])

  const urls = [
    ...(ecEn ?? []).map((a) => `${siteUrl}/${a.category_slug}/${a.brand_slug}/${a.slug}/`),
    ...(ecSv ?? []).map((a) => `${siteUrl}/sv/${a.category_slug}/${a.brand_slug}/${a.slug}/`),
    ...(faultEn ?? []).map((a) => `${siteUrl}/${a.category_slug}/${a.brand_slug}/problems/${a.slug}/`),
    ...(faultSv ?? []).map((a) => `${siteUrl}/sv/${a.category_slug}/${a.brand_slug}/problems/${a.slug}/`),
  ]

  return xmlResponse(buildUrlset(urls))
}
