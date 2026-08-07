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

// Exported separately from `siteConfig` so callers outside the Vite/SSR runtime
// (astro.config.ts, which only has `process.env`, not `import.meta.env`) can
// resolve the same site config without depending on Vite's env injection.
export function resolveSiteConfig(activeSite?: string) {
  return configs[activeSite || ''] ?? appliancefixConfig
}

export const siteConfig = resolveSiteConfig(import.meta.env.ACTIVE_SITE as string)
