# Design review audit — September 30, 2026

## Decision

The user has accepted the current UI direction. Freeze the refined Glasshouse palette, first berry icon, dense/full-width News approach, compact top navigation, grouped More menu, overlay Reader and company dossier pattern. Do not restart visual exploration. Acceptance covers demonstrated surfaces; unrelated page layouts still need task-appropriate migration.

Reviewed against the conversation, original pasted Global Intelligence Explorer requirements, current prototype, navigation inventory, source code and mission. No requested feature is intentionally dropped. This audit found under-specified preservation of Market Snapshot in the redesign handoff and corrected it. It also found stale proposed-navigation/visual-approval wording and reconciled it with the accepted design.

## Request coverage

| Request | Present now | Remaining work |
| --- | --- | --- |
| Bright agricultural identity, restrained pink, contrast, hierarchy, dense full-screen use | Refined Glasshouse; V1 icon restored; six complete cards at 1440×900 | Shared tokens/components and all-page copy/hierarchy audit |
| Newest-first News and 7d/30d/YTD/custom dates | 22 descending dates; date controls and honest historical empty results | Production query and URL-state integration |
| Multi-select berries and countries; map shares scope | Blueberry + Raspberry and YTD carried into Map Explorer with 15 sample records | Preserve actual Explorer query, layers, data and source limitations |
| Trusted versus raw Unreviewed; thumbs up/down; images | Both scopes and feedback UI; all 22 feed cards have labeled illustrative images | Persist real feedback; preserve human gates and real source images |
| Less disruptive Reader; article text inside plus external original | Overlay; default Article; separate Brief; native Costa article verified; newspaper link | Completeness/identity checks, publisher images, availability and continuity states |
| Four descriptive Reader icons and delayed tooltips | SVG thumbs, disk and newspaper; 2-second CSS hover delay, accessible labels and immediate keyboard descriptions | Full pointer/touch/accessibility checks; production-state feedback |
| Less system language; primary information first; secondary detail minimized | Brief's supporting notes collapsed; mission rule applies app-wide | Entity/operations copy still contains legacy/internal wording to migrate deliberately |
| Company alphabetical navigation, independent favorites and tiers | 102 entities, A–Z/#, Tier 1/2/3/Untiered; browser persistence | Shared analyst state and reconciliation with existing tier/watch/mute meanings |
| Custom company lists across relevant views | Multi-membership, management and shared predicates in demo | Integrate with saved/following/watch services; do not turn a list into automatic alerts |
| Editable company logos, website, LinkedIn/social | Upload/URL controls and editable links | Durable media/profile storage and private/public boundary |
| Company-associated People, highlights and editable social profiles | People tab in each dossier; no separate redesigned global People or News section | Real person identity/affiliation service, durable edits and useful sparse states |
| AI collection with manual corrections always possible | Requirement recorded; manual preview editors work | AI enrichment is not implemented; provenance/review and manual-edit protection required |
| Learn top level; Statements under More; no lost sections | Correct primary placement; 44 More links, eight groups; 50 destinations inventoried including route/anchor variants | Full routed-page audit, not just visible navigation; old routes and permission boundaries preserved |
| Annual market statistics below Explorer | Four cited US/Peru blueberry figures; country/berry scope and honest gaps | Expand verified public coverage, refresh/revision handling, existing trade adapters and snapshot export |
| Variety Growing regions and company Operating regions | Browser-local editor, linked-source prefill, map layers; 45 existing operating links, no invented variety locations | Full variety profile section, shared durable state, automatic proposals with human review, status/as-of filters and subnational mapping |
| Market Snapshot composition and export | Existing Explorer workflow is a preservation requirement; now explicit in mission | New styling not reviewed here; inherit countries/berries/evidence, include/exclude sections and verify export |

## Recommended final representative reviews

1. **Learn:** one concept page and its entry/browse experience. It is explicitly a primary destination but currently opens the existing app, so the new learning layout has not been reviewed.
2. **Market Snapshot builder and one export:** verify that map scope flows into composition and that a dense screen layout produces a readable report. This was central to the original Explorer mission and is absent from the design demo.
3. **One dense Statements or Varieties page:** test table hierarchy, filters, sorting, long cells and record detail. This gives coverage for information-heavy page families beyond cards/dossiers.

These are targeted applications of the accepted design, not three new visual directions. Saved/Following, settings, queues and other pages can be reviewed in their implementation slices using the same shared system. All must remain accessible; More links are not redesigned versions of those pages.

## Concrete gaps found

| Priority | Observation | Required outcome |
| --- | --- | --- |
| Before Reader migration acceptance | At 1440×900 the open Reader covers the Trusted/Unreviewed controls (confirmed by visible hit testing). | Keep a usable scope/review control reachable while reading without changing the accepted overlay pattern. |
| Before Reader migration acceptance | Article → Brief → Article resets reading scroll to 0; measured prior article offset 369px. | Remember position per article and per view; preserve focus/selection during actions, transitions and data arrival. |
| Before Reader migration acceptance | Native Article renders publisher paragraphs and byline but no inline publisher images. Feed/Brief images remain generated sample illustrations. | Preserve available source images/captions with honest missing-image states; never present illustrative assets as documentary publisher images. |
| Before data integration acceptance | Article capture can return text, but this prototype does not validate that extraction is complete or that a changed URL still matches the stored story. | Exercise full/partial/unavailable and article-identity checks using existing services; keep source dates and uncertainty clear. |
| Before all-page acceptance | Learn, reports, Saved/Following, Statements and other More destinations open the old app. | Migrate by page family and verify behavior. Do not report a complete redesign based on the shared shell alone. |

These are recorded deviations, not verified fixes in this audit. No major UI redesign was performed during the review.

## Implementation gates, not missing visual decisions

- Real persistence: article Save/feedback are memory-only in the demo; company marks/lists/profile edits are local to this browser. The old app does not share them. Synchronize via established production services and define feedback, Saved, Following and list behavior without duplicate stores.
- Reconcile the existing Tier 2 default and Watch/Muted semantics with approved Untiered and independent favorites; no silent data reset.
- Keep company relationships, evidence classifications and review gates intact. A thumbs-up or AI suggestion does not confer trust.
- Verify sparse company/People records, rejected uploads, failed images, unavailable article text, restrictive filters, loading and stale content.
- Complete keyboard/focus, 200% zoom, reduced-motion, contrast on translucent surfaces and long-content checks. Prior viewport tests are useful evidence, not a complete accessibility audit.
- Preserve old bookmarks/deep links and permission-dependent/static navigation. Verify real links and export pathways, not only route labels.
- Freeze shared design tokens/components for execution; current prototype CSS has incremental exploratory overrides and is not a production component library.

## Evidence from this audit

At 1440×900: six complete News cards, 22 article images, dates descending, approved five-item top navigation. Blueberry + Raspberry and YTD persisted into Map Explorer (15 matching sample articles). Companies exposed A–Z/#, favorites, tiers, lists and Overview/News/People/Connections. Costa's People tab contained two historical mentions and editable/add/highlight controls; no global People navigation. The native Article showed six publisher paragraphs; its separate original link was available. Past 7 days returned zero with an explicit historical-sample explanation. The three Reader gaps above were observed directly. Earlier focused verification covers list persistence, logo upload, More containment and keyboard tooltip behavior; it was not exhaustively repeated here.

## Handoff status

Local branch: `feature/immersive-design-sprint`, baseline `d2d1759`. The user authorized pushing this checkpoint. The push/PR outcome is recorded in the handoff response; this audit does not imply merge or deployment. Before production implementation, reconcile with current canonical. Production application code has not been migrated. The local preview server is `scripts/serve_design_studio.py`; it binds to localhost and reads only its fixed public sample articles on demand, with memory-only body caching.

## Additions after UI acceptance

The market statistics and editable region layers above were requested after the initial review. Include the growing-region profile/editor and market-data scope in the final representative Varieties and Snapshot reviews. The functional prototype demonstrates local edits and country-level mapping; it does not establish verified commercial footprints or automated extraction. No canonical domain records were changed.
