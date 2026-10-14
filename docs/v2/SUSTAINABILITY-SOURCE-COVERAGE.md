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

No paid provider or model calls are required. Source items remain private and
unreviewed until the existing human publication and Atomic Evidence gates.
