# Reader source destinations — November 3, 2026

Older Google News records can retain an opaque wrapper instead of a publisher
article URL. News cards previously described every destination as “Read original
at publisher,” including those wrappers. The selected Reader also accepted a
saved failed capture's redirect as its publisher destination.

This child of source-prose performance #482 adds a shared, read-only navigation
projection. Direct article links and locally decodable wrappers lead to the
publisher. The original `source_url` and review fields remain unchanged in the
record and feed card. Homepage links are described as websites. Google access
destinations are never described as publisher articles.

The selected Reader may reuse a successful saved capture only for the exact
original URL and item, or an existing unique exact-title publisher-discovery
match. A saved legacy capture without an item field remains usable through its
selected-item path and exact original URL. Failed, blocked, mismatched,
private-host and homepage redirects cannot supply an article link. This is
navigation, not a source-fidelity or statement-review decision.

When an article link remains unresolved, the Reader says so and offers the
recorded publisher website when available. The website is not presented as the
article. Original text, images, the Article/Brief switch and the prominent
newspaper action remain. Consent text stays excluded by the existing body
classifier. No URL is guessed from a headline or publisher name.

Feed presentation only uses existing metadata and local wrapper decoding. It
does not open capture bodies or scan publisher discovery; only the selected
Reader uses its existing capture read and bounded discovery cache. There is no
new network request, paid API call, capture migration or write on GET. Opaque
links with no saved resolution can still require publisher navigation; this
does not claim that every article can be recovered or read inside the app.

## Acceptance

The initial 112 focused checks and the broader 199 Reader/News/Digest/feed/company/capture checks pass (overlapping sets). The first
local test attempts exposed test-harness setup issues (an unavailable optional
HTML parser and a missing artifact parent directory); the tests now use only
the standard library and the existing isolated fixture setup. No dependency
was added. Native desktop and 412px phone review confirms the unresolved message, original publisher link, available article body/image and return to the grid without overflow. Final-head CI is recorded in the PR and ignored runtime receipts when complete.

This is a draft, not a deployed release. #477 is already deployed. Pending #480
and the tested #482 retain their frozen heads and separate approval scopes.
No source, canonical variety, human decision, schema, benchmark, account,
collection setting or provider qualification changes. Cold-load performance,
independent catalog audit, source/photo rights and held Map figures remain open.
