/** All curated-media requests retain the existing endpoint's twenty-ID bound.
 * Stable canonical batches are shared by mounted logo cells through React Query. */
export function companyLogoBatch(id: string, companyIds: readonly string[] = [id]): string[] {
  const ids = [...new Set([...companyIds, id])].sort();
  const start = Math.floor(ids.indexOf(id) / 20) * 20;
  return ids.slice(start, start + 20);
}
