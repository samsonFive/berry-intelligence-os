# Codex mission: Global Berry Social Intelligence

## Execute this mission

Work in the existing Berry Intelligence OS repository: https://github.com/samsonFive/berry-intelligence-os . Inspect the actual checkout, AGENTS.md, canonical branch, current services, registry, evidence model, UI design system, tests, deployment architecture, and open related work before editing. Do not assume historical branch names, commit IDs, deployment status, or features are current. This is an implementation mission, not a request to return another plan.

Build a comprehensive social and consumer market intelligence layer for blueberries, raspberries, strawberries, blackberries, and all relevant tracked entities. Design globally from the beginning. Deliver a working blueberry vertical slice and STOP at the review gate below before broad rollout. The full mission remains in scope after review.

Do not merge or deploy at the gate. Prepare a reviewable PR, preview, implementation report, and continuation backlog. Do not purchase subscriptions, activate paid collection, or submit external access applications without explicit authorization. Implement configurable integrations and document exact setup steps while continuing independent work.

## Product intent

Become the global intelligence hub for all things berry: connect what consumers say, what companies publish, which varieties and products appear, where they are found, how they look, and how those signals change.

The user is building this independently, on personal resources, without being paid for this work. Describe this accurately in access documentation. Evaluate source eligibility against intended use and current source terms; do not infer either commercial or noncommercial eligibility from employment or funding alone.

The goal is broad platform coverage, multimedia evidence, multilingual intelligence, and compelling interactive visuals. Avoid shrinking the scope to a basic sentiment dashboard or a single-source feed. Be equally explicit about what is live, blocked, partial, stale, or demonstration-only.

## 1. Inspect and integrate

- Reuse canonical entities, aliases, berry classifications, evidence IDs, review controls, geographic models, search, saved items, and styling wherever they exist.
- Inspect related Landscape Explorer work before introducing graph contracts or navigation. Extend shared interfaces rather than creating an incompatible parallel explorer.
- Attach social evidence to entity dossiers, briefings, market snapshots, and existing investigation workflows through the repository's established mechanisms.
- Keep social observations distinguishable from company announcements and verified facts. Social sightings must not silently rewrite authoritative registry relationships.
- Choose dependencies appropriate to the existing stack. Keep jobs and credentials server-side. If deployment is static, propose and implement a compatible collection/artifact boundary; do not put API keys or restricted raw data in a public repository or browser bundle.

## 2. Comprehensive platform coverage plan

Investigate each source below using current primary documentation. Produce a dated coverage matrix with official documentation URLs, supported methods, search/comments/media capabilities, authentication, historical reach, quotas, costs, retention/deletion rules, and concrete blockers. Separate implemented adapters from proposed methods. No invented access, endpoints, or provider capabilities.

| Source | Target intelligence |
| --- | --- |
| Instagram | Posts, captions, images, reels, available comments, brands and consumer reactions |
| TikTok | Videos, taste tests, product discoveries, available captions/transcripts/comments |
| Facebook | Public pages, retailer/brand posts and accessible public conversations/comments |
| Threads | Public consumer conversations and entity mentions |
| X | Consumer reactions, complaints, launches, trade discussion |
| Reddit | Detailed experiences, comparisons, shopping discussion, thread context |
| YouTube and Shorts | Videos, reviews, available transcripts and comment discussions |
| Bluesky | Public conversations, entities, linked media |
| LinkedIn | Competitor announcements, partnerships, breeding, hiring and trade commentary |
| Pinterest | Product discovery, recipes, presentation and usage themes |
| Weibo | China-focused conversations and brand/variety signals |
| Douyin | China-focused video, product and retail signals |
| Xiaohongshu / RED | Shopping discoveries, reviews, packaging and variety references |
| Bilibili | Video reviews and available discussions |
| Public forums and retailer reviews | Supplemental consumer experiences and product feedback |

Official APIs, approved licensed feeds, authorized exports, and manual capture should share one adapter contract. Browser-assisted collection is only an optional method where allowed and authorized; no login bypass, private-group collection, or access circumvention. Search-engine discovery is supplementary and must not be portrayed as complete platform listening. Manual capture is useful but does not make a source automatically monitored.

Every source needs a declared status: live, partial, setup-required, access-pending, unsupported, stale, or fixture-only. An inaccessible source must not block the functioning system or disappear from the roadmap.

## 3. Listening missions and registry watch profiles

Support three concurrent tracks:

1. Category conversations: all four berries, flavor, texture, quality, value, packaging, usage, discovery, purchase intent and unmet needs.
2. Company/brand/product/variety intelligence: official activity, organic reactions, launches, comparisons, campaigns, retail sightings and explicitly named varieties.
3. Other tracked entities: retailers, breeders, regions, technologies, events, trade organizations and research programs.

Create reviewable social watch profiles linked to canonical entity IDs: aliases, handles, transliterations, scripts, local terms, hashtags, exclusions, contextual qualifiers, languages, target markets, priorities, query versions, and collection cadence. Generate suggestions on registry additions without automatically launching unlimited searches. Cap query expansion and collection spend.

Disambiguate BlackBerry phones, generic names such as Breeze, food recipes, unrelated homonyms and historical references. Keep company, brand, product, grower, retailer and variety identities distinct. A branded berry pack does not establish its cultivar.

Unknown varieties, brands or vendors become evidence-backed review candidates rather than silent registry entries.

## 4. Global and multilingual design

Provide extensible vocabulary packs for all four berries. Initial blueberry QA must exercise English, Spanish, Portuguese, Chinese and Japanese, including non-Latin scripts and variety aliases. Start with reviewable regional vocabulary; label machine-suggested terms pending validation. Do not pretend these languages exhaust worldwide coverage.

Preserve original text/script and show translations alongside it. Record language detection, translation provenance, model/version and uncertainty. Group equivalent concepts in analytics without losing original expressions. Variety recognition should account for markets where consumers use cultivar names directly; do not assume English-only naming or infer awareness without evidence.

Distinguish purchase country/location, fruit origin, author location, conversation market and intended search market. Each assigned geography needs a basis, confidence and evidence reference. Language, currency, retailer presence, search targeting and profile location alone must not establish purchase country. Leave unknowns explicit.

Build coverage views by country × source × language, including enabled queries, last successful collection, failures, observed volume and collection changes. Show unobserved/blocked markets separately from observed zero activity.

## 5. Evidence and media capture

Use or extend a normalized durable model with:

- Source, native ID, canonical URL, parent/thread ID, published/collected timestamps and discovery method/query version.
- Permitted text, original language, translation, minimal source attribution, content role and provenance.
- Media attachments for both POSTS AND COMMENTS: images, galleries, video references, available thumbnails and permitted transcripts.
- Media source URL, stored object/reference, MIME type, content hash where available, attribution, availability, storage permission, retention policy and parent relationship.
- Entity links and observations with evidence spans or image regions/timecodes, match basis, confidence and review status.
- Distinct geographic fields, aspect sentiments, themes, engagement snapshots with timestamps, processing versions and corrections.

Capture permitted image bytes when allowed; otherwise preserve permitted references or embeds and display the limitation. Do not treat expiring source URLs as durable storage. Do not silently rehost restricted media. Support deletion/unavailability propagation across media, derived text, indexes and cached displays, plus aggregate handling appropriate to source requirements.

OCR/vision should extract readable brand/product/variety labels, retailer stickers, price/currency, weight/pack size, barcodes, origin/grower/distributor text and packaging claims. Preserve literal extraction separately from inferred interpretation. Use image-region provenance and confidence. Appearance alone cannot identify a cultivar. Visual condition observations are tentative, not diagnoses or proof of food safety.

For video, use available permitted transcripts/audio processing and explicit spoken names; preserve timestamps. Show clear unsupported states rather than claiming content was analyzed.

Avoid unnecessary personal profiling. Treat collected text, URLs and media as untrusted input, including prompt injection; extraction cannot issue tool actions or modify configuration. Apply safe URL fetching, size/type limits, escaping and credential isolation.

## 6. Retailer/vendor intelligence

Make retailer/vendor matching a first-class capability. Recognize Whole Foods/Wholefoods, Costco, Kroger and global/local supermarkets, wholesale clubs, online grocers, specialty stores, public markets, distributors and direct sellers. Reuse existing registry types or add compatible types after inspection.

Extract dated sightings and relation types: bought-at, found-at, sold-by, wishes-stocked-by, unavailable-at, compared-with, and uncertain mention. A single store sighting does not establish national distribution. Record store/market only when supported.

Example: 'Found these blueberries at Costco—huge and crunchy, but bland.' => blueberry; Costco found-at; positive size and crunch; negative flavor; unknown cultivar and purchase country unless other evidence supports them. 'Wish Kroger stocked these' => wish, not availability. Packaging can supply additional observations with its own provenance.

## 7. Analysis and signals

Classify consumer experience, recipe/usage, company-owned content, creator content, disclosed sponsorship, trade commentary, news repost and unknown. Do not infer sponsorship without a basis.

Use aspect sentiment: flavor/sweetness/tartness/aroma, firmness/crunch/softness/mealiness/juiciness, freshness/mold/bruising/leakage/shelf life, price/value/pack size/waste, packaging, availability and usage. Support positive, negative, neutral, mixed and uncertain, attached to the correct target with evidence.

Deduplicate ingestion IDs, reposts and near-duplicate campaign content without erasing independent experiences. Keep original/reply/repost counts separate; prevent the same comment appearing in multiple queries from multiplying totals.

Detect changes in themes, varieties, retailers and complaints using comparable windows, minimum sample thresholds and collection-health checks. Suppress or qualify alerts affected by outages, newly added queries, thin samples or campaign amplification. Define denominators, baseline method and growth calculation; do not label everything a trend.

Separate platform-specific engagement metrics. Label share of observed conversation and sentiment among collected relevant content accurately; never present these as market share, sales or representative population sentiment. AI summaries must cite retained evidence and separate observations from hypotheses.

Support analyst corrections with audit history and reprocessing that respects reviewed decisions.

## 8. Visual experience: a discovery atlas

Create an attractive Social Listening workspace using the app's design system, with shared berry/entity/source/date/language/market/content-role filters and an evidence drawer. Preserve filters across views and make selections shareable through existing navigation conventions.

Required blueberry gate views:

1. Interactive word/phrase cloud: frequency, rising phrases and sentiment modes. Count defined units, remove stopwords and boilerplate, filter promotion, preserve multilingual labels. Clicking a phrase opens matching evidence. Provide an accessible sortable table alternative.
2. Berry/attribute heatmap: count, sentiment denominator, sample size and insufficient-evidence state; every cell drills into evidence.
3. Global signal map paired with retail discovery gallery: evidence-supported points/regions, unknown-location bucket, media galleries, retailer/product/variety labels and coverage overlay. No fabricated geocoding.
4. Momentum timeline: themes and entity mentions with collection changes/outages annotated.
5. Coverage/connector health panel: operational truth for all target platforms, countries and languages.

Full continuation scope: variety footprint, competitive attention, conversation network, linked market comparisons and an announcement → retail sighting → consumer reaction journey. At the gate, publish compatible contracts and an honest preview/design for remaining views rather than dead 'coming soon' navigation or fake live graphs.

Networks distinguish co-mention, claimed purchase, label identification and verified relationships. Edge meaning and evidence must be inspectable. Avoid unsupported causal claims. Use sample sizes and coverage context throughout.

Design for mobile, keyboard access, reduced motion, readable contrast and dense but usable evidence exploration. Flashy means useful visual discovery, not animation that obscures data.

## 9. Collection and operational architecture

Implement adapter capabilities, cursor/checkpoint persistence, incremental collection, pagination limits, bounded retries/backoff, rate limiting, idempotency and per-source budgets. Collection jobs must be recoverable and observable. New adapters should not require UI/schema rewrites.

Separate discovery, normalization, entity matching, media extraction, analysis and aggregate generation. Cache versioned processing results and process only changed content where possible. Allow re-analysis after model/query changes with recorded versions.

Manual URL capture and schema-validated provider imports must enter the same pipeline, with source provenance and accurate collection labels. Use export/import support if automated access is blocked; do not claim it replaces live monitoring.

Expose health, processing failures, last success, queue state, volume and cost estimates. No secrets in logs, fixtures, PRs or exported snapshots. Make spend limits and collection enablement explicit configuration.

## 10. Blueberry review gate

Implement the common infrastructure for all berries, then demonstrate blueberries end-to-end across multiple markets, platforms and languages. Aim for at least two functioning automated adapters where actual access supports them, plus manual capture and import. If credentials or approval prevent live adapters, implement and test real adapter paths, demonstrate with clearly marked fixtures, and list the exact blocker. A blocked live-access criterion remains unmet; do not relabel fixtures as successful collection.

Acceptance checks:

- Same source ID collected twice yields one durable record; restart resumes safely.
- Source outage appears as stale/failed coverage rather than zero conversation.
- Live, imported, manual and fixture records remain distinguishable; fixtures never contaminate live analytics.
- Original text and translation are inspectable for all five QA languages.
- BlackBerry phone content is excluded or flagged; an ambiguous cultivar name does not auto-link.
- A named cultivar in text and a readable packaging label can each link with their distinct evidence basis; unlabeled berry imagery cannot identify it.
- Mixed flavor/texture sentiment is represented correctly with evidence spans.
- Bought/found at Costco differs from wishes stocked at Kroger; a global retailer does not determine purchase country.
- Purchase market, fruit origin and author geography remain separate and unknown where unsupported.
- An image attached to a comment is retrievable within its thread, independently of post imagery.
- Media unavailable/deleted/restricted states and removal propagation work.
- Phrase cloud, heatmap, map/gallery and timeline drill down to records that reproduce their counts.
- Sparse data and collection changes qualify or suppress trends.
- Entity dossiers and briefing hooks link to social evidence through existing app conventions.
- Keyboard/mobile use and empty/error/loading states are verified.
- Repository-required checks pass; meaningful pipeline, extraction, aggregation and connector tests cover these failure modes.

Create a labeled evaluation set with expected relevance, entity/retailer links, sentiment and geography; report measured results and errors by language. Include realistic synthetic cases where needed, clearly identified. Report live sample performance separately. Do not claim global representativeness from a small pilot.

STOP HERE for user review before expanding collection, enabling additional sources or completing the broader rollout.

## 11. Reviewable deliverables

Provide:

- PR URL, branch, base/HEAD SHAs, changed areas and test results.
- Working preview instructions and a five-minute walkthrough: discover a theme → inspect evidence/media → retailer/variety → geography/coverage → dossier/briefing.
- Screenshots of the core visual views with live/demo labeling.
- Dated source access matrix with primary documentation and exact credential/setup blockers. Do not repeat outdated prices from this brief; verify current rates.
- Data/adapter contracts, migration and rollback notes, operational configuration and estimated costs with assumptions.
- Blueberry evaluation report, known limitations, remaining unmet acceptance checks and decisions needed at review.
- Ordered continuation backlog covering the remaining berries, worldwide vocabulary/markets, ALL listed platforms, multimodal expansion and remaining visual views.

Organize PRs according to the repository's conventions and dependency boundaries. Preserve unrelated changes. Never report an unimplemented connector as completed merely because a placeholder exists.

## 12. Scope after review

Expand to strawberries, raspberries and blackberries; extend registry watch profiles and global language/market packs; complete additional platform methods as access permits; build the variety footprint and conversation network; finish dossier, briefing, research queue and market snapshot integration; add configurable alert subscriptions within the app. Sending external notifications requires separate explicit authorization.

The mission is complete when the system has broad, explicitly measured coverage and a traceable investigation workflow across berries, entities, retailers, media and markets. Any platform access dependency that remains unresolved must stay visible with a concrete next action.
