/**
 * Hand-rolled sitemap XML helpers.
 *
 * @astrojs/sitemap only discovers statically-prerendered routes at build time.
 * Once the whole site moved to on-demand SSR (see git log "Switch every
 * remaining static page to SSR"), it had nothing left to enumerate — the live
 * sitemap silently collapsed from 337+ URLs to the ~18 truly static pages,
 * with the ~48k category/brand/model/article URLs gone. These helpers back a
 * set of sitemap-*.xml.ts endpoints that query the DB directly instead.
 */

export function xmlEscape(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

export function buildUrlset(urls: string[]): string {
  const body = urls.map((u) => `<url><loc>${xmlEscape(u)}</loc></url>`).join('')
  return `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${body}</urlset>`
}

export function buildSitemapIndex(sitemapUrls: string[]): string {
  const body = sitemapUrls.map((u) => `<sitemap><loc>${xmlEscape(u)}</loc></sitemap>`).join('')
  return `<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${body}</sitemapindex>`
}

/** Shared response wrapper: XML content type + a day-long edge cache (sitemaps are crawled periodically, not per-user). */
export function xmlResponse(xml: string): Response {
  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
      'Cache-Control': 'public, max-age=0, s-maxage=86400, stale-while-revalidate=604800',
    },
  })
}
