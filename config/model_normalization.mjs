/** Spec 0 model/code normalizer shared with the Python profiler. */
export function normalizeModelCode(value) {
  return value.normalize("NFKC").trim().replace(/\s+/gu, " ").toUpperCase();
}

