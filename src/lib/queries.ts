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
