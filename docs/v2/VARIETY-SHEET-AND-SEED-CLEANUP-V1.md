# Variety research sheet and seed cleanup — review candidate

## October 28 intelligence-date sorting

The Recent intelligence heading toggles newest-first and oldest-first. A Sort by menu also restores variety-name order. Sorting uses the recorded date shown in the column; missing or invalid dates stay last in either direction, and equal dates stay alphabetical. Sort choice is retained by the existing private saved filters and alphabetical links. Stable header labels preserve column layout identifiers when sort arrows change. No article, identity or trust state is written by sorting.

Validation: 36 focused navigation/search/saved-state tests pass. Chromium verifies both date directions over the 11 linked raspberry rows, restoration on reopening the directory, filter/A–Z retention, unchanged column identity/width, name-order reset and no page errors. Deployment and merge remain held for user review.

## October 27 interaction and research follow-up

Review correction: the whole table heading layer now sits above frozen body cells, preventing scrolled variety names from covering the name heading. Chromium checks the visible heading and alignment at four vertical/horizontal scroll positions. The directory also offers **Has recent intelligence**, matching rows with an entry in the existing Recent intelligence column, including published and pending items. It combines with other filters, survives reload and is retained by alphabetical navigation; the isolated raspberry check narrows 109 rows to 11. This is presence of linked intelligence, not a new recency cutoff.

Catalog-expansion regressions now distinguish current admitted identities from explicit historical discovery fixtures. Photo permission and GET/no-write assertions remain intact, and current Roberto/Clery/Dickens identity matching is checked separately. Profile-field coverage shares request-local photo validation just as the directory does; its Cornell check now accounts for Dickens alongside the three previously cataloged varieties, without new photo reuse approval.

The earlier presentation-only checkpoint below is superseded for column interaction. Catalog and profile tables now support pointer and keyboard resizing, numeric widths, reordering and hide/show controls. Identity columns remain frozen. Layouts and catalog filters persist per authenticated analyst in private runtime state, with revision conflicts protecting against stale tabs. Profile tables with the same schema share widths across varieties. Reset columns and Reset filters are separate actions. Static/read-only output does not access private saved views.

Catalog keyword search now includes cited source-note conditions, linked source reports and captured passages, with matching excerpts and source links. Geography words in a report do not establish a growing footprint. In-app research uses explicit public web queries or the existing Ask Berry flow; opening the panel performs no provider request. Search results can enter publication review and remain untrusted. Awards, news and patent-news keyword defaults reuse the existing weekly workflow; no unattended job is enabled by this change.

Under the user's explicit selective-admission authorization, 432 source-backed proper-name identities were added as unverified records, with source URLs and admission provenance. The dated audit retains 693 ambiguous or weaker-source cases. These admissions contain no approved traits, aliases, roles or rights. Catalog removal is reversible and retains historical source references. The current catalog contains 494 identities; 463 lack canonical trait rows. This expands identity coverage while increasing the visible profile-enrichment backlog. The admission manifest records the bounded source snapshot; it is not a fresh verification of every breeder website.

Directory photo validation now reuses request-local source context instead of revalidating the same source for every variety. Identity and permission checks remain in place. Deployment and merge remain held for user review.

Follow-up validation: 70 targeted workflow, identity, source-photo, keyword/default and saved-state tests pass. Authenticated Chromium verifies pointer resize and reload persistence, hide/show, reorder, keyboard resize, shared profile widths and 390px containment, with no page errors. Fresh keyword checks return Netherlands 4, hydroponics 4, Mediterranean 7, trial 37 and Europe 6, with matching source citations. Research-panel presets and the attributed Twilight award reference render correctly. Replaying the stored live Rafiki search retains the breeder page and two patent-reference pages and suppresses seven unrelated results without another provider call. The expanded-catalog isolated static build emits 2,216 pages plus Pagefind and excludes private source/activity panels and saved-state access. These checks are local verification, not deployment or independent completeness scoring.

The user requested removal of example/test varieties and adoption of the recent Workspaces/Pages and collection-settings sheet design across the variety workspace. Merge and deployment remain on hold.

## Live catalog cleanup

The audited live variety catalog contained two explicitly fictional records, Example Blue and Example Red. Both are removed, together with their connected fictional companies (Example Genetics and Example Nursery Partners), retailer (Example Fresh Market) and three sample Evidence records. The eight records now live only under `tests/fixtures/legacy_seed/`; legacy tests explicitly opt into a separate temporary catalog. They are not installed during ordinary application startup or globally injected into the test suite. A Reader performance test now uses an existing real publication.

Removed sample Evidence pointers from Europe, North America and the premium-flavor strategic question, preserving those real geography/question records and their other references. Removed the two demo entries from the source-notes import; its 138 cited rows now cover 31 real profiles. Defensive seed-ID exclusions in exports/landscape remain in place. No real variety or real source was deleted, and no source claim was promoted to a Fact.

At the earlier cleanup checkpoint, the checkout and isolated preview contained 62 real variety profiles: 40 blueberry, 11 raspberry, six strawberry and five blackberry. Published source-record count is 1,269 after removing three fictional records. Historical audit figures of 64 varieties, 33 trait gaps and 1,272 source records describe the pre-cleanup snapshot. Canonical trait gaps at that checkpoint were 31; this is removal of two demos, not review approval of the remaining source notes. The isolated preview retains a private backup of its removed samples. Production runtime data was not edited by this task; an existing persistent production store needs the same reviewed cleanup during a later approved release.

## Sheet presentation

`variety_sheet.css` supplies one scoped research-sheet treatment for variety directory/specialist views, profiles, compare, coverage, identity review, photo imports/editing and variety growing-region pages. It uses the Workspaces/Pages evergreen header, fine grid lines, compact typography, restrained controls, alternating rows and white panels. Company and other workspaces do not inherit these styles.

The catalog has eight explicit columns: row, variety/name, berry, company roles, rights/IP, observations, growing locations and recent intelligence. Names and berry labels are no longer blended in one cell. Row and variety columns remain visible during horizontal scrolling. The existing server-side alphabetical links become a floating right-hand rail on desktop and a horizontal bottom rail on narrow screens. At the initial presentation checkpoint, filters and existing actions retained their behavior without column interaction. The October 27 follow-up above adds column editing; sorting remains alphabetical.

Profile section links now precede long source details and stay below the actual shell header while scrolling. A small shared script measures shell/tab heights for anchors and sticky positioning, including wrapped mobile headers. Source notes keep citations, limitations and pending-review labels. They remain excluded from static/read-only profiles. The shared breadcrumbs remain intact.

## Validation

150 existing/targeted catalog, app, source-note and Reader checks pass; 107 existing variety, photo, navigation, company and static regression checks pass. New cleanup regressions verify absence of seed records and dangling references, 404s for the removed profiles, no legacy search result and successful access to a real profile. Canonical record validation and diff checks pass.

Authenticated Chromium checks exercised 13 variety/company routes and parent links, verified all 62 real catalog rows, eight headers, fixed A–Z navigation and a working B filter. Both removed profile URLs return 404. Desktop and 390px mobile screenshots were inspected; no page errors, document overflow or breadcrumb overflow were found. Screenshots and runtime receipts stay private under `inbox/search-quality-evaluation/variety-sheet/`.

Fresh isolated static build: 1,784 pages plus Pagefind, with no removed sample IDs in any emitted HTML. Final browser checks also verify the name column stays fixed during horizontal scrolling, Compare is visually separated from the name, section-link selection follows the URL hash, and a clicked section clears the sticky header. JavaScript syntax validation passes. This is local validation, not deployment.
