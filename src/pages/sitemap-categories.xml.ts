export const prerender = false

import { buildUrlset, xmlResponse } from '~/lib/sitemap'
import { supabase } from '~/lib/supabase'
import {
  logged,
  getCategories,
  getCategoriesByLocale,
  getBrandsByCategory,
  getBrandsByCategoryLocale,
  getBrandCategoryPairsWithFaults,
} from '~/lib/queries'
import { siteConfig } from 'site-config'

/** Categories, category+brand pages, model-index pages, problem-index pages, and brand hubs — small (7 categories, 5 brands), both locales. */
export async function GET() {
  const siteUrl = `https://${siteConfig.domain}`
  const urls: string[] = []

  const [{ data: catsEn }, { data: catsSv }, { data: allBrands }, faultPairsEn, faultPairsSv] = await Promise.all([
    getCategories(),
    getCategoriesByLocale('sv'),
    logged(supabase.from('brands').select('slug').eq('is_active', true), 'sitemap-categories:brands'),
    getBrandCategoryPairsWithFaults('en'),
    getBrandCategoryPairsWithFaults('sv'),
  ])

  // Brand hub pages: /brands/[slug]/
  for (const b of allBrands ?? []) {
    urls.push(`${siteUrl}/brands/${b.slug}/`)
    urls.push(`${siteUrl}/sv/brands/${b.slug}/`)
  }

  // Category index + category/brand + models-index pages
  for (const cat of catsEn ?? []) {
    urls.push(`${siteUrl}/${cat.slug}/`)
    const { data: brands } = await getBrandsByCategory(cat.slug)
    for (const b of brands ?? []) {
      urls.push(`${siteUrl}/${cat.slug}/${b.slug}/`)
      urls.push(`${siteUrl}/${cat.slug}/${b.slug}/models/`)
    }
  }
  for (const cat of catsSv ?? []) {
    urls.push(`${siteUrl}/sv/${cat.slug}/`)
    const { data: brands } = await getBrandsByCategoryLocale('sv', cat.slug)
    for (const b of brands ?? []) {
      urls.push(`${siteUrl}/sv/${cat.slug}/${b.slug}/`)
      urls.push(`${siteUrl}/sv/${cat.slug}/${b.slug}/models/`)
    }
  }

  // Problem (symptom) listing pages — only for brand+category combos that actually have faults
  for (const p of faultPairsEn) urls.push(`${siteUrl}/${p.category_slug}/${p.brand_slug}/problems/`)
  for (const p of faultPairsSv) urls.push(`${siteUrl}/sv/${p.category_slug}/${p.brand_slug}/problems/`)

  return xmlResponse(buildUrlset(urls))
}
