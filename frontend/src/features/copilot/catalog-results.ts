/** Bounded authored-name matching. Multiple exact matches remain ambiguous. */
export interface CatalogOption {
  id: string; label: string; status?: string;
  match_basis?: 'exact_name' | 'exact_alias' | 'substring' | 'unfiltered';
  matched_label?: string;
}
const exact = (row: CatalogOption) => row.match_basis === 'exact_name' || row.match_basis === 'exact_alias';
export function catalogSearchResults(rows: CatalogOption[], kind: 'company' | 'variety' | 'geography', query: string) {
  const needle = query.trim().toLowerCase();
  const matches = kind === 'geography' ? rows.filter(row =>
    ['exact_name', 'exact_alias', 'substring'].includes(row.match_basis ?? '') || row.label.toLowerCase().includes(needle) || row.id === query) : rows;
  const exactMatches = matches.filter(exact);
  const ordered = [...exactMatches, ...matches.filter(row => !exact(row))];
  const results = ordered.slice(0, 12).map(({ id, label, status, match_basis, matched_label }) => ({ id, label, status, match_basis, matched_label }));
  return { basis: 'catalog metadata; authored names and aliases only', results,
    exact_match_count: exactMatches.length, returned_count: results.length,
    available_match_count: matches.length, results_limited: matches.length > results.length };
}
