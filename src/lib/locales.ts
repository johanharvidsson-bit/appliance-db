export interface LocaleInfo {
  code: string
  name: string
  flag: string
  active: boolean
}

export const LOCALES: LocaleInfo[] = [
  { code: 'en', name: 'English',  flag: '🇬🇧', active: true },
  { code: 'sv', name: 'Svenska',  flag: '🇸🇪', active: true },
  { code: 'de', name: 'Deutsch',  flag: '🇩🇪', active: false },
  { code: 'fr', name: 'Français', flag: '🇫🇷', active: false },
  { code: 'es', name: 'Español',  flag: '🇪🇸', active: false },
  { code: 'pl', name: 'Polski',   flag: '🇵🇱', active: false },
]

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
