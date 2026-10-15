# Requested sustainability sources — October 14, 2026

The operator requested Trellis, Watershed Blog, The Packer Sustainability Insights,
and AgFunderNews Climate & Sustainability. These are additional unreviewed News
sources; they do not create Evidence, assign berry identities, or bypass review.

Production-host probes returned:

| Source | Scheduled discovery | Live News discovery | Access result |
| --- | --- | --- | --- |
| Trellis | Publisher `/feed/` | Same RSS | HTTP 200, 10 entries |
| Watershed Blog | Declared `/blog/sitemap.xml`, blog paths only, 50-item cap | Indexed `site:watershed.com/blog` RSS | Sitemap HTTP 200; non-blog URLs explicitly excluded |
| Packer Sustainability Insights | Indexed `site:thepacker.com "Sustainability Insights"` RSS | Same search RSS | Search HTTP 200, 100 entries; direct section HTTP 403 |
| AgFunderNews Climate & Sustainability | Category `/feed/` | Same category RSS | HTTP 200, 50 entries |

Sources are enabled with daily discovery cadence. The existing article/news
dispatcher evaluates due Sources every six hours. Live News invokes the four
specialist queries on Refresh. Only these query IDs from the specialist provider,
with a matching publisher domain, expand the berry-only relevance scope. Crop,
country, company and date filters still apply; stories without berry identity
do not appear under a berry-specific filter.

Watershed sitemap `lastmod` is modification metadata, not independently verified
publication time. Live News uses indexed publication dates. Search coverage can
lag and does not guarantee enumeration of a complete publisher section. The
Packer may also refuse reader body requests; keep the explicit publisher link
and honest unavailable-content state. Do not bypass its access restriction.

News discovery remains keyless. Selected Packer reader fallback uses the
configured Firecrawl connection and its existing credits; no generated source
text or model cleanup is requested. Source items remain private and unreviewed
until the existing human publication and Atomic Evidence gates.

## Connected-provider checks

Operator-authorized live probes found Exa could return 3,788–7,445 characters
for three indexed Packer stories, but its Contents endpoint failed for three
specific recent Sustainability Insights articles. Perplexity Search returned
3,731 characters for one of those exact recent URLs; section comparison showed
an omitted section, so this is partial source text, not a complete article.
APITube returned no matches in the bounded test; the connected NewsCatcher key
returned HTTP 401 on the separate News API article-search endpoint. These probe
paths do not substitute differently titled stories. Private receipts remain
under `inbox/operations/publisher_api_probes/`.

The production Compose service omitted `FIRECRAWL_API_KEY`; this release adds
optional pass-through and documents it in `deploy/.env.example`. The operator's
existing credential was located in the separate private keys file, authenticated
against Firecrawl, and installed in the private production environment with a
protected rollback copy. Firecrawl returned the exact recent Packer article,
including all five main sections and the final paragraph, without interstitial
text. HTML structure was verified separately.

When a selected Packer story cannot be read directly, the reader uses at most
two bounded Firecrawl requests: the explicitly requested Sustainability Insights
listing to resolve one exact headline when necessary, then that exact article.
Publisher domain, article path, returned URL, headline and source-body structure
are checked. No guessed URL, substitute story, generated cleanup, cross-domain
redirect, homepage body or consent text is accepted. Capture reuse and negative
retry cooldown apply; explicit refresh requests fresh API content. News listing
requests do not call Firecrawl. Indexed section homepages are excluded as stories.

The existing `bios-collection.timer` was enabled but inactive when audited.
Daily Source cadence is configured and initial discovery completed, but News
refresh remains the active acquisition path while that broader timer is stopped.
This change does not resume unrelated scheduled collectors.
