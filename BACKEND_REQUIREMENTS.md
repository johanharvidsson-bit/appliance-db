# Backend-kontrakt: appliance-db (self-hosted VPS)

Detta dokument specificerar exakt vad databasen/API:t på `api.appliancerepairbase.com` behöver tillhandahålla för att frontend-koden i det här repot ska fungera. Det är härlett direkt ur `src/lib/queries.ts` och `src/lib/specs.ts` — den faktiska koden som frågar databasen — snarare än ett teoretiskt schema. Om något i det här dokumentet och den skarpa databasen skiljer sig åt: koden i `queries.ts` är sanningen, uppdatera antingen databasen eller det här dokumentet.

---

## 1. Mål

Backend ska exponera en **läsbar, PostgREST-kompatibel REST-API** mot en Postgres-databas, nåbar via `https://api.appliancerepairbase.com`, som frontend pratar med genom `@supabase/supabase-js`-klienten (`src/lib/supabase.ts`). Det är **inte** Supabase Cloud — det är er egen självhostade stack (Postgres + PostgREST, eller motsvarande) på er VPS. Frontend behöver bara läsbehörighet; ingen skrivväg används från sajten.

Sedan 2026-07-27/30 är **hela sajten server-side rendered on demand** (inte längre byggd en gång vid deploy) — det betyder att varje sidvisning en riktig besökare gör mot appliancerepairbase.com/sv.appliancerepairbase.com nu ställer en eller flera frågor mot den här backend-API:n i realtid. Tillgänglighet och svarstid på den här API:n är alltså tillgänglighet och svarstid för hela sajten, inte bara för deploys.

---

## 2. Autentisering

- Frontend använder en **read-only anon-nyckel** (JWT, `role: anon`), satt som `PUBLIC_SUPABASE_ANON_KEY` i `.env`.
- Databasen behöver **Row Level Security (RLS)**-policyer som tillåter `SELECT` för `anon`-rollen på samtliga tabeller i avsnitt 3 nedan.
- Ingen `INSERT`/`UPDATE`/`DELETE`-behörighet krävs för `anon` — allt sådant sker via era egna pipeline/scraper-skript med en annan (service-role) nyckel, inte via den här klienten.

---

## 3. Schema — tabeller, kolumner, typer

Nedan är varje tabell som faktiskt frågas, med exakta kolumner som används i kod. Kolumner som inte listas här bryr sig frontend inte om, men ta inte bort dem utan att kontrollera `queries.ts` igen.

### `categories`
| Kolumn | Typ | Anmärkning |
|---|---|---|
| `id` | int, PK | |
| `slug_en` | text | Kanonisk engelsk slug, t.ex. `washing-machines`. Notera namnet — **inte** `slug`. |

### `category_translations`
| Kolumn | Typ | Anmärkning |
|---|---|---|
| `category_id` | int, FK → `categories.id` | |
| `locale` | text | `'en'`, `'sv'` (i praktiken; `'de'/'fr'/'es'/'pl'` är förberedda i frontend-koden men inte aktiva än) |
| `slug` | text | Lokal-specifik slug, t.ex. `tvattmaskiner` för sv |
| `name` | text | Visningsnamn per språk |

Måste ha **en rad per (category_id, locale)**-kombination för varje aktivt språk (idag: en `'en'`-rad + en `'sv'`-rad per kategori, dvs. minst 14 rader för 7 kategorier).

### `brands`
| Kolumn | Typ | Anmärkning |
|---|---|---|
| `id` | int, PK | |
| `slug` | text | |
| `name` | text | Visningsnamn — **måste** vara korrekt versalisering (t.ex. `LG`, inte `Lg`). Frontend har en slug→Title Case-fallback men den används bara om denna rad saknas. |
| `logo_url` | text, nullable | |
| `is_active` | boolean | **Kritisk.** Allt varumärkes-relaterat frontend-innehåll filtrerar på `is_active = true`. En brand med modeller men `is_active = false` visas ingenstans i navigeringen (men modellsidorna kan fortfarande nås direkt om någon har URL:en — se avsnitt 6). |

### `models`
~47 600 rader — den i särklass största tabellen.

| Kolumn | Typ | Anmärkning |
|---|---|---|
| `id` | int, PK | |
| `slug` | text | Modellslug, **samma för alla språk** (ingen `sv`-variant av modellslugs) |
| `brand_id` | int, FK → `brands.id` | |
| `category_id` | int, FK → `categories.id` | |
| `series` | text, nullable | Grupperar modellvarianter |
| `release_year` | int, nullable | |
| `manual_url` | text, nullable | |
| `manual_pdf_url` | text, nullable | |

### `error_codes`
| Kolumn | Typ | Anmärkning |
|---|---|---|
| `id` | int, PK | |
| `code` | text | Visningskod, t.ex. `E4`, `F53` |
| `short_description` | text, nullable | |
| `description` | text, nullable | |
| `display_text` | text, nullable | Används av vissa locale-varianter av sidorna — se kommentar i `queries.ts` header, samma koncept som `short_description`/`description` men en annan kolumn används på olika ställen i koden. Håll båda uppdaterade om möjligt tills detta konsolideras. |
| `severity` | text | **Måste vara exakt `'easy'`, `'medium'` eller `'advanced'`** — inget annat värde. Hela severity-badge-UI:t (`getSeverityBadges()` i `src/lib/ui.ts`) är hårdkodat mot dessa tre. Verifierat mot skarp databas 2026-07-27. |
| `diy_possible` | boolean, nullable | |
| `brand_id` | int, FK → `brands.id` | |
| `category_id` | int, FK → `categories.id` | |

### `articles`
| Kolumn | Typ | Anmärkning |
|---|---|---|
| `id` | int, PK | |
| `article_type` | text | `'error_code'` eller `'fault'` |
| `fault_id` | int, FK → `faults.id`, nullable | Satt endast när `article_type = 'fault'` |

En `articles`-rad av typen `'error_code'` kopplas till en `error_codes`-rad — kontrollera hur den FK:n är namngiven/riktad i er databas (koden joinar via `error_codes.articles` embedding, se `getArticle`/`getArticleBySlug` i `queries.ts`).

### `article_translations`
| Kolumn | Typ | Anmärkning |
|---|---|---|
| `article_id` | int, FK → `articles.id` | |
| `locale` | text | |
| `slug` | text | **Unik per (brand, category), inte globalt.** Samma slug-sträng kan förekomma för olika märken/kategorier — frontend matchar alltid slug + brand + category tillsammans, aldrig slug ensamt. |
| `translation_status` | text | `'published'` eller `'pending'`. EN visar bara `'published'`; övriga språk visar även `'pending'` (maskinöversatt innehåll som väntar på granskning). |
| `title_tag` | text, nullable | |
| `meta_description` | text, nullable | |
| `h1` | text | |
| `quick_fix` | text, nullable | |
| `intro_html` | text (HTML), nullable | Renderas med `set:html` — **måste vara sanerad HTML**, ingen extra sanering sker i frontend |
| `causes_json` | jsonb | Array av `{cause, frequency, detail}` där `frequency` är `'common' \| 'occasional' \| 'rare'` |
| `steps_json` | jsonb | Array av `{action/title, detail/instruction, warning?, tip?, image_url?}` |
| `faq_json` | jsonb | Array av `{question/q, answer/a}` |
| `affected_models_json` | jsonb, nullable | Endast använd för error_code-artiklar |
| `parts_json` | jsonb, nullable | |
| `prevention_html` | text (HTML), nullable | Kan innehålla en `<!-- SPARE_PARTS_FAULT:... -->`-kommentar som frontend filtrerar bort med regex — bibehåll det formatet om det används |
| `when_to_call_technician_html` | text (HTML), nullable | |
| `last_updated` | timestamp | |

### `faults`
| Kolumn | Typ | Anmärkning |
|---|---|---|
| `id` | int, PK | |
| `slug` | text | |
| `brand_id` | int, FK → `brands.id` | **Måste vara en riktig FK-constraint** — embedded join `faults.brands(name,slug)` används nu (tillagt 2026-07-30, verifierat fungerande) |
| `category_id` | int, FK → `categories.id` | |
| `severity` | text | Samma `'easy'/'medium'/'advanced'`-krav som `error_codes.severity` |
| `has_error_code` | boolean | |

Fel scopas per **brand + category**, inte per modell — en `WashingMachine`-fault gäller alla Samsung-tvättmaskiner, inte en specifik modell.

### `fault_translations`
| Kolumn | Typ | Anmärkning |
|---|---|---|
| `fault_id` | int, FK → `faults.id` | |
| `locale` | text | |
| `symptom_name` | text | |
| `meta_description` | text, nullable | |

### `fault_error_code_map`
| Kolumn | Typ | Anmärkning |
|---|---|---|
| `fault_id` | int, FK → `faults.id` | |
| `error_code`-koppling | — | Kopplar en fault till relaterade felkoder, renderas som "Relaterade felkoder" på symptomartiklar |

### `washing_machine_specs`
| Kolumn | Typ | Anmärkning |
|---|---|---|
| `model_id` | int, FK → `models.id` | |
| `capacity_kg` | numeric, nullable | |
| `spin_speed_rpm` | int, nullable | |
| `energy_class` | text, nullable | |
| `width_mm`, `height_mm`, `depth_mm` | int, nullable | |
| `noise_spinning_db` | numeric, nullable | |
| `energy_consumption_kwh` | numeric, nullable | |
| `water_consumption_l` | numeric, nullable | |
| `door_type` | text | `'front'` eller `'top'` — annat värde visas rått, oöversatt |

**Detta är just nu den enda specs-tabellen.** Kodlagret (`src/lib/specs.ts`) är byggt för att enkelt lägga till fler (en registry per kategori-slug), men det kräver en ny tabell + en ny fetch-funktion i `queries.ts` per kategori ni vill ha specs för.

---

## 4. Kritiskt: Foreign keys måste vara riktiga DB-constraints

PostgREST auto-upptäcker embedded joins (`select=articles(error_codes(brands(...)))`) genom att läsa faktiska `FOREIGN KEY`-constraints i Postgres schema-cachen — inte genom att bara se att ett `_id`-fält råkar matcha. Om en relation bara finns som ett löst heltalsfält utan en riktig constraint kan PostgREST inte embedda den, och frågan 400:ar eller ger `null` för den nästlade resursen.

**Verifiera att följande FK-constraints existerar och är synliga för PostgREST** (kör `NOTIFY pgrst, 'reload schema'` efter ändringar):

- `models.brand_id → brands.id`, `models.category_id → categories.id`
- `error_codes.brand_id → brands.id`, `error_codes.category_id → categories.id`
- `article_translations.article_id → articles.id`
- `articles.fault_id → faults.id`
- `faults.brand_id → brands.id`, `faults.category_id → categories.id`
- `fault_error_code_map.fault_id → faults.id` (+ koppling till error_codes)
- `category_translations.category_id → categories.id`
- `washing_machine_specs.model_id → models.id`

Vi hittade och löste redan ett fall (`faults.brand_id → brands.id` saknade fungerande embed) under revisionen 2026-07-30 — märkesnamnet på symptomsidor renderades aldrig förrän den joinen testades och lades till i koden. Gå igenom listan ovan proaktivt istället för att vänta på att fler såna buggar upptäcks i produktion.

---

## 5. API-funktioner som faktiskt används

- **Paginering**: PostgREST default-cap på 1000 rader per svar måste finnas kvar — `src/lib/queries.ts`s `paginateAll()`-hjälpfunktion loopar explicit `Range`-headers runt det. Om cap ändras (högre eller lägre) måste `PAGE_SIZE`-konstanten i `queries.ts` matcha.
- **`Prefer: count=exact`** — använt för radräkning vid felsökning, inte i produktionskod, men bra att veta stöds.
- **Embedded filters flera nivåer djupt**, t.ex. `.eq('articles.error_codes.brands.slug', brandSlug)` — filtrering genom en kedja av joins.
- **`!inner`-join-modifier** — används för att kräva att en nästlad resurs faktiskt matchar (annars null-rad).
- **CORS**: inget krav idag — all datahämtning sker server-side i Cloudflare Pages Functions, aldrig från webbläsaren. Om ni någon gång lägger till klient-side Supabase-anrop måste CORS öppnas för `appliancerepairbase.com`.

---

## 6. Drift- och prestandakrav

Det här är den viktigaste skillnaden mot hur det var innan 2026-07-27:

- **Innan**: de flesta sidor byggdes statiskt **en gång per deploy**. Databasen belastades vid `npm run build`, inte av besökare.
- **Nu**: hela sajten kör on-demand SSR (löste ett Cloudflare `_routes.json`-tak på 100 regler, se `astro.config.ts`s kommentar). **Varenda sidvisning** ställer en eller flera frågor mot den här API:n i realtid. Startsidan ensam gör ~35 paginerade anrop mot `models`-tabellen per request.

Krav som följer av detta:
1. **API:t måste klara sustained samtidig trafik**, inte bara korta byggtidstoppar.
2. **Svarstid spelar roll för besökarens upplevelsen direkt**, inte bara för deploy-tider.
3. Frontend har lagt `Cache-Control`-headers (`s-maxage=3600` för de flesta sidor, `s-maxage=86400` för sitemaps) samt en `stale-if-error=604800`-fallback i `public/_headers`, så Cloudflares edge-cache absorberar en stor del av trafiken och överlever korta VPS-avbrott — men **första träffen** efter att cachen gått ut går alltid ände fram till er databas, och måste svara inom rimlig tid (några sekunder, inte tiotals sekunder) för att inte ge besökaren en seg sida.
4. Cloudflare↔VPS-anslutningen har redan orsakat minst ett produktionsavbrott (se tidigare commits om "Cloudflare-to-VPS connectivity"). Eftersom hela sajten nu är beroende av den här länken kontinuerligt (inte bara vid deploy), rekommenderar vi:
   - Uptime-monitorering på `api.appliancerepairbase.com` med alarm.
   - Loggning av 5xx/timeout-frekvens — frontend loggar redan varje misslyckad query server-side (`console.error` i Cloudflare Functions-loggar via `logged()`-wrappern i `queries.ts`), men det förutsätter att någon faktiskt tittar på de loggarna.

---

## 7. Innehållslucka (inte en kod-fråga — en data-fråga)

Enligt kommentaren i `queries.ts` (och verifierat): **felkoder finns bara skrapade för `washing-machines`.** De andra sex kategorierna (torktumlare, diskmaskiner, kylskåp, ugnar, frysar, mikrovågsugnar) har modell-/specsidor men inget av kärninnehållet (felkodsguider). Om målet är att växa SEO-trafiken brett är det här sannolikt den största enskilda flaskhalsen — och det är ingenting frontend-koden kan lösa; det kräver antingen mer skrapning/innehållsproduktion in i `error_codes`/`articles`/`article_translations`, eller en produktbeslut om att fokusera på färre kategorier tills vidare.

`CLAUDE.md` ger tillstånd att köra Python-skript i `/pipeline/` och `/scrapers/`, men ingen av mapparna finns i det här repot — om de finns någon annanstans (annat repo, direkt på VPS:en), dokumentera var, annars är behörighetsraden i `CLAUDE.md` inaktuell.

---

## 8. Känd datakvalitetsbugg (inte er att fixa i kod, men värt att känna till)

`category_translations.slug` för mikrovågsugnar på svenska är **`mikrovagnsugnar`** (med extra "n" — läses som "mikrovagns-ugnar" snarare än "mikrovågsugnar"). Detta är verifierat mot den skarpa databasen och är en riktig stavfel i datat, inte ett kodfel — rätta det i databasraden när det passar; **rätta det inte i frontend-koden** (`navigation.ts`) utan att samtidigt rätta databasraden, annars pekar länken på en URL som inte längre matchar.

---

## 9. Checklista för verifiering

- [ ] RLS: `anon`-rollen har `SELECT` på alla 9 tabeller i avsnitt 3
- [ ] Alla FK-constraints i avsnitt 4 existerar och PostgREST-schemat är omladdat
- [ ] `error_codes.severity` och `faults.severity` innehåller bara `'easy'/'medium'/'advanced'`
- [ ] `article_translations.translation_status` innehåller bara `'published'/'pending'`
- [ ] `washing_machine_specs.door_type` innehåller bara `'front'/'top'`
- [ ] Varje kategori har minst en `'en'`- och en `'sv'`-rad i `category_translations`
- [ ] `brands.is_active` är satt korrekt för alla märken som ska synas i navigering
- [ ] `brands.name` har korrekt versalisering (t.ex. `LG`, inte `lg`/`Lg`)
- [ ] API:t svarar konsekvent inom några sekunder under samtidig belastning (inte bara enstaka testfrågor)
- [ ] Uptime-monitorering finns på `api.appliancerepairbase.com`
