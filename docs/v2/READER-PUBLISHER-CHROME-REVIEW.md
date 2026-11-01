# Keep publisher site chrome out of the article reader

An observed Hortifrut article has no declared social image. Its header contains
country flags and a large illustrated menu. The Reader's eight-image limit was
filled by those images before it reached the article. A commerce heading,
“Buy”, also appeared before the actual source text. This repair targets those
two capture defects without rewriting the article or changing its trust status.

Declared social images retain priority. Otherwise, image extraction uses the
publisher's article/main region when available and excludes navigation,
sidebars, footers and hidden content. When semantic article markup is absent,
it excludes the site header and prefers a publisher figure over an unstructured
page banner. An article's own header remains eligible. A flag used within an
article is not rejected merely because it is a flag. Safe relative image URLs
resolve against the final publisher URL; alt text stays attached. Empty,
fragment-only, private and unsafe URLs cannot become article thumbnails.

Text and heading extraction exclude a site header while retaining headers
inside article/main. There is no word blacklist: a legitimate article section
called “Buy” remains. Publisher headings retain their original order; no model
generates titles or changes claims.

## Verification and boundaries

The initial synthetic regression suite reproduced six failures against the
unchanged implementation. Twelve regression cases now cover header-image
exhaustion, legitimate article headers and flag imagery, metadata precedence,
fallback banners, relative/hidden/unsafe URLs, navigation-only pages, exact
heading scope, existing image precedence and the selected-article capture path.
The combined Reader, preview, Firecrawl, capture-bound and prose-navigation
suite passes **125 tests in 10.02 seconds**, with one existing ReportLab warning.

The first bounded live-data rehearsal at `5f485120` exposed an older merge
defect: a captured image could be added under `article.image_url` and displace
an existing root-level source/operator image in the Reader. The stored input
stayed unchanged, but its display precedence did not. The preservation assertion
is retained. The repair now respects an existing public image at either level;
private/unsafe URLs cannot gain precedence. The failed attempt and its fresh
backup remain private. New-head CI, native review and a new isolated rehearsal
must establish acceptance; the earlier head's passing CI does not prove it.

A saved, bounded 67,426-byte public publisher response is replayed offline.
The original first image is a header country flag; the repaired first image is
the publisher's genetics graphic in its article figure. Removing only the site
header gives exactly the same 21 remaining passages as the repaired extractor.
The private replay keeps the HTML hash and both full image inventories. The
copyrighted page body is not committed or included in static output.

This changes only `feed_first_reader.py` and `article_structure.py`. Existing
source-copy and operator-edited article text/images keep their precedence.
The capture version, automatic collection policy and cache freshness remain.
Existing captures are not migrated or replaced: new captures use the repair,
and an analyst can explicitly reload source text through the existing control.
No paywall/consent/SSRF protections, account boundaries, publication/identity/
claim review gates, canonical records or domain schemas change.

This is separate from frozen platform #458, catalog/Map #449 and source #457.
It does not grant or repeat any pending release approval. All original 31
requirement definitions/order and the governing guide remain unchanged.
TD-122, article-body/source availability, fallback image ambiguity on other
publishers and wider visual-media coverage remain open. This is a bounded
repair, not a claim that every source now yields a correct or complete article.

Current-head CI, native desktop/phone review and a fresh isolated preservation
check remain required for this draft. A tested release requires its own scoped
approval before merge/deployment, a fresh release-time backup and retained
rollback/settings/data mounts.
