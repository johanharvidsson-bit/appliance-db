/**
 * All Supabase queries, adjusted to the actual DB schema.
 *
 * Real schema (vs. spec):
 *  brands     → is_active (not active), no category_slugs array
 *  models     → brand_id + category_id FK ints (not brand_slug/category_slug strings)
 *  error_codes→ brand_id + category_id FK ints
 *  categories → slug_en (not slug)
 *  article_translations / articles → currently empty, handled gracefully
 */
import { supabase } from './supabase'
import { siteConfig } from 'site-config'

const LOCALE = siteConfig.defaultLocale

// ── Internal helpers ──────────────────────────────────────────────────────────

async function getCategoryId(categorySlug: string): Promise<number | null> {
  const { data } = await supabase.from('categories').select('id').eq('slug_en', categorySlug).single()
  return data?.id ?? null
}

// Looks up category_id by locale-specific slug.
// For 'en', uses categories.slug_en. For other locales, uses category_translations.slug.
async function getCategoryIdByLocaleSlug(locale: string, slug: string): Promise<number | null> {
  if (locale === 'en') return getCategoryId(slug)
  const { data } = await supabase
    .from('category_translations')
    .select('category_id')
    .eq('locale', locale)
    .eq('slug', slug)
    .single()
  return data?.category_id ?? null
}

async function getBrandId(brandSlug: string): Promise<number | null> {
  const { data } = await supabase.from('brands').select('id').eq('slug', brandSlug).single()
  return data?.id ?? null
}

// ── Categories ────────────────────────────────────────────────────────────────

export async function getCategories() {
  return supabase
    .from('category_translations')
    .select('slug, name, category_id')
    .eq('locale', LOCALE)
}

export async function getCategoryBySlug(slug: string) {
  return supabase
    .from('category_translations')
    .select('slug, name, category_id')
    .eq('locale', LOCALE)
    .eq('slug', slug)
    .single()
}

export async function getCategoryByLocaleSlug(locale: string, slug: string) {
  if (locale === 'en') return getCategoryBySlug(slug)
  return supabase
    .from('category_translations')
    .select('slug, name, category_id')
    .eq('locale', locale)
    .eq('slug', slug)
    .single()
}

// ── Brands ────────────────────────────────────────────────────────────────────

/**
 * Returns active brands that have at least one error code in the given category.
 * categorySlug is the category_translations.slug (e.g. "washing-machines").
 * The category.slug_en == categorySlug (e.g. "washing-machines").
 */
export async function getBrandsByCategory(categorySlug: string) {
  const catId = await getCategoryId(categorySlug)
  if (!catId) return { data: [], error: null }

  // Get distinct brand_ids with error codes in this category
  const { data: ecs } = await supabase
    .from('error_codes')
    .select('brand_id')
    .eq('category_id', catId)

  if (!ecs || ecs.length === 0) return { data: [], error: null }

  const brandIds = [...new Set(ecs.map((e) => e.brand_id))]

  return supabase
    .from('brands')
    .select('id, name, slug, logo_url')
    .in('id', brandIds)
    .eq('is_active', true)
}

export async function getBrandBySlug(brandSlug: string) {
  return supabase.from('brands').select('id, name, slug, logo_url').eq('slug', brandSlug).single()
}

// ── Models ────────────────────────────────────────────────────────────────────

export async function getModelsByBrandCategory(brandSlug: string, categorySlug: string) {
  const [brandId, catId] = await Promise.all([getBrandId(brandSlug), getCategoryId(categorySlug)])
  if (!brandId || !catId) return { data: [], error: null }

  return supabase
    .from('models')
    .select('id, name, slug, series, release_year')
    .eq('brand_id', brandId)
    .eq('category_id', catId)
    .order('name')
    .limit(2000)
}

export async function getModelBySlug(brandSlug: string, categorySlug: string, modelSlug: string) {
  const [brandId, catId] = await Promise.all([getBrandId(brandSlug), getCategoryId(categorySlug)])
  if (!brandId || !catId) return { data: null, error: 'Not found' }

  return supabase
    .from('models')
    .select('id, name, slug, release_year, manual_url, manual_pdf_url, brand_id, category_id')
    .eq('brand_id', brandId)
    .eq('category_id', catId)
    .eq('slug', modelSlug)
    .single()
}

/**
 * Returns all model slugs with their brand and category slugs (for getStaticPaths).
 * Joins brands and categories so we get slug strings from the IDs.
 */
export async function getAllModelSlugs() {
  // Only generate pages for models that belong to active brands
  const { data } = await supabase
    .from('models')
    .select('slug, brands!inner(slug, is_active), categories(slug_en)')
    .eq('brands.is_active', true)
    .limit(10000)

  // Reshape to { slug, brand_slug, category_slug }
  const shaped = (data ?? []).map((m: any) => ({
    slug: m.slug as string,
    brand_slug: m.brands?.slug as string,
    category_slug: m.categories?.slug_en as string,
  })).filter((m) => m.slug && m.brand_slug && m.category_slug)

  return { data: shaped, error: null }
}

// ── Error codes ───────────────────────────────────────────────────────────────

export async function getErrorCodesByBrandCategory(brandSlug: string, categorySlug: string) {
  const [brandId, catId] = await Promise.all([getBrandId(brandSlug), getCategoryId(categorySlug)])
  if (!brandId || !catId) return { data: [], error: null }

  return supabase
    .from('error_codes')
    .select(`
      id, code, short_description, description, severity,
      articles ( article_translations ( slug, locale ) )
    `)
    .eq('brand_id', brandId)
    .eq('category_id', catId)
    .order('code')
}

/**
 * Error codes for a model page – since there's no model_error_codes junction table,
 * we return all error codes for the model's brand+category.
 */
export async function getErrorCodesByModel(brandId: number, categoryId: number, locale = LOCALE) {
  return supabase
    .from('error_codes')
    .select(`
      id, code, short_description, description, severity,
      articles ( article_translations ( slug, locale, translation_status ) )
    `)
    .eq('brand_id', brandId)
    .eq('category_id', categoryId)
    .order('code')
}

// ── Articles ──────────────────────────────────────────────────────────────────

export async function getArticle(locale: string, slug: string) {
  return supabase
    .from('article_translations')
    .select(`
      slug, title_tag, meta_description, h1,
      quick_fix, intro_html,
      causes_json, steps_json, faq_json,
      affected_models_json, parts_json,
      prevention_html, when_to_call_technician_html,
      last_updated,
      articles (
        id,
        error_codes (
          code, display_text, severity, diy_possible,
          brands ( name, slug ),
          categories ( slug_en )
        )
      )
    `)
    .eq('locale', locale)
    .eq('slug', slug)
    .eq('translation_status', 'published')
    .single()
}

export async function getAllArticleSlugs(locale: string) {
  const { data } = await supabase
    .from('article_translations')
    .select(`
      slug,
      articles (
        id,
        error_codes (
          brands ( slug ),
          categories ( slug_en, category_translations ( slug, locale ) )
        )
      )
    `)
    .eq('locale', locale)
    .eq('translation_status', 'published')

  // Reshape to { slug, brand_slug, category_slug, article_id }
  const shaped = (data ?? []).map((at: any) => {
    const ec = at.articles?.error_codes
    const catTrans = (ec?.categories?.category_translations ?? []).find((ct: any) => ct.locale === locale)
    return {
      slug: at.slug as string,
      brand_slug: ec?.brands?.slug as string,
      category_slug: (catTrans?.slug ?? ec?.categories?.slug_en) as string,
      article_id: at.articles?.id as number,
    }
  }).filter((a) => a.slug && a.brand_slug && a.category_slug)

  return { data: shaped, error: null }
}

// ── Locale-aware queries (for non-EN routes) ──────────────────────────────────

/** All categories in a given locale (used by locale getStaticPaths). */
export async function getCategoriesByLocale(locale: string) {
  return supabase
    .from('category_translations')
    .select('slug, name, category_id')
    .eq('locale', locale)
}

/**
 * Returns all translations for a category (by category_id) across all locales.
 * Used to build hreflang alternate URLs for category and brand pages.
 */
export async function getCategoryAlternates(categoryId: number) {
  const { data } = await supabase
    .from('category_translations')
    .select('locale, slug')
    .eq('category_id', categoryId)
  return data ?? []
}

/** Brands with error codes in a category, looked up by locale-specific slug. */
export async function getBrandsByCategoryLocale(locale: string, categorySlug: string) {
  const catId = await getCategoryIdByLocaleSlug(locale, categorySlug)
  if (!catId) return { data: [], error: null }

  const { data: ecs } = await supabase
    .from('error_codes')
    .select('brand_id')
    .eq('category_id', catId)

  if (!ecs || ecs.length === 0) return { data: [], error: null }

  const brandIds = [...new Set(ecs.map((e) => e.brand_id))]
  return supabase
    .from('brands')
    .select('id, name, slug, logo_url')
    .in('id', brandIds)
    .eq('is_active', true)
}

/** Error codes for a brand+category in a given locale (slug resolved by locale). */
export async function getErrorCodesByBrandCategoryLocale(
  locale: string,
  brandSlug: string,
  categorySlug: string
) {
  const [brandId, catId] = await Promise.all([
    getBrandId(brandSlug),
    getCategoryIdByLocaleSlug(locale, categorySlug),
  ])
  if (!brandId || !catId) return { data: [], error: null }

  return supabase
    .from('error_codes')
    .select(`
      id, code, display_text, severity, diy_possible,
      articles ( article_translations ( slug, locale ) )
    `)
    .eq('brand_id', brandId)
    .eq('category_id', catId)
    .order('code')
}

/** Models for a brand+category in a given locale (slug resolved by locale). */
export async function getModelsByBrandCategoryLocale(
  locale: string,
  brandSlug: string,
  categorySlug: string
) {
  const [brandId, catId] = await Promise.all([
    getBrandId(brandSlug),
    getCategoryIdByLocaleSlug(locale, categorySlug),
  ])
  if (!brandId || !catId) return { data: [], error: null }

  return supabase
    .from('models')
    .select('id, name, slug, series, release_year')
    .eq('brand_id', brandId)
    .eq('category_id', catId)
    .order('name')
    .limit(2000)
}

/**
 * All published translations for a given article (by articleId).
 * Returns [{locale, slug, brand_slug, category_slug}] — used to build hreflang tags.
 */
export async function getArticleAlternates(articleId: number) {
  const { data } = await supabase
    .from('article_translations')
    .select(`
      slug, locale,
      articles (
        error_codes (
          brands ( slug ),
          categories ( slug_en, category_translations ( slug, locale ) )
        )
      )
    `)
    .eq('article_id', articleId)
    .eq('translation_status', 'published')

  return (data ?? []).map((at: any) => {
    const ec = at.articles?.error_codes
    const catTrans = (ec?.categories?.category_translations ?? []).find((ct: any) => ct.locale === at.locale)
    return {
      locale: at.locale as string,
      slug: at.slug as string,
      brand_slug: ec?.brands?.slug as string,
      category_slug: (catTrans?.slug ?? ec?.categories?.slug_en) as string,
    }
  }).filter((a: any) => a.slug && a.brand_slug && a.category_slug)
}

// ── Faults ────────────────────────────────────────────────────────────────────

// Internal: resolve brand_id + category_id → brand/category slugs for a set of pairs.
async function resolveBrandCategorySlugs(
  pairs: { brand_id: number; category_id: number }[],
  locale: string
): Promise<{ brand_id: number; category_id: number; brand_slug: string; category_slug: string }[]> {
  if (pairs.length === 0) return []
  const brandIds = [...new Set(pairs.map((p) => p.brand_id))]
  const catIds = [...new Set(pairs.map((p) => p.category_id))]

  const [brandsResult, catsResult] = await Promise.all([
    supabase.from('brands').select('id, slug').in('id', brandIds).eq('is_active', true),
    locale === 'en'
      ? supabase.from('categories').select('id, slug_en').in('id', catIds)
      : supabase.from('category_translations').select('category_id, slug').eq('locale', locale).in('category_id', catIds),
  ])

  const brandMap = new Map<number, string>()
  for (const b of brandsResult.data ?? []) brandMap.set(b.id, b.slug)

  const catMap = new Map<number, string>()
  if (locale === 'en') {
    for (const c of catsResult.data ?? []) catMap.set((c as any).id, (c as any).slug_en)
  } else {
    for (const c of catsResult.data ?? []) catMap.set((c as any).category_id, (c as any).slug)
  }

  return pairs
    .map((p) => ({
      brand_id: p.brand_id,
      category_id: p.category_id,
      brand_slug: brandMap.get(p.brand_id) ?? '',
      category_slug: catMap.get(p.category_id) ?? '',
    }))
    .filter((p) => p.brand_slug && p.category_slug)
}

/**
 * Returns brand+category combos that have faults, with locale-specific category slugs.
 * Used by getStaticPaths for fault listing pages.
 * Avoids FK joins from faults → brands/categories (those may not be registered in PostgREST).
 */
export async function getBrandCategoryPairsWithFaults(locale: string) {
  const { data: rows } = await supabase.from('faults').select('brand_id, category_id')
  if (!rows || rows.length === 0) return []

  const seen = new Set<string>()
  const uniquePairs: { brand_id: number; category_id: number }[] = []
  for (const row of rows) {
    const key = `${row.brand_id}-${row.category_id}`
    if (!seen.has(key)) { seen.add(key); uniquePairs.push(row) }
  }

  return resolveBrandCategorySlugs(uniquePairs, locale)
}

// Internal: given a list of fault rows, attach article_translation slugs for the given locale.
// Avoids relying on faults→articles FK join (may not be registered in PostgREST).
async function attachFaultArticleSlugs(faults: any[], locale: string): Promise<any[]> {
  if (faults.length === 0) return faults
  const faultIds = faults.map((f) => f.id)

  const { data: artRows } = await supabase
    .from('articles')
    .select('fault_id, article_translations ( slug, locale, translation_status )')
    .in('fault_id', faultIds)
    .eq('article_type', 'fault')

  // Build map: fault_id → article_translation for the given locale
  const slugMap = new Map<number, string>()
  for (const art of artRows ?? []) {
    const ats: any[] = art.article_translations ?? []
    const at = ats.find((t: any) => t.locale === locale && t.translation_status === 'published')
            ?? ats.find((t: any) => t.locale === 'en'    && t.translation_status === 'published')
    if (at?.slug) slugMap.set(art.fault_id, at.slug)
  }

  return faults.map((row) => ({ ...row, article_slug: slugMap.get(row.id) ?? null }))
}

/**
 * Faults for a model page's "Common faults" section.
 * brand_id and category_id are integers (already resolved from the model row).
 */
export async function getFaultsByBrandCategoryId(brandId: number, categoryId: number, locale: string) {
  const { data, error } = await supabase
    .from('faults')
    .select('id, slug, severity, has_error_code, fault_translations ( symptom_name, meta_description, locale )')
    .eq('brand_id', brandId)
    .eq('category_id', categoryId)
    .order('id')

  if (!data) return { data: [], error }

  const filtered = data.map((row: any) => ({
    ...row,
    fault_translations: (row.fault_translations ?? []).filter((t: any) => t.locale === locale),
  })).filter((row: any) => row.fault_translations.length > 0)

  return { data: await attachFaultArticleSlugs(filtered, locale), error: null }
}

/**
 * Faults for a fault listing page (resolves brand+category from slugs).
 */
export async function getFaultsByBrandCategoryLocale(locale: string, brandSlug: string, categorySlug: string) {
  const [brandId, catId] = await Promise.all([
    getBrandId(brandSlug),
    getCategoryIdByLocaleSlug(locale, categorySlug),
  ])
  if (!brandId || !catId) return { data: [], error: null }

  const { data, error } = await supabase
    .from('faults')
    .select('id, slug, severity, has_error_code, fault_translations ( symptom_name, meta_description, locale )')
    .eq('brand_id', brandId)
    .eq('category_id', catId)
    .order('id')

  if (!data) return { data: [], error }

  const filtered = data.map((row: any) => ({
    ...row,
    fault_translations: (row.fault_translations ?? []).filter((t: any) => t.locale === locale),
  })).filter((row: any) => row.fault_translations.length > 0)

  return { data: await attachFaultArticleSlugs(filtered, locale), error: null }
}

/**
 * All published fault article slugs for a given locale (for getStaticPaths).
 * Returns { slug, brand_slug, category_slug, article_id }.
 */
export async function getAllFaultArticleSlugs(locale: string) {
  // Step 1: get published fault article translations with their article row
  const { data: atRows } = await supabase
    .from('article_translations')
    .select('slug, articles!inner ( id, article_type, fault_id )')
    .eq('locale', locale)
    .eq('translation_status', 'published')
    .eq('articles.article_type', 'fault')

  if (!atRows || atRows.length === 0) return { data: [], error: null }

  // Step 2: collect unique fault_ids
  const faultIds = [...new Set((atRows as any[]).map((r: any) => r.articles?.fault_id).filter(Boolean))]
  if (faultIds.length === 0) return { data: [], error: null }

  // Step 3: look up brand_id + category_id for each fault
  const { data: faultRows } = await supabase
    .from('faults').select('id, brand_id, category_id').in('id', faultIds)
  const faultMap = new Map<number, { brand_id: number; category_id: number }>()
  for (const f of faultRows ?? []) faultMap.set(f.id, { brand_id: f.brand_id, category_id: f.category_id })

  // Step 4: resolve to slugs
  const pairs = [...faultMap.values()]
  const resolved = await resolveBrandCategorySlugs(
    // dedupe
    [...new Map(pairs.map((p) => [`${p.brand_id}-${p.category_id}`, p])).values()],
    locale
  )
  const pairSlugMap = new Map<string, { brand_slug: string; category_slug: string }>()
  for (const r of resolved) pairSlugMap.set(`${r.brand_id}-${r.category_id}`, r)

  const shaped = (atRows as any[]).map((at: any) => {
    const faultId = at.articles?.fault_id
    const fault = faultId ? faultMap.get(faultId) : null
    if (!fault) return null
    const slugs = pairSlugMap.get(`${fault.brand_id}-${fault.category_id}`)
    if (!slugs) return null
    return {
      slug: at.slug as string,
      brand_slug: slugs.brand_slug,
      category_slug: slugs.category_slug,
      article_id: at.articles?.id as number,
    }
  }).filter((a): a is NonNullable<typeof a> => !!a && !!a.slug && !!a.brand_slug && !!a.category_slug)

  return { data: shaped, error: null }
}

/**
 * Full fault article content for a given locale + slug.
 * Omits brand/category joins from faults (those FKs may not be in PostgREST).
 */
export async function getFaultArticle(locale: string, slug: string) {
  return supabase
    .from('article_translations')
    .select(`
      slug, title_tag, meta_description, h1,
      quick_fix, intro_html,
      causes_json, steps_json, faq_json,
      prevention_html, when_to_call_technician_html,
      last_updated,
      articles (
        id,
        faults ( id, slug, severity, has_error_code )
      )
    `)
    .eq('locale', locale)
    .eq('slug', slug)
    .eq('translation_status', 'published')
    .single()
}

/**
 * All published locale translations for a fault article (for hreflang).
 */
export async function getFaultArticleAlternates(articleId: number) {
  // Step 1: get translations + fault_id
  const { data: atRows } = await supabase
    .from('article_translations')
    .select('slug, locale, articles!inner ( fault_id )')
    .eq('article_id', articleId)
    .eq('translation_status', 'published')

  if (!atRows || atRows.length === 0) return []

  const faultId = (atRows[0] as any).articles?.fault_id
  if (!faultId) return []

  // Step 2: get brand_id + category_id from fault
  const { data: faultRow } = await supabase
    .from('faults').select('brand_id, category_id').eq('id', faultId).single()
  if (!faultRow) return []

  // Step 3: resolve slugs for all locales present
  const locales = [...new Set((atRows as any[]).map((r: any) => r.locale as string))]
  const brandMap = new Map<number, string>()
  const { data: brandRow } = await supabase.from('brands').select('id, slug').eq('id', faultRow.brand_id).single()
  if (brandRow) brandMap.set(brandRow.id, brandRow.slug)

  const catSlugMap = new Map<string, string>()
  const { data: catEN } = await supabase.from('categories').select('slug_en').eq('id', faultRow.category_id).single()
  if (catEN) catSlugMap.set('en', catEN.slug_en)
  const nonEnLocales = locales.filter((l) => l !== 'en')
  if (nonEnLocales.length > 0) {
    const { data: catTrans } = await supabase
      .from('category_translations').select('locale, slug')
      .eq('category_id', faultRow.category_id).in('locale', nonEnLocales)
    for (const ct of catTrans ?? []) catSlugMap.set(ct.locale, ct.slug)
  }

  return (atRows as any[]).map((at: any) => ({
    locale: at.locale as string,
    slug: at.slug as string,
    brand_slug: brandMap.get(faultRow.brand_id) ?? '',
    category_slug: catSlugMap.get(at.locale) ?? catSlugMap.get('en') ?? '',
  })).filter((a: any) => a.slug && a.brand_slug && a.category_slug)
}

/**
 * Error codes linked to a fault via fault_error_code_map (for "Related error codes" section).
 */
export async function getFaultErrorCodes(faultId: number, locale: string) {
  return supabase
    .from('fault_error_code_map')
    .select(`
      error_codes (
        code, display_text,
        articles ( article_translations ( slug, locale, translation_status ) )
      )
    `)
    .eq('fault_id', faultId)
}

export async function getRelatedArticles(excludeSlug: string, limit = 5) {
  return supabase
    .from('article_translations')
    .select(`
      slug, title_tag, quick_fix,
      articles (
        error_codes (
          code, display_text, severity
        )
      )
    `)
    .eq('locale', LOCALE)
    .eq('translation_status', 'published')
    .neq('slug', excludeSlug)
    .limit(limit)
}
