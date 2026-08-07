import { appliancefixConfig } from './src/config/sites/appliancefix'
import { printerfixConfig } from './src/config/sites/printerfix'
import { boilerfixConfig } from './src/config/sites/boilerfix'
import { outboardrepairbaseConfig } from './src/config/sites/outboardrepairbase'

const configs: Record<string, typeof appliancefixConfig> = {
  appliancefix: appliancefixConfig,
  printerfix: printerfixConfig,
  boilerfix: boilerfixConfig,
  outboardrepairbase: outboardrepairbaseConfig,
}

// Fail-closed on a genuine misconfiguration (an ACTIVE_SITE value that isn't
// any known site key - almost always a typo) rather than silently serving
// the wrong site's content under someone else's domain. An *unset* ACTIVE_SITE
// still falls back to appliancefix, matching today's already-relied-on local
// dev / undocumented-deploy behavior - only an explicit-but-wrong value throws.
function validateSiteRegistry(registry: Record<string, typeof appliancefixConfig>): void {
  const domains = new Set<string>()
  for (const [key, site] of Object.entries(registry)) {
    if (domains.has(site.domain)) {
      throw new Error(`site.config: duplicate domain "${site.domain}" (site key "${key}")`)
    }
    domains.add(site.domain)
  }
}
validateSiteRegistry(configs)

// Exported separately from `siteConfig` so callers outside the Vite/SSR runtime
// (astro.config.ts, which only has `process.env`, not `import.meta.env`) can
// resolve the same site config without depending on Vite's env injection.
export function resolveSiteConfig(activeSite?: string) {
  if (!activeSite) return appliancefixConfig
  const match = configs[activeSite]
  if (!match) {
    throw new Error(
      `site.config: ACTIVE_SITE="${activeSite}" is not a known site key (${Object.keys(configs).join(', ')})`
    )
  }
  return match
}

/**
 * Resolve a site by its live request hostname rather than a build-time
 * ACTIVE_SITE env var - not wired into any call path yet (every site today
 * deploys as its own Cloudflare Pages project with its own ACTIVE_SITE), but
 * kept available for a future single-Worker-many-domains deployment model
 * without requiring a redesign of site resolution at that point.
 */
export function resolveSiteFromHostname(hostname: string) {
  const normalized = hostname.trim().toLowerCase().replace(/\.$/, '')
  const match = Object.values(configs).find((site) => site.domain.toLowerCase() === normalized)
  if (!match) throw new Error(`site.config: no site registered for hostname "${hostname}"`)
  return match
}

export const siteConfig = resolveSiteConfig(import.meta.env.ACTIVE_SITE as string)
