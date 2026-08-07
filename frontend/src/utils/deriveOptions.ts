/**
 * Derives a sorted, deduplicated list of distinct string values from a
 * dataset field — used for the Region filter dropdown (approved
 * decision: no new backend endpoint, values come from the currently
 * loaded page of results, not a controlled vocabulary). A small pure
 * function, not a component — kept generic enough for both Schools and
 * Learning Centers to reuse without either page depending on the other.
 */
export function deriveDistinctValues<T>(items: T[], field: keyof T): string[] {
  const values = new Set<string>();
  for (const item of items) {
    const value = item[field];
    if (typeof value === "string" && value.trim()) values.add(value);
  }
  return Array.from(values).sort((a, b) => a.localeCompare(b));
}
