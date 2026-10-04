# Berry Intelligence design study

Accepted direction: refined Glasshouse with the first berry icon. Daylight remains an alternative study. The checkpoint is an interactive prototype, not a production migration. The mission is in `../../docs/v2/IMMERSIVE-DESIGN-MISSION.md`.

Run from the repository root:

```powershell
python scripts/serve_design_studio.py
```

Open `http://127.0.0.1:18322`. Use the A and B buttons to compare directions. The study server exposes only this artifact directory.

The 22-record curated sample comes from published repository evidence at commit `d2d1759`. Three sample records support active canonical facts. It is historical content, not live news. Source dates, summaries, classifications and references are retained. No record has a stored article image. Four generated agricultural illustrations now supply labeled feed thumbnails and Reader images; source image fields remain untouched. See `images/README.md` for asset filenames, generation mode and exact prompts. The sample includes a fictional patent seed record, identified in its stored summary.

Article feedback and article saves exist only in page memory. Reloading resets them. Company favorites and tiers are separate browser-local preferences and survive reload. Source links open the publisher; company and secondary navigation links open the existing local app at port 18321. This study does not modify canonical or runtime data.

## News-first revision

News is now the default destination with a full-width article grid and collapsible Reader. Opening a card shows the Reader; Collapse or Escape restores the grid and returns keyboard focus, filters, selection and grid position. Cards include longer summaries, company links as context, tagged geographic coverage and stored interpretation when available. The map appears only in Explore. Both visual directions use the same News geometry. Every story has a labeled illustrative thumbnail and Reader image, with useful/not-relevant and save controls on Unreviewed cards and in the Reader. News always uses newest publication date first.

Verified the revised News view at 1440, 1050 and 390 pixels with no horizontal overflow. Confirmed images loaded, per-card feedback targets the correct story without changing the selected article, selection mirrors feedback in the Reader, saves mirror in the feed, Trusted hides feedback controls, multi-berry/multi-country scope returns the expected two records, and empty search/reset work. Explore retains the geographic panel. Mobile provides a Collapse control returning to the one-column news grid.

Current screenshots: `news-daylight-desktop.jpg`, `news-glasshouse-desktop.jpg`, `news-glasshouse-mobile.jpg`. Earlier screenshots below are the superseded three-panel study.

## Initial verification

- Viewed Daylight and Glasshouse at 1440 by 900 and saved desktop screenshots.
- Verified no horizontal document overflow at 1440, 1050, 820 and 390 pixels.
- At 1050 pixels in Glasshouse, the top navigation was 63 pixels high and the feed began about 254 pixels from the viewport top.
- Selected blueberry and raspberry together, then China and Peru together; the sample narrowed to two records.
- Verified search with no results, reset, company filtering and its visible clear control.
- Verified selected-story navigation, Reader expansion, mission dialog and Escape dismissal.
- Verified preview usefulness and save controls without sending review or extraction requests.
- Browser error log was empty after the verification sequence.

The browser pass found and fixed a stacking-context problem with the country menu over translucent panels. Full contrast, screen-reader, image-failure, layout persistence and production workflow checks remain part of the implementation acceptance criteria.

Screenshots: `daylight-desktop.jpg`, `glasshouse-desktop.jpg`, `glasshouse-mobile.jpg`.

Map boundaries reuse the app's existing Natural Earth asset. See `../../app/static/COUNTRY-BOUNDARIES.md` for provenance.

## Grid revision verification

Verified three columns at 1440 pixels, two at 1050 and one at 390; opening and collapsing the Reader; Escape and focus return; restored grid position after selecting a lower article; retained multi-berry scope; and a disabled Open Reader control when no results remain. Current grid screenshot: `news-grid-glasshouse-desktop.jpg`.

## Compact News and Map Explorer revision

Compact cards are now the default, with smaller thumbnails and three-line summaries; Detailed cards restores larger imagery. More context expands company/geographic/interpretive detail without opening the Reader. Shared berry, country and trust filters remain visible above both views. Map Explorer presents the map beside either news or the Reader, preserves the selected scope when returning to News, and reports mapped versus geographically untagged records. The Existing Explorer link carries berry/country filters into the original app.

Latest screenshots: `news-compact-desktop.jpg` and `map-explorer-desktop.jpg`.

Verified six complete compact cards at 1440×900 and four at 1050×900, with filters visible. No horizontal page overflow in News or Map Explorer at 1050 or 390 pixels. Checked compact/detailed density switching and expanding card context. Selecting China on the map returned one tagged story; opening its Reader retained the map and review filters, collapsing restored the feed, and returning to News preserved China and the selected story. The existing Explorer link included the selected country.

## Entities / Companies

The Entities tab previews a company directory and dossier using `companies.json`, a presentation-only export of 102 published company entities and their referenced active facts/relationships. It excludes runtime data. Counts describe linked records; country is entity metadata, not operating geography. The export includes repository seed/example entities. The three dossier tabs cover overview, related sample news and explicit connections. Only the first three stored statements appear in Overview; the full existing dossier remains linked.

Company name/alias search, recorded-country, role and berry filters operate in the preview. Related articles open the shared News Reader with a company filter. News counts cover only the curated article sample. `companies-desktop.jpg` captures the proposed Companies layout.

Companies verification: alias search for Fruitist resolved to Agrovision; no-result search displayed its empty state; recorded-country and role filters combined correctly; Connections retained explicit predicates and source links; the Costa article opened the shared News Reader with a company scope chip. No horizontal overflow at 1050 pixels.

## Date scope and refined Glasshouse

News and company-related news always show newest publication dates first. News/Map Explorer share an inclusive date range, with Past 7 days, Past 30 days, Year to date, All dates and custom dates. Defaults to All dates for the historical sample. Verified: 7-day and 30-day windows relative to local September 29, 2026 returned zero; year-to-date returned 22; July 1–31 returned the independently counted 16 records; August 6 only returned one; reversed endpoints produced an error without applying. Map Explorer retained the custom range.

Glasshouse is now the default study direction, with reduced pink, stronger green-gray outlines, restrained shadows and opaque reading surfaces. Targeted WCAG palette calculations are recorded in the mission; this is not a complete accessibility audit. Latest preview: `glasshouse-refined-news.jpg`; date control: `news-date-filter.jpg`.

## Company marks and alphabet navigation

Company rows are now sorted A–Z with initial-letter navigation (All, A–Z, #). Each row and dossier includes independent favorite and tier controls. Tier labels are Tier 1, Tier 2, Tier 3 and Untiered. Shared company filters scope Entities, News and Map Explorer; a linked company must satisfy both active predicates. Cards and Reader company labels reflect the marks. Company marks persist in browser-local storage; public company data and the production app are untouched.

Verified C-only navigation, directory/dossier agreement, favorite+Tier 1 narrowing to the marked company and its linked article/map coverage, persistence after reload, changing the tier without losing the favorite, changing favorite without losing the tier, and zero matches for incompatible filters. Test changes to Costa were restored to its original not-favorite/Untiered state. Screenshot: `companies-alphabet-marks.jpg`.

## Custom company watch lists

Manage lists creates and renames named groups, edits members through company-name/alias search, and archives/restores lists. Lists buttons in company rows/dossiers and Edit lists in the Reader support membership in multiple groups. The shared Watch list filter and list badges carry into Entities, News, Map Explorer and the Reader. Favorite/tier/list predicates must match the same linked company. Lists persist in browser-local `berry-design-company-lists-v1`; no collection or alerts are created, and the original application remains unchanged.

Verification used explicitly labeled Preview test lists: two-company membership yielded two entities, three linked articles and two mapped stories; editing membership in the Reader persisted after reload; a company belonged to two lists; renaming retained IDs/members; case-insensitive duplicate names were rejected. The verification lists are archived after testing and can be restored; no real company watch was inferred. Screenshot `company-watch-lists.jpg` shows the manager during verification.


## Latest review: navigation, profiles and overlay Reader

Learn is top level; Statements and retained specialist sections are under More. The navigation inventory reconciles 50 destinations from current and older navigation, without deleting production routes. People is now a tab inside each selected company's dossier only; no separate People or News directory. Manual company logos and website/social/LinkedIn fields and person details/highlights persist in browser storage; automated enrichment remains a documented future integration.

Reader now overlays the right side while the grid stays fixed. Its default width is 610px (responsive); Expand offers 860px. Close/Escape retains scope and selection. V1 icon is the current user preference after comparing both at header size; V2 is retained as an alternative. Prompts and generation/edit provenance are in `images/brand-icon-manifest.json`.

Verified via UI: unsafe links rejected, manual link saved and persisted across reload, original metadata restored; PNG upload decoded and rendered on the company header; People links edited and restored, highlighted-only filtered correctly, and Add person preselected the current company. Verification values were restored. News grid measured 1219px with three 393px columns both before and after opening the Reader.

Map Explorer verification: map stayed 704px and feed 503px before/after Reader opening. Escape dismissed the overlay. At 390px, company People and News/Reader had no page-wide horizontal overflow. Screenshots: `company-people-tab.jpg` and `reader-overlay-v2.jpg`. Production migration and full accessibility audit remain pending.

Reader hierarchy refinement was checked against `ev-ffp-hortifrut-mbo-2026`, the user screenshot article: 17px summary, 18px Source context heading, two verbatim interpretation points, unchanged CLAIM classification and three company cards. Browser console reported no errors. Screenshot: `reader-hierarchy-v3.jpg`.

Latest refinement: summary now precedes the image; Key statements and company cards remain primary. Interpretation moved below them into collapsed About this coverage. Source details and internal record reference are also collapsed. Claim labels remain visible. Header/favicon restored to V1. This information-first/plain-language rule is recorded as an app-wide migration requirement in the mission.


More menu refinement: all 44 destinations retained exactly once, organized into eight headings across four desktop columns. The menu is positioned outside the blurred header and centered within viewport bounds; its maximum height tracks available space. Close/header stay visible during internal scrolling. Verified at 1440×900, 1050×700, 810×825, 390×844 and 320×568: all menu bounds stayed inside the visible area, no internal horizontal overflow, and narrow views used internal scrolling. Escape returned focus to More; Close reset expanded state; console showed no errors. Screenshot: `more-menu-grouped.jpg`.


Reader article actions: sticky icon toolbar near the headline now places the original article (newspaper) beside Useful (thumbs up), Not relevant (thumbs down) and Save (floppy disk). CSS hover delay is 2 seconds, keyboard descriptions appear immediately, and icons have independent accessible names. Verified the original URL, mutually exclusive feedback states, Save/Unsave label changes, keyboard focus restoration and Escape tooltip dismissal without closing the Reader. Test feedback and save state were restored. Screenshot: `reader-icon-actions.jpg`. Existing menu grouping remains unchanged.


Native article reading: Article is now the default Reader view; Brief contains the summary, illustrative image, key statements, companies and optional notes. The original newspaper link still opens the publisher separately. The local preview server reuses `app.services.article_acquisition.fetch_article` only for the fixed public sample URLs, on demand. Captured article paragraphs are escaped and rendered directly in the Reader. They are cached in server memory only, never added to static JSON or committed artifacts. No private inbox data is exposed and no production collection, publication, or review action runs. Reader failure is visible with an external original link, Brief and retry options. Use the new preview server command above; the simple static server cannot supply article text.

Verification: Costa/BluGenix loaded six publisher-text paragraphs with author Roy G into the native Article view; no summary was substituted for article text. Unavailable-state UI was also observed during network-restricted operation. The preview now runs with publisher access enabled. Unknown article IDs return 404 and cross-site read requests return 403. Screenshot: `reader-native-article.jpg`.


## September 30 checkpoint: market statistics and regions

At the bottom of Map Explorer, Market statistics shows four factual 2025 measures from USDA NASS and Peru MIDAGRI, with source links, period, units and limitations. The initial dataset covers US cultivated blueberries and Peru fresh-blueberry exports only. Country/berry selections apply; news-date, review and company filters do not change annual national figures. Missing coverage is explicit. Sources were checked September 30; this is not a live feed and no Perplexity call was made.

Explorer's Show selector switches among News coverage, Variety growing regions and Company operating regions. Edit regions opens a shared preview editor over 64 varieties, 102 companies and 11 canonical countries. It reads 45 existing operating relationships for 22 companies; there are no inferred variety growing locations. Manual entries, corrections and removals persist in this browser. Linked statements/news can fill supporting text and links for review; choosing a source does not extract or confirm a location. Company Overview includes Operating regions. Growing regions' full redesigned variety-profile placement and production persistence remain mission work.

Verified add → map → reload → edit → remove with a clearly labeled temporary variety trial entry, then removed it. Verified company overlay filtering (China: four recorded companies), source/claim prefill, multi-berry filters, empty country statistics, and annual figures remaining visible with an empty Past 7 days news scope. At 390px, the region editor and statistics had no document horizontal overflow; the dialog fit within the viewport. No browser console errors. Screenshot: `market-statistics-desktop.jpg`.

Five deterministic Reader boundary/cache/failure tests pass (`tests/test_design_studio.py`). Canonical validation passed. The trusted static build produced 1,751 pages, built Pagefind and passed its unpublished-data leakage check. The full deterministic suite is reported in the PR/checkpoint response; do not infer a complete suite pass from these focused checks. No canonical Variety/Trade schema, published records, production navigation or runtime review state changed.

Morning review: open the local preview, then Map Explorer → Show and Edit regions; scroll below the map for Market statistics. Review the mission and audit before implementation. Remaining representative designs are Learn, Market Snapshot plus export, and a dense Varieties/Statements page. Known Reader continuity/image/scope-control issues and shared persistence remain listed in `DESIGN-REVIEW-AUDIT.md`.


## Section audit and dense region table

Map region results now occupy a full-width table below the map/news row, with sticky column headings, A–Z filtering, name/country/activity search, Company/Country ascending sorts, source links and edit actions. The 480px table viewport replaces the 190px stacked-card list; roughly ten compact rows fit rather than two or three cards. One entry per region preserves source/activity/date distinctions. Alphabet/search narrow the table only; map country/berry and company mark/list scope remain shared.

Browser checks: A returned five entries across three companies; Peru search returned three entries; Country sort began with Australian entries; clearing search/alphabet restored all 45 entries. At 390px, the table scrolls internally with no document overflow. Screenshot: `company-region-table-desktop.jpg`. Statement source links now point to supporting Evidence pages, fixing a `/facts/...` route shape that the section audit verified returns 404.

The complete section audit is `docs/v2/APP-SECTION-AUDIT.md`, supported by route and render JSON inventories here. The isolated render audit checked 75 URL variants plus four operator-only rechecks: 72 successful pages, two expected redirects, four expected permission denials, and the canonical Fact-shaped link's 404. No network attempt occurred. Run `python scripts/audit_app_sections.py` to reproduce with a separate empty audit runtime. The script does not exercise approvals, live refresh, user runtime or binary exports.


## Visual product and workflow guide

Open `http://127.0.0.1:18322/workflow-guide.html`, or Mission & audit → Open the visual guide. The audit edition explains nine proposed section families plus cross-app Help/Search, the everyday analyst loop, separate human-review decisions, and six reporting capabilities. Expand section cards for current mechanics, proposed improvements and outstanding proof. Current implementations, browser-local additions and proposed groupings stay distinct. No production navigation or workflow was migrated.

The section audit now includes a required purpose/input/behavior/output/state/proof/gap/disposition/acceptance contract and a 12-family initial behavior ledger. The mission requires this guide to evolve alongside consolidation and match delivered navigation and verified workflows at final handoff. The 58-entry section inventory remains the route-level baseline; full action and end-to-end acceptance is still pending.

Verified this edition at 1440×1000 and 390×844: chapter navigation clears the desktop sticky bar; section disclosure opens/closes by Enter; all six report rows render; the narrow report table scrolls internally with keyboard access and no page overflow. The preview Mission dialog links to the guide. Screenshot: `workflow-guide-desktop.jpg`. These checks verify the guide, not the application workflows it describes.


## Accepted section-review amendments

Personal Digest combines saved stories, Reading Queue and stories from explicitly subscribed lists, with visible origins and no duplicate copies of the same article. Saved/read/priority/completed state and list subscription remain distinct. Landscape gets selectable subjects, geography and sections. Learn defaults to detailed, visual, interactive lessons and research; selection-triggered Perplexity research-to-lesson work is an accepted feature requirement, not implemented by this preview. War Room is renamed Meeting Prep and its existing link moves into Reports & briefs. The guide, audit, navigation inventory and Learn requirements now capture these decisions. Existing `/saved`, `/queues/reading` and `/war-room` routes retain their current behavior. No live research or production-state migration occurred.

Verified the renamed Personal Digest and Meeting Prep links retain their existing route targets; Meeting Prep is in Reports & briefs and all 44 menu destinations remain. The Learn guide card shows the confirmed detailed-lesson-first direction. Screenshot: `section-review-menu.jpg`.


## Consolidated menu correction

More now contains eight consolidated workspaces instead of 44 legacy links. Each opens a local navigation-study page, with 20 nested views in total. Integrated actions are explicitly pending; collapsed existing-tool links preserve access without advertising duplicates as independent sections. Companies is the primary directory label. Normal News/Map/Companies buttons return to the existing preview, preserving its in-memory scope; hidden News shortcuts are disabled while a workspace study is open. Browser hash navigation supports reload/back/forward.

Verification: all eight workspace entries and all 20 nested views rendered with one selected view and no document overflow. Meeting Prep exposes the existing `/war-room` route inside Reports & Briefings. Keyboard view/disclosure activation, Escape menu dismissal, browser Back and News return were checked; the selected berry survived a workspace round trip. At 390×844 the complete menu stayed within the viewport (x=8..367, y=142..633) without page overflow. Scope was restored to All berries. Screenshot: `consolidated-menu.jpg`. JavaScript syntax and whitespace checks passed.


**Mission 26 live workspace evidence:** `company-research-review.png` and `company-research-mobile.png` show actual unreviewed company-detail suggestions from an explicit public-identity research check, with readable sources and no visible provider reference dumps. None of those real suggestions was applied. A separate ignored fixture exercised manual-blank protection, contact acceptance and source history. At 390px, the page/content were both 375px. Raw/private research stays out of this tracked artifact directory. See docs/v2/MISSION-26-COMPANY-DETAIL-SUGGESTIONS.md.

**Report design follow-up:** report-export-refined.pdf and its first-page PNG now show the stronger takeaway, compact scope and numbered finding cards; all five final pages were inspected. report-workspace-refined.png, report-items-refined.png and report-reading-mobile.png show the delivered editor reading order and card contrast. The existing isolated report and analyst prose remain unchanged; this is a design-review sample, not completed intelligence. At a requested 390px viewport the document was 375px without horizontal overflow. See docs/v2/REPORT-READING-DESIGN-FOLLOWUP.md.


**Mission 27 location review:** `region-source-suggestions.png` shows source-bound review cards; `region-source-unsupported.png` and `region-source-mobile.png` show a fictional patent-territory growing claim visibly unsupported. `region-variety-map.png` shows the saved, human-corrected fictional trial in the shared Map table. All locations/passages used for these actions are labeled design fixtures in an ignored, isolated runtime; these images do not establish real growing locations. Desktop and 390px containment and keyboard history were checked. See docs/v2/MISSION-27-SOURCE-LOCATION-SUGGESTIONS.md.


**Mission 28 selected-location snapshot:** `map-locations-snapshot.pdf` and `map-locations-snapshot.png` show the actual compact location export, with named sources and unchanged qualifications; both PDF pages were inspected. `map-locations-snapshot-browser.png` and `map-locations-snapshot-mobile.png` show explicit variety selection, unreviewed status, unknown dates and saved limitations in the delivered composer. All entries/passages are explicitly fictional design fixtures in an ignored isolated runtime, not real geographic evidence. No provider call or canonical/private user data change occurred. See docs/v2/MISSION-28-SELECTED-LOCATION-SNAPSHOTS.md.
