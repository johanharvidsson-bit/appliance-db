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

const activeSite = (import.meta.env.ACTIVE_SITE as string) || 'appliancefix'

export const siteConfig = configs[activeSite] ?? appliancefixConfig
