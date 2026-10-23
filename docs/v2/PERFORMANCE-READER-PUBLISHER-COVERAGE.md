# App performance, reader recovery and publisher coverage — October 23, 2026

This release closes the follow-up scope from automatic News: slow workspaces,
Packer-only API recovery, and search-dependent Packer/Watershed discovery.
The approved profile optimization in PR 407 is included and preserved.

## Measured performance

Identical isolated copies of production data, fixed Python hash seed, the
current production base, and read-only startup warm-up were used. Brief seen
state was held constant for the comparison. Second-request seconds:

| View | Before | Candidate |
| --- | ---: | ---: |
| Morning Brief | 6.192 | 2.380 |
| Live Intelligence | 6.628 | 2.415 |
| Variety index | 10.613 | 2.372 |
| Monitoring | 2.018 | 0.913 |
| News | 1.115 | 0.990 |
| Sources | 0.866 | 0.554 |
| Search | 0.727 | 0.473 |

All story/action links were identical across 14 measured views. This is a
server response benchmark, not a claim about every browser, network or route.
Initial warm-up takes roughly 15–20 seconds before the server accepts requests.
It performs no collection, source fetching, review action or seen-state write.

Profiles identified repeated source-text cleaning, catalog matching, variety
candidate/portfolio derivation and repeated runtime JSON reads. Memoization is
bounded by entries and bytes; private mutable results are copied. Keys contain
exact relevant inputs, or current file inventory/inode/size/mtime/ctime, never
record ID alone. File creation, replacement, repair and deletion invalidate
snapshots. Candidate derivation also expires on the UTC day. Unsupported or
oversized inputs/results simply execute uncached. Rendered authenticated pages
are not cached. Review, attribution, variety identity and trust policies do not
change; caching addresses the measured variety presentation blocker only.

## Selected reader recovery

Direct retrieval stays first. The configured Firecrawl connection can now
recover other public HTTPS publishers, using one exact article request, or one
recorded publisher listing followed by one uniquely matched article. Packer's
specific verified body container remains supported. Current publisher discovery
can resolve retained Google-linked Packer/Watershed titles to exact source URLs.

Publisher host, returned path/query and headline must agree. Private addresses,
credentials in URLs, nonstandard ports, Google shells, mismatched pages and
generated replacements are rejected. API response bytes, calls, timeouts and
paragraph counts are bounded. Cookies/dialogs/navigation are omitted using
existing reader sanitizers. An access-limited excerpt, API warning or uncertain
body structure remains partial. Source text, headings and publisher links remain
available; cached captures and failed-refresh preservation are retained. No
retrieval mechanism guarantees access to every publisher or paywalled article.

Real candidate API checks recovered Watershed's *Research brief: AI emissions*
(21 paragraphs, 5,235 characters) and Trellis's *Updated: Sustainability
leadership moves* (109 paragraphs, 21,899 characters), both as full source text.
These are source-reader captures, never approved Evidence or Atomic claims.

## Publisher-first discovery

Watershed's public blog cards supply up to 24 candidate URLs per hourly check.
Article JSON-LD supplies the original `datePublished`; `dateModified`, sitemap
`lastmod`, and retrieval time never substitute for original publication date.
Unchanged listing cards reuse verified metadata; changed/new cards are fetched
with four workers and bounded responses/timeouts. Non-blog paths are excluded.

Packer's explicitly requested Sustainability Insights listing is read through
the existing Firecrawl connection at most every six hours, up to two pages
following only a publisher-declared Next link on that exact section. This uses
existing API credits; no purchase or top-up is introduced. Article discovery
uses section card headlines, exact publisher links and displayed calendar dates.
That date basis is recorded explicitly. No automatic article-body acquisition
or generated text is requested by this job.

Candidate checks found 16 verified Watershed entries and 15 Packer section
entries without errors. These are bounded listing counts, not exhaustive
archive recall or a guarantee of a new post every day. The existing News date,
berry, country and company filters still apply. Search remains a supplementary
lane, and matching publisher/title/date entries prefer the direct source link.

The existing 15-minute scheduled News runner refreshes these private discovery
caches when due, then runs the normal news collector. General News lanes remain
keyless; Packer listing discovery uses the bounded API allowance above. The
current runtime schedule, other pipeline controls, accounts, settings, trusted
data and review gates are preserved. Failures retain last-good publisher data
for at most 24 hours and remain visible as partial/failed health; indexed
discovery continues when publisher recovery is unavailable.
