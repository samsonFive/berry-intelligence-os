# Collection settings — review checkpoint

`/settings/collection` provides a shared, authenticated collection editor. It is reachable from More → Collection settings, Reader settings, and Source Health. The page reads the current runtime registry and effective discovery configuration, rather than a hardcoded list of publishers.

Users can find, add, edit, pause, remove, and restore article sources, discovery expressions, and specialist feeds. It displays full expressions/URLs, source priority and cadence preferences, and the configured pipeline schedule. Manual references remain visibly different from discoverable feeds. Enabled configuration is not a claim that a provider is keyed, a scheduler succeeded, or coverage is complete. Cached editions remain available until refreshed; saving does not issue provider requests or start collection.

Source edits update the existing Source repository consumed by collectors. Adapter options, taxonomy links, source IDs and recorded check metadata survive edits. Multiple feed URLs are supported. New RSS and keyword monitors use the existing article/news discovery adapters and the reference registry type so the legacy headline-only poller cannot publish their results directly. Existing sources retain their adapter identity. Removal disables the record and retains it for restoration; previously collected articles and review history are untouched.

Discovery overrides and the last 200 change events live in the persistent, gitignored `inbox/operations/collection_settings.json`. Defaults remain code-owned and removals are reversible tombstones. The actual News, Industry discovery, weekly discovery, Radar, Exa and background CatchAll generators read overrides on every call. Specialist feed query construction and fetch resolution use the same effective feed catalog. New custom entries are limited to 30. Existing date-window constraints remain in force after wording changes. Ad hoc analyst research questions and non-article pipelines (social, trade, weather, patents, etc.) are outside this editor.

Writes require authoring mode and a session-bound, expiring signed form token. The existing shared collection lease serializes this editor with collector runs and other editor submissions. A revision fingerprint rejects stale forms; private settings writes and Source repository snapshots use atomic replacement. Invalid URLs, malformed settings, missing entries, and active collection produce errors rather than silently overwriting configuration. Public static output does not render the editor or copy its private overrides. Existing shared analyst authorization applies: there is no separate viewer/editor role in the current account model.

Source cadence is the existing `update_cadence` preference. This UI does not change the scheduler cadence policy, enable disabled pipelines, install credentials, or turn on provider subscriptions. Pipeline configuration is shown read-only with links to execution health.

## Validation

- 155 offline regression tests passed across the editor, discovery providers, weekly discovery, Radar, CatchAll, specialist feeds, and Source repository.
- A second focused run passed 117 tests covering source collection eligibility, Source persistence, News, and topic search/report regressions.
- Record validation and whitespace checks passed. Static pages rendered and the unpublished-draft leak check passed. Pagefind initially failed with a Windows sandbox permission error; retrying only the index step outside that sandbox succeeded (1,793 indexed pages). A subsequent output check found no private preview fixtures or collection editor page.
- An authenticated loopback preview uses an isolated copy of configuration. Browser checks exercised search/filtering, term add/edit/remove/restore, and source add/edit/remove. No live production configuration was edited and no provider searches were issued for these UI checks.

## Review walkthrough

Open `/settings/collection` and choose Sources, Discovery terms, Specialist feeds or Schedule. Each collection sheet sorts names alphabetically and keeps column headers visible while scrolling. Search by name, publisher, URL or expression. The floating A–Z rail jumps to the first matching row; unavailable letters disable after filtering. On narrow screens it becomes a horizontal floating dock.

Open a name or Edit to inspect the full entry in the side editor. Add a monitor, change its wording, uncheck Enabled to pause it, or choose Remove → Confirm removal. Enable Show removed to restore entries. Escape or Cancel closes the editor without saving. Arrow keys switch tabs. Source Health and Collection activity distinguish configuration from execution. Changes apply to the shared site.

The October 27 visual revision follows the recent Workspaces / Pages research-sheet design: evergreen headers, compact fixed columns, alternating rows, blue selection, and amber paused states. Existing 14 collection-settings regressions passed; browser checks verified alphabet jumping, filtered letter availability, tabs, side-editor save/return state, and the narrow-screen dock. No backend collection behavior changed in this revision.

Deployment remains stopped for user review. The earlier search-quality acceptance gaps in `SEARCH-RESEARCH-QUALITY-V1.md` remain open.

## Remaining operational debt

Older `/sources` mutations and the optional legacy polling loop predate the shared editor lease and can still perform stale whole-registry writes. The new editor avoids stale forms and coordinates with the modern collector; a complete migration of legacy mutation paths to one transaction service remains separate work (TD-COLLECTION-UI-001). Keep the legacy poller off, as in the existing production default, and use this editor for configuration changes. Per-account collection-editor permissions are not implemented (TD-COLLECTION-UI-002); every authenticated analyst in authoring mode shares these controls under the current account model.

## Guided discovery terms — October 27

Add terms now separates the display name, collection destination, topic input, Berry and Region. For the review example, enter Floricane as the topic, choose Blackberry and Global, and use News feed / Google News. The expression is `(Floricane) AND (blackberry OR blackberries OR zarzamora)`. Unlike the older broad blackberry defaults, an explicit Blackberry choice omits generic caneberry because that also describes raspberry. This example was saved only in the isolated local preview.

Simple mode accepts up to 20 comma-separated or newline-separated terms, deduplicates them, quotes multiword phrases, and lets the analyst choose Any (OR) or All (AND). These are alternatives/requirements inside one named monitor, not a bulk create operation. Advanced mode preserves the analyst's topic expression and still adds the selected scopes; provider operator semantics can differ. Region adds the existing place-name clause and search-edition metadata, rather than claiming verified article location. Global has no place restriction. Scope selections are persisted and consumed by actual discovery query generators, including the existing workflow date windows. The preview and save paths use one compiler; preview performs no provider requests or writes.

Each destination explains where and when the monitor is consumed. Optional providers retain their existing credential/routing requirements. Arbitrary new terms cannot enter the official-publisher lane. Existing default and legacy raw expressions remain editable as full expressions; newly guided custom monitors reopen with their original input and scopes, avoiding repeated expansion. The existing CSRF, authoring, conflict, limit and review controls still apply.

Validation: 85 tests passed across collection settings, Industry discovery, Radar and Weekly edition, including compiler validation, multiple terms, persisted scope dispatch, preview/save equivalence, and preview access controls. Script syntax and whitespace checks passed. Authenticated browser checks saved and reopened Floricane / Blackberry, verified its separate scope columns and Berry filtering, and left the new form available for review. No provider search was initiated from the form; no production collection settings, merge or deployment changed.


## Monitor names and separate dimensions — October 27

Technical query prefixes no longer determine the displayed name or alphabet index. Names describe subjects such as Production expansion or Cultivar traits. Berry, Region, Workflow, Provider and Language are separate discovery-sheet columns. Berry and Region also appear for sources/feeds. The name column stays visible during horizontal scrolling. Column filters combine with text search and the A–Z jump rail.

APAC is Asia-Pacific (region); Lang identifies regional-language queries; Pulse maps to Industry discovery; Radar maps to Emerging developments; Today maps to News. Exa is a web/semantic discovery provider. CatchAll identifies the NewsCatcher service used by Background recall. The page explains these terms in What do these columns mean? Language is query/search-edition language, not a guarantee about the returned articles. Optional providers remain contingent on routing and credentials.

Displayed berry tags use stored crop scope or literal crop terms, including the existing multilingual query words. Unspecified crops stay visibly Not specified. The view records each default query's consuming workflows, so shared Industry discovery / Weekly edition searches remain one editable monitor. Stable IDs, expressions, provider routing and saved analyst names are preserved. Earlier automatically generated technical labels are upgraded for display without rewriting runtime settings. Custom labels remain untouched.

Validation: 16 collection-settings tests passed, including dimension accuracy, shared workflow membership, preservation of literal search behavior and analyst names. Script syntax and whitespace checks passed. Browser checks exercised combined Berry/Region filters, Provider/Workflow filters, and the subject-based alphabet rail. This is a presentation change; it does not complete the broader search acceptance work or authorize deployment.

## Keyword Monitoring name and source-menu entry

The user-facing discovery sheet is now Keyword Monitoring; stable query IDs and the terms anchor remain unchanged. Add source / Google News search terms opens the guided keyword-monitor form and carries over the entered display name. The incomplete duplicate raw-expression creation form is hidden for that selection. New entries use the selected discovery workflow, not a new source-registry record. Existing keyword source records remain editable through Sources with their existing collection adapters; they are not migrated or duplicated. RSS / Atom and manual-reference creation remain available in Add source.

Validation: the 19 collection-settings tests passed after the rename. Browser verification exercised Add source, keyword selection, guidance, and transition to Add keyword monitor with the entered name retained. Earlier scoped dispatch, multi-term and preview/save tests remain covered by this suite. Provider live search/result quality and scheduling changes are outside this form check. Deployment remains held for review.

Historical backfill follow-up (October 27): saved scoped monitors now offer an explicit dated backfill into the existing untrusted publication inbox, with provider choice, bounds, background status and review links. The live Floricane/Blackberry test collected six older articles including both Ervin primary pages. All three archive-only regression wordings then found and cited the saved sources with zero web calls. See KEYWORD-MONITOR-BACKFILL-V1.md for the trust boundary, live evidence, validation and limitations. Deployment remains held.
