# Appliance Repair Base

Source for [appliancerepairbase.com](https://appliancerepairbase.com) — a multilingual SEO site that helps people diagnose and fix appliance problems: find your error code or symptom, get a step-by-step repair guide. Revenue comes from display ads and geo-targeted affiliate links.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | [Astro 5](https://astro.build/), `output: 'server'` via `@astrojs/cloudflare` |
| Styling | Tailwind CSS |
| Database | Self-hosted Postgres on our own VPS, exposed via a Supabase-compatible PostgREST API (`api.appliancerepairbase.com`) — see [CONTEXT.md](./CONTEXT.md) |
| Hosting | Cloudflare Pages |

Most routes are static (`export const prerender = true`); the error-code-article/model-page route (`src/pages/[category]/[brand]/[slug]/index.astro`) renders on demand, since there are 20k+ model pages — past Cloudflare Pages' static build limits.

See **[CONTEXT.md](./CONTEXT.md)** for the full architecture writeup (content model, DB schema notes, URL structure, i18n conventions) and **[CLAUDE.md](./CLAUDE.md)** for the permissions Claude Code operates under in this repo.

## Project structure

```
src/
├── config/sites/        # Per-site branding config (site.config.ts picks one via ACTIVE_SITE)
├── lib/
│   ├── supabase.ts       # DB client (Supabase-compatible, self-hosted)
│   ├── queries.ts        # All DB queries — read this first when touching data
│   ├── specs.ts          # Config-driven model-specs registry (per appliance category)
│   ├── ui.ts              # i18n translation strings
│   └── locales.ts         # Supported locales + hreflang URL builders
├── pages/                # English routes (default locale, no prefix)
│   └── sv/               # Swedish routes — mirrors the English tree
├── components/           # Appliance-specific UI (SpecsTable, QuickFixBox, FaultPills, ...)
└── layouts/              # PageLayout, MarkdownLayout, LandingLayout
```

English and non-English locale pages are currently separate, hand-maintained files (not a shared component parameterized by locale) — check both when fixing a bug that could apply to either.

## Commands

| Command | Action |
|---|---|
| `npm install` | Install dependencies |
| `npm run dev` | Start the local dev server (`localhost:4321`) |
| `npm run build` | Production build to `./dist/` |
| `npm run preview` | Preview a production build locally |
| `npm run check` | Type-check + lint + format-check |
| `npm run fix` | Auto-fix lint + formatting |

## Environment variables

See `.env` (not committed): `ACTIVE_SITE`, `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_ANON_KEY`.

## Deployment

Cloudflare Pages, auto-deployed on every push to `main`. No GitHub Actions.
