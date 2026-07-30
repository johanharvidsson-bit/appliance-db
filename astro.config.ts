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

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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
      config: './src/config.yaml',
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
