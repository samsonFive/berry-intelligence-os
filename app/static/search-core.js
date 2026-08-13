// Shared between the header dropdown preview (base.html) and the full
// results page (search.html) so the two surfaces rank results the same way
// instead of drifting apart -- entity pages are the strongest possible
// match for their own name and belong first, followed by newsfeed articles
// ordered by recency rather than raw text-match score. See ARCHITECTURE.md
// "Search result prioritization" for why a single Pagefind query can't
// express this on its own.
export async function mergedSearch(pf, term) {
  const [entityMatches, newsfeedMatches, allMatches] = await Promise.all([
    pf.search(term, { filters: { type: "entity" } }),
    pf.search(term, { filters: { type: "evidence" }, sort: { date: "desc" } }),
    pf.search(term),
  ]);
  const seen = new Set();
  const merged = [];
  for (const bucket of [entityMatches.results, newsfeedMatches.results, allMatches.results]) {
    for (const result of bucket) {
      if (seen.has(result.id)) continue;
      seen.add(result.id);
      merged.push(result);
    }
  }
  return merged;
}
