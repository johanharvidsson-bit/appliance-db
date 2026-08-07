export interface LocaleInfo {
  code: string
  name: string
  flag: string
  active: boolean
}

/**
 * Single source of truth for supported locale codes. Previously this list was
 * hand-duplicated in `astro.config.ts` (`i18n.locales`), `src/lib/ui.ts` (the
 * `Locale` type), and `src/pages/404.astro` — all four had to be kept in sync
 * by hand. Now `astro.config.ts` and `ui.ts` both derive from this array; only
 * `ui.ts`'s translation dictionary still needs a manual entry per code (an
 * empty `{}` for locales with no translations yet).
 */
export const LOCALES = [
  { code: 'en', name: 'English',  flag: '🇬🇧', active: true },
  { code: 'sv', name: 'Svenska',  flag: '🇸🇪', active: true },
  { code: 'de', name: 'Deutsch',  flag: '🇩🇪', active: false },
  { code: 'fr', name: 'Français', flag: '🇫🇷', active: false },
  { code: 'es', name: 'Español',  flag: '🇪🇸', active: false },
  { code: 'pl', name: 'Polski',   flag: '🇵🇱', active: false },
] as const satisfies readonly LocaleInfo[]

export type LocaleCode = (typeof LOCALES)[number]['code']

export const ACTIVE_LOCALES = LOCALES.filter((l) => l.active).map((l) => l.code)

/** Active non-English locales — the ones that get /[locale]/ prefixed routes. */
export const NON_EN_ACTIVE_LOCALES = ACTIVE_LOCALES.filter((l) => l !== 'en')

export function getLocaleInfo(code: string): LocaleInfo {
  return LOCALES.find((l) => l.code === code) ?? LOCALES[0]
}

/** Build hreflang URL for an article alternate. */
export function buildAlternateUrl(
  siteUrl: string,
  alt: { locale: string; category_slug: string; brand_slug: string; slug: string }
): string {
  if (alt.locale === 'en') {
    return `${siteUrl}/${alt.category_slug}/${alt.brand_slug}/${alt.slug}/`
  }
  return `${siteUrl}/${alt.locale}/${alt.category_slug}/${alt.brand_slug}/${alt.slug}/`
}

/** Build hreflang URL for a category page alternate. */
export function buildCategoryUrl(siteUrl: string, locale: string, categorySlug: string): string {
  return locale === 'en'
    ? `${siteUrl}/${categorySlug}/`
    : `${siteUrl}/${locale}/${categorySlug}/`
}

/** Build hreflang URL for a brand page alternate. */
export function buildBrandUrl(siteUrl: string, locale: string, categorySlug: string, brandSlug: string): string {
  return locale === 'en'
    ? `${siteUrl}/${categorySlug}/${brandSlug}/`
    : `${siteUrl}/${locale}/${categorySlug}/${brandSlug}/`
}

/** Build URL for a fault listing page. */
export function buildFaultListingUrl(
  siteUrl: string,
  locale: string,
  categorySlug: string,
  brandSlug: string
): string {
  const prefix = locale === 'en' ? '' : `/${locale}`
  return `${siteUrl}${prefix}/${categorySlug}/${brandSlug}/problems/`
}

/** Build hreflang URL for a fault article alternate. */
export function buildFaultArticleUrl(
  siteUrl: string,
  alt: { locale: string; category_slug: string; brand_slug: string; slug: string }
): string {
  const prefix = alt.locale === 'en' ? '' : `/${alt.locale}`
  return `${siteUrl}${prefix}/${alt.category_slug}/${alt.brand_slug}/problems/${alt.slug}/`
}
