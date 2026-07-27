/**
 * Config-driven specs registry.
 *
 * `washing_machine_specs` is currently the only specs table in the DB, and the
 * model page used to gate on a hardcoded `category === 'washing-machines'` /
 * `'tvattmaskiner'` string check, with `SpecsTable.astro` hardcoding every
 * field/label/unit. That blocked adding specs for any other category.
 *
 * This registry is keyed by category slug (every active locale's slug for
 * that category, since page files only have the locale-specific URL param in
 * scope). To add specs for a new category later: add a fetch function in
 * `queries.ts`, define its `SpecField[]`, and add an entry per locale slug
 * below — no changes needed to `SpecsTable.astro` or the `[slug]` page files.
 */
import { getWashingMachineSpecs } from './queries'
import { t } from './ui'

export interface SpecField {
  /** Column name on the specs row. */
  key: string
  /** Translation key (ui.ts) for the display label. */
  labelKey: string
  /** schema.org PropertyValue name (kept in English, matching prior behavior). */
  schemaName: string
  /** Unit suffix appended to the raw value, e.g. "kg". Ignored if `format` is set. */
  unit?: string
  /** Custom formatter, e.g. mapping an enum to a translated label. */
  format?: (value: any, locale: string) => string
}

export interface SpecsConfig {
  fetch: (modelId: number) => Promise<Record<string, any> | null>
  fields: SpecField[]
}

const washingMachineFields: SpecField[] = [
  {
    key: 'door_type',
    labelKey: 'specs.doorType',
    schemaName: 'Door Type',
    format: (v, locale) => (v === 'front' ? t(locale, 'specs.frontLoad') : v === 'top' ? t(locale, 'specs.topLoad') : v),
  },
  { key: 'capacity_kg', labelKey: 'specs.drumCapacity', schemaName: 'Drum Capacity', unit: 'kg' },
  { key: 'spin_speed_rpm', labelKey: 'specs.maxSpinSpeed', schemaName: 'Max Spin Speed', unit: 'rpm' },
  { key: 'energy_class', labelKey: 'specs.energyClass', schemaName: 'Energy Class' },
  { key: 'width_mm', labelKey: 'specs.width', schemaName: 'Width', unit: 'mm' },
  { key: 'height_mm', labelKey: 'specs.height', schemaName: 'Height', unit: 'mm' },
  { key: 'depth_mm', labelKey: 'specs.depth', schemaName: 'Depth', unit: 'mm' },
  { key: 'noise_spinning_db', labelKey: 'specs.noiseSpin', schemaName: 'Spin Noise', unit: 'dB' },
  { key: 'energy_consumption_kwh', labelKey: 'specs.energyConsumption', schemaName: 'Energy Consumption', unit: 'kWh' },
  { key: 'water_consumption_l', labelKey: 'specs.waterConsumption', schemaName: 'Water Consumption', unit: 'L' },
]

const washingMachineConfig: SpecsConfig = { fetch: getWashingMachineSpecs, fields: washingMachineFields }

/** Every active locale's slug for a category maps to the same SpecsConfig. */
const SPECS_BY_CATEGORY_SLUG: Record<string, SpecsConfig> = {
  'washing-machines': washingMachineConfig,
  'tvattmaskiner': washingMachineConfig,
}

export function getSpecsConfig(categorySlug: string): SpecsConfig | null {
  return SPECS_BY_CATEGORY_SLUG[categorySlug] ?? null
}

/** Renderable {label, value} rows for SpecsTable.astro, in field-config order. */
export function buildSpecRows(specs: Record<string, any>, fields: SpecField[], locale: string) {
  return fields
    .filter((f) => specs[f.key] != null)
    .map((f) => ({
      key: f.key,
      label: t(locale, f.labelKey as any),
      value: f.format ? f.format(specs[f.key], locale) : f.unit ? `${specs[f.key]} ${f.unit}` : String(specs[f.key]),
    }))
}

/**
 * schema.org `additionalProperty` entries for JSON-LD. Always formatted in
 * English regardless of page locale, matching the site's prior JSON-LD
 * behavior (structured data values were never localized).
 */
export function buildSpecSchemaProperties(specs: Record<string, any>, fields: SpecField[]) {
  return fields
    .filter((f) => specs[f.key] != null)
    .map((f) => ({
      '@type': 'PropertyValue',
      name: f.schemaName,
      value: f.format ? f.format(specs[f.key], 'en') : f.unit ? `${specs[f.key]} ${f.unit}` : String(specs[f.key]),
    }))
}
