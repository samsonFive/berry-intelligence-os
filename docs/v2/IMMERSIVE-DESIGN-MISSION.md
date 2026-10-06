# Berry Intelligence immersive design mission

Create a bright, polished agricultural intelligence workspace that uses the available screen well and supports dense scanning, comfortable reading and fast investigation. Fresh green, berry color, translucent materials and clear contrast replace the earlier navy-led direction. Compact top navigation replaces the permanent wide sidebar as the proposed default.

As of September 30, 2026, the user accepts the current UI direction: refined Glasshouse, the first berry icon, compact top navigation, dense News, the right-side overlay Reader and the company dossier approach. This is the implementation mission and local handoff package. Approval settles the demonstrated visual direction and flows; it does not imply that every existing page has been redesigned or that production integration is complete. See [Design review audit](DESIGN-REVIEW-AUDIT.md) for remaining representative reviews and known prototype gaps.

## Core experience: News and Reader

Latest section-review decisions: **Personal Digest** combines Saved access, Reading Queue functions and stories from explicitly subscribed lists while retaining independent saved/read/priority/completed state and visible origin labels; **Landscape** becomes configurable by subjects, geography and included sections; **Learn** expands into visual, interactive lessons with selection-triggered Perplexity deep research; **Meeting Prep** replaces the War Room label. The user generally agrees with the remaining audit recommendations. See `APP-SECTION-AUDIT.md` → User review decisions for the acceptance scope and sequence, and `feature-requests/LEARNER-MODE.md` for the research-to-lesson addition. These decisions are accepted requirements, not claims of production implementation.

The News feed and Reader are the primary daily product experience. Their quality is the first implementation gate. The News prototype starts as a full-width article grid. Opening a story slides a Reader over the right side of the unchanged feed; Close or Escape returns to the grid, preserving filters, selected story, column widths and prior grid position. No geographic panel competes for News space. Map Explorer owns the geographic workspace and is a first-class lens on the same news, not a separate collection. It keeps the shared berry, country, search and trust filters, highlights tagged countries for the selected story, and allows map selection to filter the feed. Opening a story overlays the Reader on the right without replacing or resizing the underlying map/feed; closing restores the unobscured workspace. Returning to News preserves scope and selection. Article discovery, scanning, opening, reading, feedback, saving and returning must work as one continuous experience.

Visual language approval and page-layout approval are separate decisions. Comparing Daylight and Glasshouse does not authorize imposing this layout on every route. Both News studies use identical geometry to isolate the material and typography choice. Validate each route family against its own task before changing its layout.

## User direction

- The app is used daily for berries and agricultural developments. It should feel bright, colorful, organic and futuristic.
- Use glass, transparency and subtle liquid-like transitions where they improve the experience. Maintain strong contrast on reading surfaces.
- Use the full screen and keep information dense. Reduce empty margins, tall headers and excessive padding.
- Establish unmistakable hierarchy between headlines, summaries, sections, body text, metadata and provenance, especially in the Reader.
- Keep feed, geography and supporting evidence connected without repeatedly losing scope or reading position.
- Retain supplied article images, multi-select berry scope, clearly separated Trusted and Unreviewed views, and existing review semantics.
- A dark appearance may remain an option; it is not the defining identity.

The user's later direction supersedes earlier navy and sidebar-preservation assumptions for this redesign. Existing domain, provenance, publication and confirmation rules continue to govern implementation.

## References and interpretation

| Reference | What informs this mission |
| --- | --- |
| [Logistics Shipment Dashboard](https://dribbble.com/shots/26859326-Logistics-Shipment-Dashboard) | Alignment, connected panels, restrained depth and coherent finish. |
| [Arion Surveillance System](https://dribbble.com/shots/27237001-Arion-Surveillance-System) | Compact top navigation, a large central canvas and contextual information at its edges. |
| [Matchboard Football Match Dashboard](https://dribbble.com/shots/27235118-Matchboard-Football-Match-Dashboard) | Several useful views visible together. It retains a narrow icon rail. |

The references are visual inspiration. Their dark palettes, small screenshot text, domain-specific metrics and unverified interactions are not requirements for Berry Intelligence.

## Initial audit

The baseline is Explorer commit `d2d1759`. Prototype work is isolated on `feature/immersive-design-sprint`; its base includes PR 272. Reconcile against canonical before production migration.

| Observed finding | Evidence | Consequence |
| --- | --- | --- |
| Navigation occupies 220 to 260 pixels before gaps and padding; an open Reader adds a third column. | `app/static/berry_os.css`, `.bos-shell` and `.bos-shell.has-reader`. | Reclaim navigation width for investigation. |
| At the user's approximately 1050-pixel browser width, navigation appears as a long block above the feed. | Browser inspection of `/today?entity=seed-org-0054`. | Include this width in acceptance, alongside desktop and phone endpoints. |
| News places watched counts, multiple disclosures, nine filter fields and shortcut help before the cards. | `feed_first_today.html` and the inspected page. | Consolidate controls and status so actual intelligence appears earlier. |
| Navigation lists 14 primary destinations plus Explorer. | `feed_first.py::NAV` and `_feed_first_rail.html`. | Group navigation by analyst task while preserving discoverability. |
| The template inventory contains 69 pages extending `base.html` and 21 extending `base_stakeholder.html`. | Initial static template count; not a verified route count. | Inventory actual routes and nested components before claiming complete migration. |
| Multiple card, Reader and shell implementations coexist. | Feed-first templates, shared V2 Reader, stakeholder shell and expansion guide TD-10. | Define shared presentation contracts and migrate in coherent groups. |
| Today reports no live cache and displays historical stored coverage. | Browser inspection. | Preserve freshness disclosures and meaningful empty states. |
| The 22-record prototype sample has three records linked to active canonical facts and no stored image URLs. | `artifacts/design-sprint/content.json`. | Exercise sparse Trusted and populated raw views with clearly labeled generated illustrations for this visual study; no original source images exist in the sample. |

This is an initial audit. Complete the route and state checklist during the first implementation slice; every route has not yet been visually inspected.

## Working prototype

Run `python scripts/serve_design_studio.py` and open `http://127.0.0.1:18322/`. The simple static server alone cannot supply native article text. It uses 22 curated published records across four berries, retaining source references, stored summaries and active fact classifications. Counts describe only this historical sample, not live news or total coverage. It does not access runtime inbox data.

**Daylight** uses crisp warm-white surfaces, botanical green, subtle borders and restrained berry accents. The image-led News feed and full reading pane share the workspace. An editorial serif headline is an explicit option to compare with the sans-serif interface.

**Glasshouse** uses translucent panels over soft green and berry-colored light, with rounded surfaces and the same News layout as Daylight. Geographic context appears in Explore. The Reader remains comparatively opaque and has a stronger sans-serif headline. It uses the same content and actions as Daylight.

Both directions provide berry and country combinations, search, Trusted and Unreviewed selection, story selection, company filtering, keyboard story movement, Reader expansion and demonstrative saves and feedback. Feedback does not call extraction or review APIs. Source and company links open the real source or existing local app in another tab.

Four generated agricultural illustrations provide feed thumbnails and Reader hero images. Every use is visibly labeled as illustrative, source-image fields remain untouched, and sample summaries and dates retain their stored provenance; the separate Article view retrieves publisher text on demand. Production should use actual publisher images where available; generated imagery is a prototype-only treatment, not a default replacement for documentary source photos. Prompts and asset provenance are in `artifacts/design-sprint/images/README.md`.

Review core interaction design during the prototype phase: scanning, preview depth, grid-to-Reader transitions, collapse/return behavior, scope and comfortable density. Feedback/save controls remain memory-only demonstrations; service integration, persistence and production review semantics are verified during implementation.

Panel resizing, persistent layout preferences, production review actions, complete navigation and exhaustive state coverage remain implementation work. The prototype is a visual and interaction study, not a completed app migration.

## Proposed navigation and layout

Use the selected top bar: News, Map Explorer, Entities, Learn and More. More groups secondary workspaces into eight headings across four desktop columns, adapting to smaller widths. People belongs inside a selected company dossier. Preserve all destinations in the navigation inventory and audit remaining detail routes before migration. Search shortcuts supplement visible navigation.

The default News workspace offers an image-led article grid with a collapsible Reader. Compact cards are the default: a small thumbnail, readable headline, three-line stored summary, berry/geography tags, linked companies and relevance/save actions. More context expands geographic detail and labeled stored interpretation in place. Detailed cards remain an optional density choice. A shorter shared header and filter bar reclaim screen area; do not gain density by shrinking body text to illegibility. Do not invent context for sparse records. Grid columns respond to viewport width and remain unchanged when the Reader opens above them. Connected companies remain available inside the article. Map Explorer gives the map a substantial canvas beside the feed, with the Reader available as an overlay and exposes mapped versus untagged story counts. The prototype links to the existing Explorer for its implemented mission functionality; production must reuse that workflow and its services, not replace it with a decorative map. Reading focus enlarges the Reader. On narrower screens, secondary context moves below the primary task. Mobile follows a clear reading sequence with an easy return to the selected story.

Workspace scope includes berries, countries, company and time. Review state and sort order remain explicit. Production navigation preserves meaningful selections in URLs, restores reading position and returns keyboard focus. Empty states distinguish restrictive filters, absent coverage and acquisition failures.

## Shared system

Finalize tokens after visual review. Define color roles for canvas, reading surface, raised surface, primary action, selection, border, muted text, focus, trust state and berry categories. Category color does not imply trust or confidence.

Define typography roles for page title, headline, lead summary, section heading, body, label, metadata and provenance. Headline and summary must remain visibly distinct at normal zoom. Use a compact default with consistent spacing increments and accessible controls; reclaim layout waste before reducing text size.

Use translucent navigation and context panels with solid fallbacks. Keep long-form reading surfaces clear and avoid continuous decoration behind text. Define hover, focus, selected, disabled, loading, saved, failure and empty states. Motion should be short, optional under reduced-motion preferences and never delay a task.

Build shared header, navigation, scope bar, article row, image treatment, Reader sections, trust marks, entity connection, table, dialog, empty state and status notice components. Avoid page-specific copies.

## Implementation sequence

| Phase | Deliverable | Exit evidence |
| --- | --- | --- |
| 1 | Initial audit and two working directions | Compare the same content at daily-use viewport sizes. |
| 2 | Refined chosen direction and route inventory | Agreed material, navigation, density and type hierarchy; open choices recorded. |
| 3 | Shared shell and the complete News feed and Reader workflow first | Scan, scope, open, read, review and return use existing services; keyboard and URLs retain context. |
| 4 | Companies, varieties, geography and related intelligence | Shared components cover rich and sparse records; provenance stays available. |
| 5 | Reports, saved/following, queues and secondary tools | Each route family passes workflow checks; print and PDF are verified separately. |
| 6 | Remaining surfaces and retirement of old styles | No unexplained legacy exceptions in the route inventory; final screenshots and checks. |

Keep each phase reviewable and one owner for shared tokens and shell components. Additional agents may take bounded tasks only when authorized by the active collaboration rules.

## Product and engineering boundaries

Reuse existing retrieval, hierarchy, query and review services. Preserve source dates, classifications, evidence identifiers, URLs and human gates. Thumbs up is relevance feedback or extraction preparation, never automatic trust promotion. Prototype feedback must never become a real analyst decision.

Preserve public static separation from private runtime data. Do not move inbox drafts into published records, introduce live collection on page load, infer geography from headquarters, or present record counts as confidence or market share.

Changes to Variety, Trade, Weather, extraction qualification or intelligence schemas require a demonstrated blocker and a scoped decision. Add no framework or visual dependency without a concrete requirement. Preserve the canonical expansion guide; record intentional departures from older visual rules here.

## Acceptance criteria

- At 1440 by 900 and 1280 by 800, navigation, active scope, the first story and the start of the Reader appear without scrolling past a large header.
- Around 1050 pixels, navigation stays compact. At 390 pixels and 200 percent zoom, content reflows without horizontal page overflow or inaccessible controls.
- Normal text meets 4.5:1 contrast; large text and necessary UI boundaries meet 3:1 against actual composited surfaces. Verify translucent and solid fallback states.
- Touch targets, visible focus, dialog focus return and Escape behavior work. Shortcuts do not intercept typing. Reduced-motion preferences are respected.
- Title, source/date, summary, interpretation, fact/claim and provenance remain distinguishable in every Reader host.
- Scope updates relevant panels consistently, preserves a valid selection and handles a selected record disappearing from scope.
- Compact News should fit at least six complete cards at 1440 by 900 with filters visible, and at least four at about 1050 by 900 in the curated sample. Verify both rich and sparse cards; expanded context may increase card height.
- News and Map Explorer share filters and selected-story state. Map actions update news, the Reader retains geographic context, and missing geographic tags remain explicit. Trusted/Unreviewed stays available with the Reader open.
- Closing the Reader restores the full-width News grid, active scope, selected article and reading position. Escape closes it and returns keyboard focus to the article. Opening a card restores the Reader; previews contain enough sourced context to decide whether to read.
- News is the default daily destination and works without opening Explore. The Reader receives enough width for comfortable reading, visible title hierarchy and article imagery.
- Source images preserve aspect ratio and avoid layout shifts. Missing or failed images use a compact fallback.
- Visually verify empty, loading, failed acquisition, stale data, pending and trusted states with real or deterministic fixture content.
- Styling never changes confirmation, publishing, extraction or private/static behavior.
- Compare before/after screenshots for populated and sparse workflows. Require existing repository checks on the current PR head before merge; verify print/PDF independently.

## Handoff requirements

Provide this mission, selected prototype files and screenshots, route/state inventory, token and component definitions, service integration points, unresolved choices and phased acceptance evidence. Confirm the current branch and canonical merge state. Do not infer working behavior from a design reference.

The user can continue in this chat. A separate executor is optional once the local package is committed and made available. The visual direction is accepted. Recommended final representative reviews are Learn, Market Snapshot composition/export, and one dense Statements or Varieties view; remaining state checks belong in phased implementation. The audit lists concrete gaps and handoff gates.

## Entities / Companies prototype

Entities remains the broader navigation concept; Companies is its current design-study surface. Use a dense, searchable company directory beside a readable dossier, with berry, recorded-country and role filters. Country comes from entity metadata and must not imply operating footprint. The preview exports 102 published company records; it includes repository seed/example records and is not a live inventory refresh. Keep record counts distinct from confidence or competitive strength.

The dossier separates entity metadata, active stored statements (retaining fact/claim classifications), explicit relationship predicates, and related news. Overview, News, People and Connections are functional prototype sections. Related news is limited to the 22-record design sample and opens the existing shared prototype Reader, with a visible company filter. Missing news in this sample is not absence of news. The full existing dossier remains directly linked.

This is a proposed directory/dossier layout for visual review, not authorization to remove existing company capabilities. Production migration must retain the existing profile service, confirmed statements, source provenance, role distinctions, aliases, variety links and dossier depth. Other entity types need task-specific treatment rather than an automatic copy of this layout.

## Reading order and date scope

News always sorts by publication date, newest first; remove the curated-order choice. Apply the same ordering to related company news. Missing dates sort last. Shared News/Map Explorer filters include Past 7 days, Past 30 days, Year to date, All dates, and an inclusive custom start/end date range. Presets use the local calendar date, including today (7 days means today plus the preceding six days). Invalid reversed custom ranges do not apply. Open-ended custom ranges are allowed. Reset clears date scope. The historical preview defaults to All dates; recent empty results must remain honest. Production must preserve this scope in URL/navigation state.

## Accepted Glasshouse direction

Keep green and berry identity with minimal pink across the canvas. Use largely opaque near-white cards and Reader surfaces, translucent surrounding chrome, visible green-gray card outlines, restrained shadows, and a distinct selected state with a green edge. Darken secondary text instead of relying on low opacity. Keep keyboard focus explicit and reduced motion supported. Daylight remains available for comparison, but refined Glasshouse is the current preview default.

Follow [WCAG contrast guidance](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum): normal text at least 4.5:1; necessary non-text indicators at least 3:1. Checked opaque palette pairs: main text/card 12.21:1, secondary text/card 5.94:1, secondary text/selected card 5.32:1, controls' border/fill 3.77:1, links/card 6.84:1. These are targeted color-pair calculations, not a full accessibility audit or proof of every composited state. Continue responsive, keyboard, zoom, all-state and composited-surface verification during implementation. Comfortable daily use still requires user review.

## Company alphabet, favorites and tiers

User-approved tier labels: Tier 1, Tier 2, Tier 3 and Untiered. Favorite is a separate boolean; tier is a separate optional assignment. Neither changes the other, review/trust state, article saves, following, or watch status. Do not automatically assign tiers from relevance, record volume or evidence strength.

The directory is alphabetical, with All / A–Z / # controls narrowing names by initial. Available letters reflect other active directory filters. Alphabet scope belongs only to the company directory. Favorite and Tier filters are shared between Entities, News and Map Explorer; news matches explicit company links, with favorite and tier requirements satisfied by the same linked company. Do not infer company links from article keywords. Unlinked articles do not match company-mark filters. Marks appear alongside linked company names in cards and the Reader. Controls are available directly in directory rows and the dossier.

Prototype assignments persist independently in browser-local storage under `berry-design-entity-preferences-v1`, keyed by canonical entity ID; filtering/reset never deletes assignments. This does not write the existing app, publish records, or synchronize across devices. No favorites or tiers are preassigned. Production must use one shared analyst-state service across all applicable routes, migrate identifiers carefully, and preserve provenance/private-static boundaries. The existing feed-first service has `entity_tiers` with tier1/tier2/tier3/watch/muted and a Tier 2 default; explicitly reconcile its default and watch/mute behavior with the approved Untiered state. Do not silently treat existing assignments as Untiered, convert Watch into Favorite, or create independent page-local stores.

Acceptance: A–Z and search combine with berry/country/role filters; row and dossier controls agree; favorite and tier change independently; assignments survive reload; shared filters preserve state across views; combined filters match the same company; removing a mark while filtered produces a correct empty state; keyboard focus survives rerender; clear-filter actions retain assignments. Test changed preferences must be restored after validation.

## Custom company watch lists

Support user-named lists for particular company watches alongside Favorite and Tier. A company may belong to multiple lists. List membership, favorite boolean, tier assignment, article saves, and underlying review/trust status are independent. Do not invent list memberships or trigger collection, notifications or alerts when a company is added.

Expose Lists controls in directory rows, dossiers and the Reader's company context. The shared Watch list filter is available in Entities, News and Map Explorer; list badges alongside linked companies can apply that same filter. A story matches through explicit linked company IDs. When favorite, tier and list filters combine, one linked company must satisfy all predicates. List/date/berry/country scopes remain composable. Company initial-letter navigation is local to the directory. Clearing filters preserves saved lists and memberships.

Management supports create, rename, company search, adding/removing members, and reversible archive/restore. Names are trimmed, nonblank, limited to 60 characters and unique case-insensitively, including archived lists. Stable IDs preserve membership and filter references through rename. Empty lists legitimately show no matching companies or articles. Archived lists retain membership for restoration and are excluded from active filters and badges; archiving the selected list clears that filter explicitly. Mark counts represent unique company memberships, not confidence or alert volume.

The prototype persists lists under `berry-design-company-lists-v1`, separate from company favorite/tier preferences. It uses browser-local state only and leaves published records, runtime watch services and the original app unchanged. Production must implement a shared private analyst-state list service referenced consistently by every applicable view and persisted across navigation/reload. Reconcile this grouping with existing watch inventory rather than replacing watch objects or creating parallel alert stores. Group creation itself does not authorize automatic acquisition or scheduled work.

Acceptance includes multi-list membership, independent marks, rename without lost membership, duplicate-name validation, unlinked/empty news states, shared filter transitions, Reader editing, storage persistence, archive/restore, modal keyboard focus and narrow-screen usability. No list data may enter public static output unless a separately authorized product decision changes that boundary.


## Review contract and feature ledger

This phase reviews visual language, information hierarchy, navigation placement and core interaction flows. Functional prototype controls are review aids, not evidence of production service integration. Record each new request here before execution; clearly distinguish an accepted requirement from an approved visual treatment. Do not silently delete a section or infer approval for a production migration from approval of a mockup.

The navigation inventory is [DESIGN-NAVIGATION-INVENTORY.md](DESIGN-NAVIGATION-INVENTORY.md). It reconciles 50 unique destinations from current and older visible navigation, including anchor/query variants. Learn is a top-level item; Statements sits under More. Local preview links open retained application sections whose redesign is pending. The final route/permission audit remains an implementation gate. More uses eight labeled groups across four desktop columns, preserving every destination; narrower widths use two columns or one, with internal scrolling.

| Requirement | Current review artifact | Production work still required |
| --- | --- | --- |
| Refined Glasshouse, dense News, hierarchy, images | Interactive prototype; generated images labeled | Shared tokens/components, actual source image handling, complete accessibility checks |
| Newest-first, date presets/custom range, berry multi-select, trust/country filters | Interactive sample | Reuse application query/filter contracts and URL state |
| Map Explorer and shared scope | Sample map/feed with preserved selection | Preserve implemented Explorer mission functionality and services |
| Reader overlay | Original article text inside the app by default; separate Brief view; right-side overlay, Close/Escape and optional wider reading | Shared live Reader, keyboard/focus and route/history integration across entry points |
| Favorites, Tier 1/2/3/Untiered, custom watch lists | Browser-persisted prototype with shared company predicates | Shared private analyst state across applicable views; no implicit monitoring |
| Company logos, website and social/LinkedIn | Upload/URL/contact editor, browser persistence and stored-detail restoration | Validated media storage, provenance, access control and synchronization across entity surfaces |
| People | Editable, highlightable people inside each company dossier's People tab | Existing person identities/affiliations and durable manual edits; no global People navigation or News section |
| Learn, Statements and existing specialist sections | Navigation placement + preservation inventory | Migrate retained sections; verify all routes and permissions |
| Brand icon | V1 glassy green/blueberry berry restored after user preferred its character at header size | User selection, vector/small-size refinements and final favicon/app assets |

## Editable company identity and People

A company logo can always be uploaded manually or supplied by URL, replaced, or removed. Preserve initials when no usable image exists. Website, LinkedIn, Instagram, X, Facebook and YouTube links are editable; blank means missing, never a guessed account. The preview accepts PNG/JPEG/WebP up to 2 MB, validates image decoding and http(s) URLs, supports Instagram/X handles, and keeps edits in `berry-design-editable-profiles-v1`. Production must use the established entity identity rather than duplicating companies and must not put private analyst edits into public snapshots accidentally.

People belong in a People tab on the individual company dossier. There is no redesigned standalone People directory and no People section on News. Add a person in company context, edit their name, role, affiliation, social/LinkedIn links and notes, and highlight relevant people. Company scope is explicit and independent of the directory's search text. Preserve existing `/people` compatibility while reviewing migration; its omission from top-level navigation does not authorize deleting records or routes.

AI-assisted enrichment is an implementation requirement, not running functionality in this prototype. Suggestions must retain source URLs, collection timestamps and review state. Manual edits win over later automatic suggestions; never silently replace user-added logos or links. Distinguish public profile metadata, historical mentions and reviewed claims. A social account match or executive role suggestion never becomes trusted evidence automatically. No inferred contact handles or current employment from old source mentions.

The People sample contains two historical mentions linked to the June 8, 2026 BluGenix source, explicitly labeled as historical and awaiting review. No social handles or current affiliations were invented. Highlighting is an analyst preference, separate from company favorite/tier/list status and domain trust.

## Reader overlay refinement

The latest direction supersedes the split-pane proposal. Keep the News grid and Map Explorer arrangement stable while a reading surface slides over the right side. Use a clear opaque reading surface, restrained edge/shadow, short reduced-motion-aware entry, a persistent Close control, Escape dismissal, next-story navigation and optional wider reading. Do not darken the whole workspace. Keep selection, filters, scroll and grid column widths on close. A narrow screen can use almost the full viewport while preserving a clear return path. Never make feedback, Save or selection change the trust classification by itself.


## Reader information hierarchy — current refinement

The first overlay still read as continuous body text. The revised hierarchy uses a 28px headline, 20px summary heading, 17px medium-weight summary, 18–19px section titles, 15px statement text, 14px contextual interpretation and 10–11px secondary metadata. On narrow screens, summary body becomes 16px. The intent is distinct information roles, not uniformly small typography.

Summary uses a muted green lead block; interpretation is tucked into a collapsed About this coverage disclosure after the primary information, explicitly labeled as interpretation when expanded; claims use amber with a visible CLAIM badge and attribution caveat. Reviewed statement classifications remain intact. Color is reinforced by headings, labels, border treatment and grouping. Company links become discrete compact cards. Provenance remains quiet but legible. Avoid unnecessary decorative color, blanket bold paragraphs and oversized gaps; the Reader should still feel dense and readable.

Long stored interpretations may split at sentence boundaries into points without paraphrasing, omitting content, or promoting certainty. No automated rewriting of evidence is implied. Apply this hierarchy audit to other pages in the larger mission, especially dossier sections, Learn content, Statements, tables and empty/error states. Verify contrast and typography in both themes, keyboard focus, narrow screens and long real records before production acceptance.


## App-wide content rule: essential information first

Lead every page, panel and card with the answer or development the user came to understand, followed by the few details needed to act. Use plain domain language. Avoid exposing implementation vocabulary such as canonical records, stored interpretation, repository snapshots, pipeline states or internal IDs in ordinary reading flows. Keep precise technical language in specialist operations and audit views where it serves a real user task.

Default secondary explanations, methodology, provenance detail and record references to collapsed disclosures with clear labels. Importance controls prominence: color, size and visible space belong to primary intelligence, not system commentary. Avoid repeating caveats across the page. Keep material uncertainty, claim classification, source/date, stale information affecting decisions and actionable errors visible beside the relevant information; these must not be hidden as cosmetic clutter. Progressive disclosure must preserve keyboard access and all underlying detail.

Reader order: headline/source/date and compact review label; persistent primary action toolbar; Article / Brief switch. Article is the default and contains publisher text. Brief contains the summary, illustration/image, key statements with classification, companies, and collapsed About this coverage and Source details. No interpretation panel interrupts the main reading sequence. The coverage note preserves the original interpretation text without promoting it to a fact. The same information-priority and plain-language audit is required across News, Map Explorer, entity dossiers, Learn, Statements, reports and other retained pages during migration. The prototype change demonstrates the rule; full-app copy and disclosure migration remains implementation work.

Brand direction: user prefers the first, more playful glassy berry icon when seen at actual header size. Restore V1 in the preview and favicon; retain V2 only as an alternate study. Judge future refinements in context rather than treating an enlarged logo study as decisive.


## More menu: grouped and bounded

Organize the 44 secondary navigation links into eight groups: Read & follow; Reports & briefs; Markets & varieties; Directory & settings; Analysis & decisions; Watches & alerts; Review & quality; Sources & collection. Statements belongs under Analysis & decisions. Learn remains top level. Use four balanced desktop columns, two below 1000px, and one below 340px. Distinct heading weight and separators should make group boundaries readable without oversized spacing.

The menu must fit inside the visible viewport on every side, with height derived from the available space below its trigger. Render outside any ancestor whose blur/transform creates a fixed-position containing block. Keep the header/Close control visible while the menu scrolls internally; prevent horizontal overflow. Support Close, outside click, Escape with focus return, keyboard links and resize/reposition. All current links retain their original destinations; regrouping does not remove sections or imply a backend change.


## Primary article actions — preserve access to the article

Reading the original article is a primary action, at the same level as Useful, Not relevant and Save. Never tuck the only original-article link into Source details. In the Reader, use one persistent toolbar with recognizable outlined thumbs-up, thumbs-down, floppy-disk and newspaper icons. The newspaper opens the original source in a new tab. The source URL must remain validated; do not fabricate a destination when absent. Feedback remains available in Unreviewed according to the existing trust workflow; Trusted retains Save and the original link.

Tooltips use plain action descriptions after 2 seconds of continuous mouse hover; keyboard focus reveals them immediately. Every icon has an accessible name independent of the tooltip, a visible focus ring, sufficient click/tap area and a distinguishable selected state where relevant. Save's name reflects its state. Escape dismisses a visible tooltip first; the next Escape can close the Reader. Restore keyboard focus after feedback or Save updates. Tooltips must remain available while hovered and within the reading surface. Hover descriptions supplement icons; they must not be the only accessible labels or block touch activation.

Keep the article, its source/date, summary and images central to the experience. Collapsing implementation notes and provenance detail must not bury the news itself or the action for reading the complete original. Production integration and availability of full article text remain separate from the prototype's summary/sample content.


## Read the article inside the Reader — required core experience

The user explicitly clarified that reading means the original article text inside this app, alongside a separate option to visit the publisher. A summary plus an outbound link does not satisfy the core News Reader requirement.

Article is the default view within the same right-side Reader. Render legitimately available publisher text as readable paragraphs in the application, with source/date and an author when available. Brief is a separate view for the summary, key statements, company connections and collapsed supporting notes. Both share the persistent feedback/save/original toolbar. The newspaper icon opens the publisher separately; do not repurpose it to replace in-app reading. Preserve the selected article, shared filters and reading location through these transitions. Partial text, blocked access and missing text must be accurately distinguished; never present a generated summary as original article text or assert that an extraction is complete solely because it exceeds a length threshold.

Reuse established article acquisition and source-body services in production, including captured paragraph provenance, original URLs, source limitations, retry/error behavior and sanitized rendering. Do not bypass publisher access controls or authentication. Loading text must never publish, confirm, extract trusted statements or change review status. The local design preview now demonstrates native article text fetched on demand for its allowlisted public sample through the existing acquisition service, with memory-only caching. Full production integration, completeness/identity checks, cross-view persistence and rights/access handling remain migration gates.


## Preserve the Market Snapshot workflow

The original Explorer mission includes Explore → Select → Filter → Investigate → Build → Export. The redesigned Explorer must retain Create Market Snapshot, inherit selected countries, berries and the relevant filtered evidence, allow users to include/exclude supported report sections, and retain source links through the existing supported export. Missing coverage must remain explicit. The design prototype's sample map is not a replacement for this implemented workflow. Review the builder in the accepted visual language and inspect a representative exported document before migration sign-off; screen styling and print/PDF styling need separate verification. Do not add unsupported narrative, invent market data, or introduce an unnecessary report backend.


## Map Explorer: annual market statistics

User addition, September 30: populate market statistics at the bottom of Explorer using the best available public sources; Perplexity may help research the initial dataset. Keep the map and news central, followed by a dense, readable statistics section. Country and multi-berry scope applies. Annual statistic periods are independent of News publication-date ranges, trust, and company/list filters, and the interface must say so. Multiple countries remain separate; missing figures are coverage gaps, never zeros.

The design checkpoint includes four sourced 2025 figures for cultivated blueberries in the US (utilized production and harvested area, USDA NASS) and fresh blueberry exports from Peru (volume and value, MIDAGRI). Native units, crop/calendar periods, release dates, source links and limitations are preserved. This small initial sample is not global coverage, a live feed, or a trusted platform publication. Production and exports must never be compared as equivalent market-size measures.

Production acceptance: prioritize FAOSTAT for broad production/area/yield coverage, national statistical/agricultural agencies for authoritative detail and revisions, and existing Trade/Customs providers for trade. Preserve commodity coverage (cultivated/wild; fresh/frozen; combined customs codes), quantity units, currency and FOB/CIF or unknown value basis, reporting geography/partner, observation period, publication/access date, revision/estimate flags and source locator. Normalize units only with explicit recorded conversions. Do not sum mismatched periods, partial coverage, reporting bases or incompatible commodities. HS 081040 and 081020 are mixed commodity families; do not relabel them pure blueberry or raspberry without support. Reuse existing trade_observation and adapters; do not introduce a competing trade schema.

Perplexity, if used, is a research assistant: request original publication URLs, dates, table/page references and units; verify each number against its original source before accepting it into the initial dataset. AI output does not itself establish provenance or grant trusted status. Keep collection bounded, cached and refreshable, with failures, stale periods and missing coverage visible. No Perplexity call or recurring collection was enabled in this checkpoint. Preserve the existing human review/publication gates. Market Snapshot must optionally include selected market figures with period, basis, limitations and citations retained in export.

## Growing regions and operating regions: shared, editable map context

User addition, September 30: every Variety needs a **Growing regions** section that is user-editable and can be populated from linked statements/news. Every Company/Entity needs **Operating regions** with the same editing and source-linking pattern. These are shared profile data used by Map Explorer, not separate copies owned by the map. One record may have multiple regions, activities and dated observations. Edits should carry across profile, map, applicable filters and snapshot views through the existing application services.

Each entry needs a canonical country/geography reference, optional state/province/locality, activity, observed/effective date or explicit unknown, supporting statement/evidence/news links, source date, user notes and edit history. Preserve proposed, historical, active and disputed meanings through existing review/status fields rather than inventing a parallel trust schema. User corrections must remain editable, attributable and protected from silent AI replacement. Removing or superseding a region must retain an audit trail in production.

Variety activities distinguish commercial growing, trials, announced planting and historical growing. A selling country, retailer listing, license territory, patent filing, breeder office or the country mentioned in a story does not establish where a variety is grown. Reuse the existing variety footprint and commercial-observation services while preserving this distinction: countries observed in a market are not growing regions. Company activities distinguish growing, breeding/research, packing/processing, sales/distribution and headquarters. A company headquarters is not its entire operating footprint; a relationship recorded only as operates_in remains activity-unspecified until better evidence is supplied.

Source-assisted entry: a linked statement or news item can fill the source and relevant text and propose a location/activity; preserve classification, ambiguity and contrary evidence. A user reviews/corrects the proposed association. Unreviewed news may appear only as a visibly reported/suggested entry, never auto-confirmed geography. A claim remains a claim. Keep evidence details accessible without burying the place, activity, status and date.

Map layers: News coverage, Variety growing regions, Company operating regions. Use clearly distinct legends and counts; country shading represents recorded presence, not hectares, certainty or market share. Country and berry selections carry across layers. Company favorites/tiers/watch lists apply to the company layer; specify any indirect company-to-variety scope via actual linked roles, not name matches. News date/review filters do not silently remove long-lived region entries. In production offer explicit region status/activity and as-of filters. A country/region opens a readable list with profile and source navigation; support keyboard and touch as well as hover. Mark approximate granularity, overlapping regions and unknown boundaries honestly. Do not place invented farm coordinates or imply a country centroid is an exact site.

Checkpoint implementation: browser-local editor for 64 repository varieties and 102 companies, 11 canonical countries, country shading and source-selection assistance. It reads 45 existing operates_in relationships for 22 companies, preserving notes and source links; no variety growing regions were inferred. Company profiles expose Operating regions; varieties can be selected in the map's region editor and linked to their existing profile. Add/edit/remove and reload persistence work within this browser preview. Full redesigned variety profile placement, durable shared storage, automated suggestions, reconciliation/conflicts, subnational boundaries, snapshot inclusion and production layers remain execution work. Do not alter Variety/Trade backend schemas unless implementation demonstrates a genuine blocker and documents it.

## Section consolidation gate before broad migration

The user requested a thorough section audit before redesigning every page. `APP-SECTION-AUDIT.md` now takes precedence over any assumption that every old navigation label needs its own newly styled page. Keep the accepted UI direction and core workflow prototypes. Review the proposed destination map, preserve distinct state/trust semantics, and prove replacement workflows before retiring duplicate navigation or legacy presentation variants. No production section has been removed or automatically approved for removal.

The audit covers the prior 50 menu entries plus eight additional entry points, all 165 route registrations, and 79 isolated render checks. It found working specialist features missing from the earlier inventory, a mislabeled informational Settings page, overlapping News/Monitor/Reports families, and broken canonical Fact-shaped links. The proposed combinations are decisions for review, not completed migrations.

Explorer region results now use a full-width compact table below the map/news row, with A–Z navigation, text search, Company/Country sorting, source links and editing. The table shows one location entry per row to preserve activity/date/source differences. Table search/alphabet do not alter geographic map scope. Narrow screens scroll inside the table without widening the document.

## Accepted checkpoint and handoff

### Required deliverable: visual product and workflow guide

The user requested an explainer of the site's sections, analyst workflow and reporting capabilities as an outcome of redesign/consolidation. The first audit edition is [workflow-guide.html](../../artifacts/design-sprint/workflow-guide.html), linked from the preview's Mission and audit dialog. It is a review artifact, not an extra production navigation section.

Maintain three explanations: **where to go** (purpose, audience and destination of every section); **how to work** (daily reading, deeper investigation, explicit human review, communication and monitoring); **what to produce** (report inputs, composition, persistence, presentation/export and limitations). Distinguish current capabilities, demonstrated prototype behavior and proposed consolidation. Do not illustrate an automatic article → Fact → Signal ladder or imply every article needs formal analysis.

Every audited section requires the purpose/behavior/proof contract and acceptance record in `APP-SECTION-AUDIT.md`: how it works, what was verified, defects and a reasoned keep/combine/improve/relocate/retire recommendation. Source inspection and successful page rendering do not establish a complete working workflow.

The final guide must match delivered navigation and verified jobs, remain accessible from Help, and include real reporting examples with source/status labels intact. Keep the review edition separate until then. Update guide and audit in the same changes that consolidate a family. Final walkthrough includes reading/saving, company monitoring, variety/region investigation, source/proposition review, Learn detours and a reviewed finding carried through report or brief export.

### Checkpoint boundaries

The user authorized building and pushing a reviewable design checkpoint on September 30. Push the accepted prototype, source assets, this mission, the navigation inventory and design audit on the design branch. Do not merge or deploy the production redesign based on prototype acceptance. Next representative reviews are Learn, Market Snapshot plus export, and a dense Varieties/Statements page including the Growing regions section. Migrate existing page families with preservation checks, real persistence, accessibility and trust boundaries; the local prototype is not production completion.


## Consolidated navigation checkpoint

The preview now demonstrates the agreed workspace hierarchy rather than exposing the legacy 44-link list. Eight More destinations open 20 nested views; Personal Digest absorbs Reading Queue access, Monitor absorbs separate watch/alert entries, Reports & Briefings groups brief creation/library and Meeting Prep, and Operations groups collection/review/quality. Existing tools remain available within their new home. Continue with concrete workflow prototypes and durable integration; do not treat explanatory workspace tabs as completed merged features.

## Mission 1 implementation checkpoint

Personal Digest now has a real private `/digest` workspace and persistent save/reading/list-subscription integration, using the existing analyst stores and shared overlay Reader. `/saved` redirects compatibly; Reading Queue history and specialist actions remain available inside Digest. The isolated review is an application implementation, with sample personal state and labeled illustrative images. It is not a deployment or a claim that other page families have migrated. The preservation map, acceptance evidence and remaining work are in [MISSION-01-PERSONAL-DIGEST.md](MISSION-01-PERSONAL-DIGEST.md). Update the visual guide's status alongside each following family.

**2026-09-30 Mission 2 checkpoint:** The real /news-packets workspace selects dates/review scope, captures fresh public news, previews/validates and generates immutable JSON with Last generated history. /variety-seeds is a compact Varieties subview linked to company dossiers and existing candidate review. Associations are provisional photo inputs, not breeder/owner claims or canonical variety creation. This checkpoint does not deploy the redesign or claim other families migrated. See [MISSION-02-COMPETITOR-NEWS-PACKETS.md](MISSION-02-COMPETITOR-NEWS-PACKETS.md).


**2026-10-01 Mission 6 checkpoint:** Varieties now has a dense Glasshouse directory, alphabet/company-mark/growing-location filters, source-led profiles and compact identity review. Competition and Retail observations retain their existing query scopes; photo associations remain provisional. Growing regions reuse the same editor/history and map annotations. Previous profiles, Compare/Coverage and published static templates remain available. See [MISSION-06-VARIETIES.md](MISSION-06-VARIETIES.md).
