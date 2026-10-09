# Publisher article hierarchy review

October 8, 2026. Product/UI and acquisition presentation follow-up to draft #368.
The accepted Glasshouse layout, news grid and human review gates remain intact.

## Problem and behavior

Original news bodies were indexed correctly but publisher section headings and
interview questions were rendered as ordinary paragraphs. New article acquisition
now retains optional `heading_level` display hints for exact publisher h2–h6 text
already present in the normalized body. The personal Article reader, legacy full
reader and legacy overlay render those titles distinctly. No generated headings,
rewritten answers or punctuation-based guesses are used.

Explicit Reader capture retains short publisher headings in source order, excludes
navigation/aside/footer/hidden content, and records matched heading hints. Its
existing 24-passage limit is unchanged, but reaching that limit now sets `partial`,
`truncated` and `article-text-limit` rather than reporting a complete capture.
Bounded HTTP, redirect, paywall and private/public protections remain in force.
Capture source binding also checks the original URL, with the final URL as a
fallback for older direct results. A mismatched source cannot lend its text or
heading metadata to another record.

The article artifact gains one optional integer display field, 2–6. Existing
paragraph text, indexes, normalized text hash and evidence locators are unchanged.
No Variety domain schema, registry, rights or geographic model changes are made.
Operator-written stored bodies still win over captured text and are not annotated
from a cache. Old bodies without heading metadata remain readable as paragraphs;
this change does not silently reacquire or migrate them.

## Real original-source proof

The existing configured Italian Berry source's original article is
https://italianberry.it/en/news/g-viva-g-berries-raspberry . A new real fetch through
`article_acquisition.fetch_article` produced 35 paragraphs, 1,506 words and 12
publisher h4 headings. Compared with the earlier pending acquisition, every
paragraph's text/index and the normalized source content SHA are identical.
The existing draft remains byte-for-byte unchanged, draft / in_review.

Native browser review uses a separate explicitly identified preview copy,
`ev-reader-hierarchy-g-viva`, in this task's ignored, isolated localhost runtime.
It is not a new production story, approved Evidence, catalog addition or new
coverage-count result. Source body text is not committed. The reviewed image is
still the publisher's original raspberry photograph.

A separate real bounded Reader capture returned HTTP 200, 24 passages and 10
heading hints. It correctly reported partial / article-text-limit; no existing
private capture was saved or replaced by this proof.

## Browser and automated verification

- Native desktop proof: publisher questions use compact bold headings and thin
  section rules; answers remain regular body text. Article/Brief and original
  publisher actions remain top-level.
- Native mobile proof: actual width and scroll width both 375 pixels; 18px source
  headings versus 15px body. The full reader's sticky action bar was initially
  behind the 121px mobile header and now starts at 122px, fully visible.
- Stylesheet versions changed so existing browser caches receive the new rules.
- 168 affected tests passed, one existing warning, 17.56 seconds. Tests cover
  unchanged words/indexes/hash, original source heading matching, ambiguous and
  hidden/chrome exclusions, unchanged operator bodies, mismatched URLs, capture
  truncation, non-article heading shells, escaped publisher text, personal and
  legacy readers, patent structures, acquisition outcomes and variety/Digest gates.
- An initial new source-binding assertion failed for direct results without
  requested_url. The production fallback binding was fixed; the assertion remains.
- Final shared reader/shell verification: 30 tests passed, one existing warning,
  16.86 seconds; overlapping the affected run, not an additive total.
- Record validation passed. All 2,771 original data JSON files and canonical
  expansion guide are unchanged.
- Local public static build: 1,755 pages, unpublished draft IDs/titles excluded.
  Final asset-version/mobile synchronization was rebuilt successfully: 1,755
  pages and the same unpublished-ID/title exclusion check.
- The first child CI static-safety run caught an existing required relative
  app.css URL assertion after live cache versioning. Static pages now retain
  their original relative asset path; only live pages receive that cache query.
  Original test assertions are preserved; 22 focused static/reader/shell tests
  passed, one existing warning, 19.02 seconds.
- Parent #368 head b0ec41e passes all four checks: 4,441 tests / 11 skipped /
  two warnings / 478.11 seconds. Run 37886083984, Python job 113676332471;
  live watch session 90121 was consumed with terminal success.

Private proofs/screenshots stay under ignored inbox/european-portfolio-followup:
article-hierarchy-real-proof.json, article-hierarchy-reader-capture-proof.json,
article-hierarchy-desktop.png and article-hierarchy-mobile.png.

## Remaining goal scope

This resolves the observed loss of available publisher headings in new article
and explicit capture paths. It does not recreate all publisher formatting, infer
missing headings, migrate operator edits or establish universal article coverage.
No generated emphasis changes source claims into reviewed facts. Stored corpus
acquisition, pending News/subscribed Digest inventory parity, complete current and
historical portfolios, independently reviewed real recall, rights/profile depth,
human catalog authoring and the integrated release review remain open.

CAT-01/CAT-02/TD-116 and the ongoing goal remain active. No merge, deployment or
other-berry Landscape rollout. No user input is needed for the next safe work.
