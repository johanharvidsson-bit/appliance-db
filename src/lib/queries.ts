/**
 * All Supabase queries, adjusted to the actual DB schema.
 *
 * Real schema (vs. spec):
 *  brands     → is_active (not active), no category_slugs array
 *  models     → brand_id + category_id FK ints (not brand_slug/category_slug strings)
 *  error_codes→ brand_id + category_id FK ints
 *  categories → slug_en (not slug)
 *  article_translations / articles → currently empty, handled gracefully
 *
 * Error handling: every query goes through `logged()` (single query) or
 * `paginateAll()` (paginated query) so that PostgREST/DB errors are logged
 * server-side instead of silently becoming an empty result. This matters more
 * now that the DB is a single self-hosted VPS instead of managed Supabase Cloud —
 * a DB/network hiccup should show up in Cloudflare Pages Function logs, not
 * just render as "no data" on the page.
 */
import { supabase } from './supabase'
import { siteConfig } from 'site-config'

const LOCALE = siteConfig.defaultLocale
const PAGE_SIZE = 1000

// ── Error logging helpers ──────────────────────────────────────────────────────

/**
 * Awaits a single PostgREST query and logs (without throwing) if it errored.
 * Typed loosely as `any` on purpose: the Supabase client here isn't given a
 * Database generic (see `src/lib/supabase.ts`), so query results are already
 * effectively untyped everywhere in this codebase — trying to thread a real
 * generic through this wrapper made TypeScript infer `never` for some embedded
 * (joined) selects instead of `any`, breaking callers.
 */
async function logged(promise: PromiseLike<{ data: any; error: any }>, label: string): Promise<{ data: any; error: any }> {
  const result = await promise
  if (result.error) console.error(`[queries:${label}]`, result.error)
  return result
}

/**
 * Paginates through a PostgREST query in PAGE_SIZE-row chunks — PostgREST caps
 * unpaginated selects at 1000 rows, which several tables here exceed (e.g.
 * ~35k models). Replaces the near-identical `while(true) { .range(...) }`
 * loop that used to be copy-pasted in 5 different query functions.
 */
async function paginateAll(
  buildQuery: (from: number, to: number) => PromiseLike<{ data: any[] | null; error: any }>,
  label: string
): Promise<any[]> {
  const all: any[] = []
  let offset = 0
  while (true) {
    const { data, error } = await buildQuery(offset, offset + PAGE_SIZE - 1)
    if (error) console.error(`[queries:${label}]`, error)
    if (error || !data?.length) break
    all.push(...data)
    if (data.length < PAGE_SIZE) break
    offset += PAGE_SIZE
  }
  return all
}

// ── Internal helpers ──────────────────────────────────────────────────────────

async function getCategoryId(categorySlug: string): Promise<number | null> {
  const { data } = await logged(
    supabase.from('categories').select('id').eq('slug_en', categorySlug).single(),
    `getCategoryId(${categorySlug})`
  )
  return data?.id ?? null
}

// Looks up category_id by locale-specific slug.
// For 'en', uses categories.slug_en. For other locales, uses category_translations.slug.
async function getCategoryIdByLocaleSlug(locale: string, slug: string): Promise<number | null> {
  if (locale === 'en') return getCategoryId(slug)
  const { data } = await logged(
    supabase.from('category_translations').select('category_id').eq('locale', locale).eq('slug', slug).single(),
    `getCategoryIdByLocaleSlug(${locale}, ${slug})`
  )
  return data?.category_id ?? null
}

async function getBrandId(brandSlug: string): Promise<number | null> {
  const { data } = await logged(
    supabase.from('brands').select('id').eq('slug', brandSlug).single(),
    `getBrandId(${brandSlug})`
  )
  return data?.id ?? null
}

// ── Categories ────────────────────────────────────────────────────────────────

export async function getCategories() {
  return logged(
    supabase.from('category_translations').select('slug, name, category_id').eq('locale', LOCALE),
    'getCategories'
  )
}

export async function getCategoryBySlug(slug: string) {
  return logged(
    supabase.from('category_translations').select('slug, name, category_id').eq('locale', LOCALE).eq('slug', slug).single(),
    `getCategoryBySlug(${slug})`
  )
}

export async function getCategoryByLocaleSlug(locale: string, slug: string) {
  if (locale === 'en') return getCategoryBySlug(slug)
  return logged(
    supabase.from('category_translations').select('slug, name, category_id').eq('locale', locale).eq('slug', slug).single(),
    `getCategoryByLocaleSlug(${locale}, ${slug})`
  )
}

// ── Brands ────────────────────────────────────────────────────────────────────

/**
 * Returns active brands that have at least one model in the given category.
 * categorySlug is the category_translations.slug (e.g. "washing-machines").
 * The category.slug_en == categorySlug (e.g. "washing-machines").
 *
 * Gates on models rather than error_codes: error codes have so far only been
 * scraped for washing-machines, which left every other category's page
 * showing "No brands available" even though thousands of model pages exist
 * and render fine (specs, variants, etc. don't require an error code).
 */
export async function getBrandsByCategory(categorySlug: string) {
  const catId = await getCategoryId(categorySlug)
  if (!catId) return { data: [], error: null }

  // Paginated — a category can have thousands of models, past the 1000-row default cap.
  const modelRows = await paginateAll(
    (from, to) => supabase.from('models').select('brand_id').eq('category_id', catId).range(from, to),
    `getBrandsByCategory:models(${categorySlug})`
  )

  if (modelRows.length === 0) return { data: [], error: null }

  const brandIds = [...new Set(modelRows.map((m) => m.brand_id))]

  return logged(
    supabase.from('brands').select('id, name, slug, logo_url').in('id', brandIds).eq('is_active', true),
    `getBrandsByCategory:brands(${categorySlug})`
  )
}

export async function getBrandBySlug(brandSlug: string) {
  return logged(
    supabase.from('brands').select('id, name, slug, logo_url').eq('slug', brandSlug).single(),
    `getBrandBySlug(${brandSlug})`
  )
}

// ── Models ────────────────────────────────────────────────────────────────────

export async function getModelsByBrandCategory(brandSlug: string, categorySlug: string) {
  const [brandId, catId] = await Promise.all([getBrandId(brandSlug), getCategoryId(categorySlug)])
  if (!brandId || !catId) return { data: [], error: null }

  const all = await paginateAll(
    (from, to) =>
      supabase
        .from('models')
        .select('id, name, slug, series, release_year')
        .eq('brand_id', brandId)
        .eq('category_id', catId)
        .order('name')
        .range(from, to),
    `getModelsByBrandCategory(${brandSlug}, ${categorySlug})`
  )
  return { data: all, error: null }
}

export async function getModelBySlug(brandSlug: string, categorySlug: string, modelSlug: string, locale: string = LOCALE) {
  const [brandId, catId] = await Promise.all([getBrandId(brandSlug), getCategoryIdByLocaleSlug(locale, categorySlug)])
  if (!brandId || !catId) return { data: null, error: 'Not found' }

  return logged(
    supabase
      .from('models')
      .select('id, name, slug, series, release_year, manual_url, manual_pdf_url, brand_id, category_id')
      .eq('brand_id', brandId)
      .eq('category_id', catId)
      .eq('slug', modelSlug)
      .single(),
    `getModelBySlug(${brandSlug}, ${categorySlug}, ${modelSlug})`
  )
}

/** Other models in the same series (for "Alternate models" section on model pages). */
export async function getModelsBySeries(brandId: number, categoryId: number, series: string, excludeSlug: string) {
  const { data, error } = await logged(
    supabase
      .from('models')
      .select('id, name, slug')
      .eq('brand_id', brandId)
      .eq('category_id', categoryId)
      .eq('series', series)
      .neq('slug', excludeSlug)
      .order('name')
      .limit(50),
    `getModelsBySeries(${brandId}, ${categoryId}, ${series})`
  )
  return data ?? []
}

/**
 * Returns all model slugs with their brand and category slugs (for getStaticPaths).
 * Joins brands and categories so we get slug strings from the IDs.
 */
export async function getAllModelSlugs() {
  const all = await paginateAll(
    (from, to) =>
      supabase
        .from('models')
        .select('slug, brands!inner(slug, is_active), categories(slug_en)')
        .eq('brands.is_active', true)
        .range(from, to),
    'getAllModelSlugs'
  )

  const shaped = all.map((m: any) => ({
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

  return logged(
    supabase
      .from('error_codes')
      .select(`
        id, code, short_description, description, severity,
        articles ( article_translations ( slug, locale ) )
      `)
      .eq('brand_id', brandId)
      .eq('category_id', catId)
      .order('code'),
    `getErrorCodesByBrandCategory(${brandSlug}, ${categorySlug})`
  )
}

/**
 * Error codes for a model page – since there's no model_error_codes junction table,
 * we return all error codes for the model's brand+category.
 */
export async function getErrorCodesByModel(brandId: number, categoryId: number, locale = LOCALE) {
  return logged(
    supabase
      .from('error_codes')
      .select(`
        id, code, short_description, description, severity,
        articles ( article_translations ( slug, locale, translation_status ) )
      `)
      .eq('brand_id', brandId)
      .eq('category_id', categoryId)
      .order('code'),
    `getErrorCodesByModel(${brandId}, ${categoryId})`
  )
}

// ── Articles ──────────────────────────────────────────────────────────────────

// EN: published only. Other locales: also serve machine-translated 'pending' content.
function publishedStatuses(locale: string): string[] {
  return locale === 'en' ? ['published'] : ['published', 'pending']
}

/**
 * Targeted single-row lookup: is this (locale, category, brand, slug) an
 * error-code article? Used by the on-demand [slug] route to decide between
 * the article and model view without fetching the full article slug list.
 * Slugs are only unique per brand (not globally), so brand+category must be
 * part of the match — see migration 007's note on article_translations.
 */
export async function getArticleBySlug(locale: string, categorySlug: string, brandSlug: string, slug: string) {
  const catId = await getCategoryIdByLocaleSlug(locale, categorySlug)
  if (!catId) return null

  const { data } = await logged(
    supabase
      .from('article_translations')
      .select(`
        slug,
        articles!inner (
          id,
          error_codes!inner ( brands!inner(slug), category_id )
        )
      `)
      .eq('locale', locale)
      .eq('slug', slug)
      .eq('articles.error_codes.brands.slug', brandSlug)
      .eq('articles.error_codes.category_id', catId)
      .in('translation_status', publishedStatuses(locale))
      .maybeSingle(),
    `getArticleBySlug(${locale}, ${categorySlug}, ${brandSlug}, ${slug})`
  )

  if (!data) return null
  return { article_id: (data as any).articles.id as number }
}

export async function getArticle(locale: string, articleId: number) {
  return logged(
    supabase
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
      .eq('article_id', articleId)
      .in('translation_status', publishedStatuses(locale))
      .single(),
    `getArticle(${locale}, ${articleId})`
  )
}

export async function getAllArticleSlugs(locale: string) {
  const { data } = await logged(
    supabase
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
      .in('translation_status', publishedStatuses(locale)),
    `getAllArticleSlugs(${locale})`
  )

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
  return logged(
    supabase.from('category_translations').select('slug, name, category_id').eq('locale', locale),
    `getCategoriesByLocale(${locale})`
  )
}

/**
 * Returns all translations for a category (by category_id) across all locales.
 * Used to build hreflang alternate URLs for category and brand pages.
 */
export async function getCategoryAlternates(categoryId: number) {
  const { data } = await logged(
    supabase.from('category_translations').select('locale, slug').eq('category_id', categoryId),
    `getCategoryAlternates(${categoryId})`
  )
  return data ?? []
}

/** Brands with models in a category, looked up by locale-specific slug. */
export async function getBrandsByCategoryLocale(locale: string, categorySlug: string) {
  const catId = await getCategoryIdByLocaleSlug(locale, categorySlug)
  if (!catId) return { data: [], error: null }

  // Paginated — a category can have thousands of models, past the
  // 1000-row default cap on an unpaginated select.
  const modelRows = await paginateAll(
    (from, to) => supabase.from('models').select('brand_id').eq('category_id', catId).range(from, to),
    `getBrandsByCategoryLocale:models(${locale}, ${categorySlug})`
  )

  if (modelRows.length === 0) return { data: [], error: null }

  const brandIds = [...new Set(modelRows.map((m) => m.brand_id))]
  return logged(
    supabase.from('brands').select('id, name, slug, logo_url').in('id', brandIds).eq('is_active', true),
    `getBrandsByCategoryLocale:brands(${locale}, ${categorySlug})`
  )
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

  return logged(
    supabase
      .from('error_codes')
      .select(`
        id, code, display_text, severity, diy_possible,
        articles ( article_translations ( slug, locale ) )
      `)
      .eq('brand_id', brandId)
      .eq('category_id', catId)
      .order('code'),
    `getErrorCodesByBrandCategoryLocale(${locale}, ${brandSlug}, ${categorySlug})`
  )
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

  const all = await paginateAll(
    (from, to) =>
      supabase
        .from('models')
        .select('id, name, slug, series, release_year')
        .eq('brand_id', brandId)
        .eq('category_id', catId)
        .order('name')
        .range(from, to),
    `getModelsByBrandCategoryLocale(${locale}, ${brandSlug}, ${categorySlug})`
  )
  return { data: all, error: null }
}

/**
 * All published translations for a given article (by articleId).
 * Returns [{locale, slug, brand_slug, category_slug}] — used to build hreflang tags.
 */
export async function getArticleAlternates(articleId: number) {
  const { data } = await logged(
    supabase
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
      .in('translation_status', ['published', 'pending']),
    `getArticleAlternates(${articleId})`
  )

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
    logged(supabase.from('brands').select('id, slug').in('id', brandIds).eq('is_active', true), 'resolveBrandCategorySlugs:brands'),
    locale === 'en'
      ? logged(supabase.from('categories').select('id, slug_en').in('id', catIds), 'resolveBrandCategorySlugs:categories')
      : logged(
          supabase.from('category_translations').select('category_id, slug').eq('locale', locale).in('category_id', catIds),
          'resolveBrandCategorySlugs:category_translations'
        ),
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
  const { data: rows } = await logged(supabase.from('faults').select('brand_id, category_id'), 'getBrandCategoryPairsWithFaults')
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

  const { data: artRows } = await logged(
    supabase
      .from('articles')
      .select('fault_id, article_translations ( slug, locale, translation_status )')
      .in('fault_id', faultIds)
      .eq('article_type', 'fault'),
    'attachFaultArticleSlugs'
  )

  // Build map: fault_id → article_translation for the given locale
  const allowed = publishedStatuses(locale)
  const slugMap = new Map<number, string>()
  for (const art of artRows ?? []) {
    const ats: any[] = art.article_translations ?? []
    const at = ats.find((t: any) => t.locale === locale && allowed.includes(t.translation_status))
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
  const { data, error } = await logged(
    supabase
      .from('faults')
      .select('id, slug, severity, has_error_code, fault_translations ( symptom_name, meta_description, locale )')
      .eq('brand_id', brandId)
      .eq('category_id', categoryId)
      .order('id'),
    `getFaultsByBrandCategoryId(${brandId}, ${categoryId})`
  )

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

  const { data, error } = await logged(
    supabase
      .from('faults')
      .select('id, slug, severity, has_error_code, fault_translations ( symptom_name, meta_description, locale )')
      .eq('brand_id', brandId)
      .eq('category_id', catId)
      .order('id'),
    `getFaultsByBrandCategoryLocale(${locale}, ${brandSlug}, ${categorySlug})`
  )

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
  // Step 1: get published/pending fault article translations with their article row
  const { data: atRows } = await logged(
    supabase
      .from('article_translations')
      .select('slug, articles!inner ( id, article_type, fault_id )')
      .eq('locale', locale)
      .in('translation_status', publishedStatuses(locale))
      .eq('articles.article_type', 'fault'),
    `getAllFaultArticleSlugs:translations(${locale})`
  )

  if (!atRows || atRows.length === 0) return { data: [], error: null }

  // Step 2: collect unique fault_ids
  const faultIds = [...new Set((atRows as any[]).map((r: any) => r.articles?.fault_id).filter(Boolean))]
  if (faultIds.length === 0) return { data: [], error: null }

  // Step 3: look up brand_id + category_id for each fault
  const { data: faultRows } = await logged(
    supabase.from('faults').select('id, brand_id, category_id').in('id', faultIds),
    `getAllFaultArticleSlugs:faults(${locale})`
  )
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
 * Only selects articles.id and articles.fault_id (both plain columns, no nested FK joins)
 * to avoid PostgREST errors from unregistered articles→faults FK.
 */
export async function getFaultArticle(locale: string, articleId: number) {
  return logged(
    supabase
      .from('article_translations')
      .select(`
        slug, title_tag, meta_description, h1,
        quick_fix, intro_html,
        causes_json, steps_json, faq_json,
        prevention_html, when_to_call_technician_html,
        last_updated
      `)
      .eq('locale', locale)
      .eq('article_id', articleId)
      .in('translation_status', publishedStatuses(locale))
      .single(),
    `getFaultArticle(${locale}, ${articleId})`
  )
}

/** Get fault_id for an article (used on fault article pages where articleId is in props). */
export async function getArticleFaultId(articleId: number) {
  const { data } = await logged(
    supabase.from('articles').select('fault_id').eq('id', articleId).single(),
    `getArticleFaultId(${articleId})`
  )
  return (data as any)?.fault_id as number | null ?? null
}

/** Fault metadata (severity, has_error_code) for a fault article's meta bar. */
export async function getFaultById(faultId: number) {
  return logged(
    supabase.from('faults').select('id, slug, severity, has_error_code').eq('id', faultId).single(),
    `getFaultById(${faultId})`
  )
}

/**
 * All published locale translations for a fault article (for hreflang).
 */
export async function getFaultArticleAlternates(articleId: number) {
  // Step 1: get translations + fault_id
  const { data: atRows } = await logged(
    supabase
      .from('article_translations')
      .select('slug, locale, articles!inner ( fault_id )')
      .eq('article_id', articleId)
      .in('translation_status', ['published', 'pending']),
    `getFaultArticleAlternates:translations(${articleId})`
  )

  if (!atRows || atRows.length === 0) return []

  const faultId = (atRows[0] as any).articles?.fault_id
  if (!faultId) return []

  // Step 2: get brand_id + category_id from fault
  const { data: faultRow } = await logged(
    supabase.from('faults').select('brand_id, category_id').eq('id', faultId).single(),
    `getFaultArticleAlternates:fault(${faultId})`
  )
  if (!faultRow) return []

  // Step 3: resolve slugs for all locales present
  const locales = [...new Set((atRows as any[]).map((r: any) => r.locale as string))]
  const brandMap = new Map<number, string>()
  const { data: brandRow } = await logged(
    supabase.from('brands').select('id, slug').eq('id', faultRow.brand_id).single(),
    `getFaultArticleAlternates:brand(${faultRow.brand_id})`
  )
  if (brandRow) brandMap.set(brandRow.id, brandRow.slug)

  const catSlugMap = new Map<string, string>()
  const { data: catEN } = await logged(
    supabase.from('categories').select('slug_en').eq('id', faultRow.category_id).single(),
    `getFaultArticleAlternates:categoryEN(${faultRow.category_id})`
  )
  if (catEN) catSlugMap.set('en', catEN.slug_en)
  const nonEnLocales = locales.filter((l) => l !== 'en')
  if (nonEnLocales.length > 0) {
    const { data: catTrans } = await logged(
      supabase
        .from('category_translations').select('locale, slug')
        .eq('category_id', faultRow.category_id).in('locale', nonEnLocales),
      `getFaultArticleAlternates:categoryTranslations(${faultRow.category_id})`
    )
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
  return logged(
    supabase
      .from('fault_error_code_map')
      .select(`
        error_codes (
          code, display_text,
          articles ( article_translations ( slug, locale, translation_status ) )
        )
      `)
      .eq('fault_id', faultId),
    `getFaultErrorCodes(${faultId})`
  )
}

export async function getWashingMachineSpecs(modelId: number) {
  const { data } = await logged(
    supabase
      .from('washing_machine_specs')
      .select('capacity_kg, spin_speed_rpm, energy_class, width_mm, height_mm, depth_mm, noise_spinning_db, energy_consumption_kwh, water_consumption_l, door_type')
      .eq('model_id', modelId)
      .single(),
    `getWashingMachineSpecs(${modelId})`
  )
  return data as Record<string, any> | null
}

export async function getRelatedArticles(excludeSlug: string, limit = 5) {
  return logged(
    supabase
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
      .limit(limit),
    `getRelatedArticles(${excludeSlug})`
  )
}
