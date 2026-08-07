# Homepage Redesign — Claude Code Specification
**Project:** Appliance Repair Base (`appliancerepairbase.com`)
**File:** `src/pages/index.astro` (and new component files)
**Stack:** Astro 5, Tailwind CSS, self-hosted database on our VPS (build-time data fetch)
**Accent color:** `#16a34a` (green-600)

---

## Overview

Replace the current homepage with a new layout consisting of six sections in this order:

1. Hero — two-tab search widget
2. Browse by appliance type
3. Popular brands
4. Common faults (symptom pills)
5. Trending + Popular guides (two-column)
6. How it works

The page tagline under the site title should read:
> **"Fix appliance error codes — free step-by-step guides"**

No other introductory body text is needed. One supporting line below the hero widget CTA:
> *"Written by appliance technicians. No sign-up needed."*

---

## Section 1 — Hero widget

### Component file
`src/components/HeroWidget.astro`

### Layout
- Full-width section with background `bg-slate-50` (or equivalent light tint)
- Centered content, max-width `max-w-2xl`, padding `py-12 px-4`
- H1: site name, large bold
- Tagline: `text-green-600 font-semibold text-lg` directly below H1
- Supporting copy: one short sentence, muted color, centered

### Two-tab pill switcher
Render two tabs as a pill toggle:
- **Tab 1:** "An error code" (default active)
- **Tab 2:** "A symptom / fault"

Active tab: white background, `text-green-700`, subtle shadow.
Inactive tab: transparent, `text-slate-500`.
Use Astro client-side JS (`<script>`) to toggle visibility of the two tab panels.

### Tab 1 — Error code panel
Three controls in a row (stack vertically on mobile):

| Control | Type | Data source |
|---|---|---|
| Appliance type | `<select>` | Fetched from the database at build time — distinct `appliance_type` values from `models` table |
| Brand | `<select>` | Disabled until appliance type selected. Filtered list of brands for that appliance type. Populate via inline `<script>` using a pre-serialised JSON map of `appliance_type → [brands]` embedded in the page at build time. |
| Error code | `<input type="text">` | Free text, placeholder "e.g. E4, F53" |

**CTA button:** full-width below the three controls, `bg-green-600 hover:bg-green-700 text-white`, label "Find fix →"

**Button behaviour:**
- If all three fields are filled: navigate to `/[appliance-type]/[brand-slug]/[error-code]`
- If only appliance type + brand filled: navigate to `/[appliance-type]/[brand-slug]` (error code index)
- If only appliance type filled: navigate to `/[appliance-type]`
- Slugify all values (lowercase, hyphens) before building URL

**Below CTA:** small muted text "Or browse the full error code list for this model →" — this becomes a link to `/[appliance-type]/[brand-slug]` once brand is selected.

### Tab 2 — Symptom / fault panel
- Same appliance type + brand dropdowns as Tab 1 (can share the same `<select>` elements — just show/hide the error code input and change CTA behaviour)
- Below dropdowns: a pill grid of common fault names (see Section 4 for data source)
- Pills are static on page load. When appliance type and/or brand is selected, filter pills to relevant faults via inline JS (use pre-serialised JSON of `appliance_type → [fault_names]` embedded at build time)
- Clicking a pill navigates to `/faults/[fault-slug]` or `/[appliance-type]/[brand-slug]/faults/[fault-slug]` if brand is selected

---

## Section 2 — Browse by appliance type

### Component file
`src/components/ApplianceTypeGrid.astro`

### Data
Fetch distinct `appliance_type` values from the database's `models` table at build time. Map each to an emoji icon and display label (maintain a static mapping object in the component):

```js
const icons = {
  'washing-machine': '🫧',
  'dishwasher': '🍽️',
  'dryer': '🌀',
  'fridge': '❄️',
  'oven': '🔥',
  'freezer': '🧊',
  'microwave': '📡',
}
```

### Layout
- Section heading: "Browse by appliance type" (`text-2xl font-bold`)
- Grid: `grid grid-cols-3 sm:grid-cols-4 md:grid-cols-7 gap-3`
- Each card: white background, border, rounded-xl, padding, centered emoji + label, hover lift effect
- Link target: `/[appliance-type-slug]`

---

## Section 3 — Popular brands

### Component file
`src/components/BrandsSection.astro`

### Data
Fetch top brands by article count from the database at build time:
```sql
select brand_slug, brand_name, count(*) as article_count
from articles
group by brand_slug, brand_name
order by article_count desc
limit 20
```

### Layout
- Section heading: "Popular brands" with "All brands →" link right-aligned pointing to `/brands`
- Render brands as pill buttons: `rounded-full border px-4 py-1.5 text-sm hover:bg-slate-100`
- Wrap in `flex flex-wrap gap-2`
- Link each pill to `/brands/[brand-slug]`

---

## Section 4 — Common faults

### Component file
`src/components/FaultPills.astro`

### Data
Fetch fault names from the database's `faults` + `fault_translations` tables at build time (English, `locale = 'en'`):
```sql
select f.fault_slug, ft.name, f.appliance_type
from faults f
join fault_translations ft on ft.fault_id = f.id
where ft.locale = 'en'
order by ft.name asc
```

Serialise result as a JSON map `appliance_type → [{fault_slug, name}]` and embed in a `<script type="application/json" id="fault-data">` tag for use by Tab 2 hero and this section's filter.

### Layout
- Section heading: "Common faults — what are you seeing?"
- Subheading (muted): "No error code? Browse by symptom."
- Pill grid: `flex flex-wrap gap-2`
- Each pill: `rounded-full border px-4 py-2 text-sm hover:bg-slate-100 cursor-pointer`
- Show top 16 faults by default. "All faults →" link at end pointing to `/faults`
- Link each pill to `/faults/[fault-slug]`

---

## Section 5 — Trending + Popular guides

### Component file
`src/components/TrendingAndGuides.astro`

### Layout
Two equal columns side-by-side (`grid grid-cols-1 md:grid-cols-2 gap-6`), each in a white bordered card.

### Left card — Trending error codes
- Heading: "Trending error codes"
- Fetch top 6 error codes by page view proxy (use article `updated_at` recency as a stand-in until analytics is wired):
```sql
select a.brand_slug, a.appliance_type, a.error_code, a.slug
from articles a
where a.article_type = 'error_code' and a.locale = 'en'
order by a.updated_at desc
limit 6
```
- Each row: brand + appliance type left, error code right with a small badge showing the fault category if available
- Link each row to the article page

### Right card — Popular guides
- Heading: "Popular guides"
- Fetch same query but order by `created_at asc` (oldest = most established) as a proxy for popularity until real analytics exists
- Same row layout, linked to article pages

**Note:** Both cards should be easy to swap to analytics-based ordering later — keep the query in a clearly labelled helper function.

---

## Section 6 — How it works

### Component file
`src/components/HowItWorks.astro`

### Layout
- Light background section (`bg-slate-50`)
- Centered heading: "How it works"
- Three cards in a row (`grid grid-cols-1 md:grid-cols-3 gap-4`), each with:
  - Step number in `text-green-600 font-bold text-2xl`
  - Bold step title
  - Short muted description (one line)

| Step | Title | Description |
|---|---|---|
| 1 | Select your appliance and brand | Or enter the error code directly |
| 2 | Find your error code or symptom | Pick from the list or search |
| 3 | Follow the fix steps | Free guides, no sign-up needed |

---

## Nav dropdown — "Browse"

Update the existing nav Browse dropdown to include:
- **By appliance type:** links to each `/[appliance-type]` index — list all types
- **By brand:** links to top 8 brands by article count, then "All brands →"

The dropdown data can be fetched once at build time and shared via Astro's `getStaticPaths` or a shared data module.

---

## i18n / multilingual

All database queries should use `locale = 'en'` (unprefixed default). The component architecture should make it easy to pass `locale` as a prop later when implementing `/sv/`, `/de/` etc. prefixed routes.

Fault and brand names should come from translation tables where available; fall back to slug-derived display name if no translation exists.

---

## Build-time data strategy

Avoid runtime database calls. All homepage data fetched in the Astro component frontmatter (server-side at build time via `import { supabase } from '~/lib/supabase'` — a Supabase-compatible client pointed at our self-hosted VPS database).

Data that needs to be available client-side for the interactive dropdowns and pill filtering should be serialised as JSON and embedded in the HTML:

```astro
<script type="application/json" id="appliance-brand-map">
  {JSON.stringify(applianceBrandMap)}
</script>
<script type="application/json" id="fault-data">
  {JSON.stringify(faultsByAppliance)}
</script>
```

Client-side `<script>` tags read from these JSON blocks — no API calls at runtime.

---

## Files to create / modify

| Action | File |
|---|---|
| Modify | `src/pages/index.astro` |
| Create | `src/components/HeroWidget.astro` |
| Create | `src/components/ApplianceTypeGrid.astro` |
| Create | `src/components/BrandsSection.astro` |
| Create | `src/components/FaultPills.astro` |
| Create | `src/components/TrendingAndGuides.astro` |
| Create | `src/components/HowItWorks.astro` |

Keep existing nav and footer components unchanged unless the Browse dropdown needs updating (see Nav section above).

---

## Definition of done

- [ ] Homepage renders all six sections without runtime errors
- [ ] Tab switcher toggles correctly between error code and fault panels
- [ ] Appliance type dropdown populates brand dropdown correctly (client-side, no extra fetch)
- [ ] "Find fix →" button navigates to correct URL for all three fill states
- [ ] Fault pills filter by appliance type when selected
- [ ] All links resolve (no 404s for existing content)
- [ ] Page passes Lighthouse mobile score ≥ 85 (no heavy JS, all data at build time)
- [ ] i18n locale prop accepted by all new components (even if only `en` used now)
