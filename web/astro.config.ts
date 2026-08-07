import path from 'path';
import { fileURLToPath } from 'url';

import { defineConfig } from 'astro/config';

import tailwind from '@astrojs/tailwind';
import mdx from '@astrojs/mdx';
import partytown from '@astrojs/partytown';
import icon from 'astro-icon';
import compress from 'astro-compress';
import cloudflare from '@astrojs/cloudflare';
import type { AstroIntegration } from 'astro';

import astrowind from './vendor/integration';

import { readingTimeRemarkPlugin, responsiveTablesRehypePlugin, lazyImagesRehypePlugin } from './src/utils/frontmatter';
import { LOCALES } from './src/lib/locales';
import { resolveSiteConfig } from './site.config';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// astro.config.ts runs in plain Node before Vite is available, so it reads
// `process.env` directly rather than `import.meta.env` (which `site.config.ts`
// uses everywhere else, since that's Vite-injected and only populated once the
// app is actually running). Astro loads `.env` into `process.env` before this
// file is evaluated, so `ACTIVE_SITE` is already set here.
const activeSiteConfig = resolveSiteConfig(process.env.ACTIVE_SITE);

const hasExternalScripts = false;
const whenExternalScripts = (items: (() => AstroIntegration) | (() => AstroIntegration)[] = []) =>
  hasExternalScripts ? (Array.isArray(items) ? items.map((item) => item()) : [items()]) : [];

export default defineConfig({
  // 'server' + the Cloudflare adapter: the whole site renders on-demand (see git
  // log "Switch every remaining static page to SSR") — Cloudflare Pages' _routes.json
  // caps at 100 include/exclude rules, and one exclude-rule-per-static-file blew
  // that cap once SV parity pushed the static page count past ~337.
  //
  // Sitemap: @astrojs/sitemap only knows about statically-prerendered routes, so
  // with nothing prerendered it can't discover the ~48k model/article/category
  // URLs anymore — removed in favor of hand-rolled sitemap-*.xml.ts endpoints
  // that query the DB directly (see those files + public/robots.txt).
  output: 'server',
  adapter: cloudflare(),

  i18n: {
    defaultLocale: 'en',
    // Derived from src/lib/locales.ts — the single source of truth for locale codes.
    locales: LOCALES.map((l) => l.code),
    routing: {
      prefixDefaultLocale: false,
    },
  },

  integrations: [
    tailwind({
      applyBaseStyles: false,
    }),
    mdx(),
    icon({
      include: {
        tabler: ['*'],
        'flat-color-icons': [
          'template',
          'gallery',
          'approval',
          'document',
          'advertising',
          'currency-exchange',
          'voice-presentation',
          'business-contact',
          'database',
        ],
      },
    }),

    ...whenExternalScripts(() =>
      partytown({
        config: { forward: ['dataLayer.push'] },
      })
    ),

    compress({
      CSS: true,
      HTML: {
        'html-minifier-terser': {
          removeAttributeQuotes: false,
        },
      },
      Image: false,
      JavaScript: true,
      SVG: false,
      Logger: 1,
    }),

    astrowind({
      // Built from the active multisite config (site.config.ts) instead of the
      // old static src/config.yaml, which only ever described appliancefix and
      // was silently wrong (header, <title>, OG tags, Astro.site) for every
      // other ACTIVE_SITE value.
      config: {
        site: {
          name: activeSiteConfig.name,
          site: `https://${activeSiteConfig.domain}`,
          base: '/',
          trailingSlash: true,
          googleSiteVerificationId: activeSiteConfig.meta.googleSiteVerificationId ?? '',
        },
        metadata: {
          title: {
            default: activeSiteConfig.name,
            template: `%s — ${activeSiteConfig.name}`,
          },
          description: activeSiteConfig.meta.description,
          robots: {
            index: true,
            follow: true,
          },
          openGraph: {
            siteName: activeSiteConfig.name,
            images: [{ url: '~/assets/images/default.png', width: 1200, height: 628 }],
            type: 'website',
          },
          twitter: {
            handle: activeSiteConfig.meta.twitterHandle,
            site: activeSiteConfig.meta.twitterHandle,
            cardType: 'summary_large_image',
          },
        },
        i18n: {
          language: activeSiteConfig.defaultLocale,
          textDirection: 'ltr',
        },
        // Omitted `apps.blog` entirely rather than passing `{ isEnabled: false }` —
        // the vendor Config type requires the full AppBlogConfig shape when the key
        // is present at all, and `isEnabled: false` is already configBuilder's own
        // default when `apps` is left out.
      },
    }),
  ],

  image: {
    domains: ['cdn.pixabay.com'],
  },

  markdown: {
    remarkPlugins: [readingTimeRemarkPlugin],
    rehypePlugins: [responsiveTablesRehypePlugin, lazyImagesRehypePlugin],
  },

  vite: {
    resolve: {
      alias: {
        '~': path.resolve(__dirname, './src'),
        'site-config': path.resolve(__dirname, './site.config'),
      },
    },
  },
});
