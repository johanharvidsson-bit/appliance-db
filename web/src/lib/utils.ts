/** Parse a value that may be a pre-parsed JSONB array or a JSON string. */
export function parseJson(val: unknown): any[] {
  if (!val) return []
  if (Array.isArray(val)) return val
  try { return JSON.parse(val as string) } catch { return [] }
}
