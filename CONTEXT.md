# Project Context — Appliance Repair Base

This document gives Claude Code background on the project architecture, conventions, and decisions. Read this before making any changes.

---

## What this project is

Appliance Repair Base (`appliancerepairbase.com`) is a multilingual SEO site helping users diagnose and fix appliance problems. The core value proposition: find your error code or symptom, get a clear step-by-step repair guide.

Revenue comes from display ads and geo-targeted affiliate links (AppliancePartsPros for US, eSpares for UK, FixPart for EU).

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Astro 5 (based on AstroWind template) |
| Styling | Tailwind CSS, accent color `#16a34a` (green-600), font Inter |
| Database | Supabase (Postgres) |
| Hosting | Cloudflare Pages |
| Repo | GitHub, user `johanharvidsson-bit` |
| Dev machine | Windows, VSCode, `C:\Users\Admin\` |

---

## Content model — the five core entities

### 1. Brand
A manufacturer. Has a `brand_slug` (e.g. `samsung`) and `brand_name`. Brands are linked to appliance types via the models they make.

### 2. Appliance type
A category of appliance: `washing-machine`, `dishwasher`, `dryer`, `fridge`, `oven`, `freezer`, `microwave`. Stored as a slug string on the `models` table — not a separate table.

### 3. Model
A specific appliance model. Uses **base model codes** (e.g. `WW90T986DSH`) as the canonical unit — not regional product code variants. This reduces tens of thousands of SKUs to a manageable set of unique model pages. Key columns: `model_slug`, `brand_slug`, `appliance_type`, `base_model_code`.

### 4. Error code
A machine-generated signal shown on the appliance display (e.g. `E4`, `F53`). Scoped to brand + appliance type. Stored on the `articles` table with `article_type = 'error_code'`.

### 5. Fault
A user-observed symptom (e.g. "not draining", "won't start", "making noise"). This is what users actually search for — it maps to search intent. Faults are scoped at **brand + appliance type level**, not per model. This is intentional: all Samsung washing machines share the same fault set, avoiding join table complexity.

**Key distinction:** Error codes = machine signals. Faults = human symptoms. They are separate entities that can be linked via `fault_error_code_map`.

---

## Database schema (relevant tables)

### `articles`
Main content table. Each row is one repair guide.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `slug` | text | URL slug |
| `locale` | text | `'en'`, `'sv'`, `'de'` etc. |
| `brand_slug` | text | FK to brands |
| `appliance_type` | text | e.g. `'washing-machine'` |
| `model_slug` | text | nullable — some articles are brand-level |
| `error_code` | text | nullable — null for fault articles |
| `article_type` | text | `'error_code'` or `'fault'` |
| `fault_id` | uuid | nullable FK to `faults` |
| `title` | text | |
| `steps_json` | jsonb | Repair steps |
| `causes_json` | jsonb | Possible causes with frequency badges |
| `faq_json` | jsonb | FAQ entries |
| `published` | boolean | |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### `faults`
Brand + appliance type scoped symptoms.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `fault_slug` | text | URL slug |
| `appliance_type` | text | |
| `brand_slug` | text | nullable — null means generic/all-brand fault |
| `created_at` | timestamptz | |

### `fault_translations`
Translated display names for faults.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `fault_id` | uuid | FK to `faults` |
| `locale` | text | `'en'`, `'sv'` etc. |
| `name` | text | Display name, e.g. "Not draining" |
| `description` | text | Short description |

### `fault_error_code_map`
Links faults to the error codes that can cause them.

| Column | Type | Notes |
|---|---|---|
| `fault_id` | uuid | FK to `faults` |
| `article_id` | uuid | FK to `articles` |

### `models`
Appliance models.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `model_slug` | text | |
| `base_model_code` | text | Canonical identifier |
| `brand_slug` | text | |
| `appliance_type` | text | |

---

## URL structure

| Page | URL pattern |
|---|---|
| Homepage | `/` |
| Appliance type index | `/[appliance-type]` |
| Brand hub | `/brands/[brand-slug]` |
| Brand + appliance index | `/[appliance-type]/[brand-slug]` |
| Error code article | `/[appliance-type]/[brand-slug]/[error-code]` |
| Model page | `/[appliance-type]/[brand-slug]/[model-slug]` |
| Fault page | `/faults/[fault-slug]` |
| All brands | `/brands` |
| All faults | `/faults` |

For non-English locales, prefix with language code: `/sv/[appliance-type]/[brand-slug]/[error-code]`

English is the **default locale** — no prefix.

---

## i18n convention

- English: no URL prefix (`/washing-machine/samsung/e4`)
- Other languages: subdirectory prefix (`/sv/washing-machine/samsung/e4`)
- All Supabase queries filter by `locale` — default to `'en'`
- All new components must accept a `locale` prop even if only `'en'` is used now
- Translation tables follow the pattern: base table + `_translations` table with `locale` column

---

## Supabase client

Import from `@/lib/supabase`:
```ts
import { supabase } from '@/lib/supabase'
```

All homepage data must be fetched **at build time** in Astro component frontmatter — no runtime Supabase calls from the browser. Data needed client-side for interactive elements should be serialised as JSON and embedded in the HTML at build time.

RLS is configured with public read access for published content.

---

## Affiliate links

Geo-targeted using Cloudflare's `CF-IPCountry` header:

| Region | Affiliate |
|---|---|
| US | AppliancePartsPros |
| UK | eSpares |
| EU | FixPart |
| Other | FixPart (default) |

Affiliate CTAs appear on article pages, not on the homepage.

---

## Key design decisions (do not reverse without discussion)

- **Manuals excluded intentionally.** Do not add links to PDF manuals or ManualsLib — this sends traffic to competitor sites.
- **Base model codes as canonical unit.** Do not create separate pages per regional SKU variant.
- **Faults scoped at brand + appliance type.** Do not scope faults per model — `model_fault_map` is explicitly deferred.
- **Article content in structured fields.** Content is stored as `steps_json`, `causes_json`, `faq_json` etc. — not as HTML blobs. Do not consolidate these into a single content field.
- **Build-time data only on homepage.** No client-side Supabase calls on the homepage.

---

## Component conventions

- Component files: `src/components/ComponentName.astro`
- Page files: `src/pages/index.astro`, `src/pages/[appliance-type]/index.astro` etc.
- Shared data helpers: `src/lib/`
- Tailwind only — no custom CSS files unless strictly necessary
- All new components accept a `locale: string = 'en'` prop

---

## Current status

- Site is live on Cloudflare Pages
- English content is populated
- Homepage currently has a basic error-code-only hero widget — this is being replaced
- Fault entity (`faults`, `fault_translations`, `fault_error_code_map` tables) is set up but fault content seeding is in progress
- Swedish (`/sv/`) and German (`/de/`) locales are planned but not yet implemented
