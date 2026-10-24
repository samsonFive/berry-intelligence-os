# Analyst living workspaces

Private authoring implementation; production deployment and merge are not authorized.

## Review entry points

- `/workspaces`: pages, nested pages, capture inbox and document search.
- `/workspaces/<page-id>`: portable block editor, incoming feed and page map.
- `/workspaces/evidence/<evidence-id>`: preserved wording, exact captured passage,
  attribution, archived article version and interpretation history.
- Existing article readers expose **Save full article to workspace**. Selecting
  text exposes Quick save, Capture fact, Link relationship, Add note, destination
  choice and Open workspace. Existing Research/Learn remains available.
- Company/entity dossiers and Landscape link to private workspace material.

The editor uses native, accessible form controls and stable JSON blocks rather
than adding a third-party rich-text editor. This fits the existing server-rendered
stack without a new JS build/dependency/license surface. Block movement is by
keyboard-accessible up/down controls. Paragraph, heading, list, checklist,
callout, evidence, statement, note, hypothesis, article, table, entity/page link,
feed, map and cited briefing representations remain portable.

## Data and trust

`inbox/living_workspaces/workspace.sqlite3` is a private runtime database;
`PRAGMA user_version=1` is created lazily. No canonical seed migration is needed.
Objects, append-only revision history, idempotency receipts and an evidence
projection outbox share SQLite transactions. Stale page/item writes return 409.
Atomic evidence-file creation never replaces a file already changed by review.
Pending outbox operations recover on the next workspace request.

Every capture and nonempty authored note/hypothesis enters the existing
`inbox/evidence/` review path immediately, with `status=in_review` and
`verification_state=unverified`. `workspace_capture.nature` separates source
material, source statement, analyst note and analyst hypothesis. Publication
review preserves this metadata; saving or publication review does not create a
trusted Relationship, Fact, Signal or Assessment. A revised interpretation gets
its own unverified review identity; prior review is not silently transferred.

Sources are immutable content-addressed snapshots. Exact wording, position,
prefix/suffix, article identity, URL, publisher, publication date and capture time
remain distinct from editable interpretation. A mismatched/repeated quote with
no valid position is explicitly unresolved; it never jumps to the first match.
Multiple placements share an evidence item. Removing/undoing a placement leaves
that item and its other references intact. Existing evidence review remains the
door for knowledge-record deletion/publication decisions.

The existing app authoring gate, same-origin mutation checks and session login
apply. Read-only mode rejects these routes. No sharing route is added. Native
account semantics remain a shared analyst workspace, not per-page ownership.
Only escaped text is rendered from source bodies; publisher HTML/iframes never
execute. Available, partial, excerpt-only and unavailable states follow existing
reader acquisition metadata. Saving never triggers an LLM or new acquisition.

## Feeds, relationships and synthesis

Feed configurations explicitly store OR/AND across active facets, with OR within
each facet. Entities, berries, technologies, topics, geographies, sources,
languages and keywords are configurable. Matching reads existing ingested
records; no page scheduler, duplicate fetching or paid background research is
created. Open pages check every 30 seconds and announce changed coverage without
rewriting the document. Manual refresh, pause, last successful check and failures
are visible. Published dates remain distinct from discovery dates. Feature is
an explicit capture; dismissal is only a page preference.

Relationships reuse the current predicate enum, canonical entity IDs and
explicit From → To direction. Nature, verification, program scope, source
passage, notes, additional supporting capture IDs and history stay separate.
Co-mentions create no edge. Hypotheses are dashed and explicitly speculative;
source statements retain an unverified label. The graph has a legend, search,
type/status filters, dossier links and an interactive table equivalent. Expanding
into related workspace/canonical knowledge is explicit and labels outside-page
material. Withdrawal and revisions preserve history.

Generation uses selected blocks or the curated page. Unfeatured incoming cards
are excluded. The default is a deterministic cited digest, which works without
credentials. Optional model synthesis uses the existing untrusted JSON gateway;
the UI explicitly states which selected material goes to the configured provider.
Every returned sentence needs citations to selected items; invalid/out-of-scope
citations are dropped. All model prose remains generated interpretation, with
speculation labeled, alongside the original grounded digest. Model failures keep
the digest. Generation does not hold the capture database lock. A new block
stores source versions, selected block snapshots, page revision and generation
metadata; previous edited drafts are preserved. Referenced-item changes are
indicated. Markdown export retains the bibliography and passage URLs; JSON export
includes blocks, items and archived source versions.

## Local real-source preview

Run in the repository Python environment:

```powershell
python scripts/preview_living_workspaces.py --research-inbox ../berry-intelligence-os-gene-editing/inbox
```

Preview: `http://127.0.0.1:18773/workspaces/wp-gene-preview`.
The process binds loopback, requires the existing session login, disables source
polling and writes only `inbox/living-preview-v2/`. Local preview sign-in
instructions are in that ignored directory's `preview-access.txt`; these are
isolated review credentials, not production credentials.

The setup reuses previously acquired original publisher text and existing
gene-editing identities/drafts. It never reruns paid research. Pairwise/HRB's
May 26, 2026 licensing release is embedded in full. Simplot's October 28, 2021
alliance announcement and Ohalo's March 10, 2025 consortium announcement provide
additional attributed statements. A comparison table, company link, nested page,
configured feed, supported licensing claim and cited draft are included. The
separate, clearly labeled demonstration hypothesis is a synthetic analyst
question confined to this preview. It asserts no real new partnership.

Walkthrough: expand the article; highlight a passage; Quick save; reload and
open its evidence link; inspect the preserved marked passage and existing
review link. Change a statement/add a note without modifying the quote. Inspect
the map and hypothesis filter. Edit/reorder blocks and nest a page. Feature or
dismiss incoming coverage. Select blocks and generate a new cited draft; export
it with its sources. Capture undo removes only its placement.

## Validation and remaining limitations

- 74 targeted tests passed across workspace persistence/retries/concurrency,
  citation scope, model failure, page-authored notes, source review metadata,
  existing readers, Digest, remote auth and duplicate/portable publication review.
- `scripts/validate_records.py` passed. The static build generated 1,794 pages
  and verified no unpublished draft IDs/titles leaked. JS syntax and diff checks
  passed. GitHub checks must be assessed on the final PR head before merge.
- Browser verification exercised mouse selection/one-click capture in the real
  embedded article, reload persistence, keyboard citation activation and exact
  source-passage highlighting. A 390px layout had no horizontal overflow; the
  hypothesis filter removed the speculative edge from the table. Live-feed
  matching arrivals/nonmatches are covered
  by integration tests. Physical touch hardware and a production ingestion run
  were not exercised. No live model call was made; model tests use fixtures.
- The editor is a native block/form editor, not a full Notion rich-text clone:
  no collaborative cursor, slash-command rich-text menus or drag gestures.
- Topic/technology identities absent from the canonical registry may be saved as
  explicitly unresolved private stubs. These never auto-merge. Feed configuration
  currently uses taxonomy IDs/keywords with visible match explanations.
- Living-document exports are Markdown and portable JSON. Existing report PDF
  workflows remain available separately; this document format has no direct
  PDF/DOCX renderer. Existing source acquisition limits still apply.
- Page blocks and source snapshots are separate from existing published-record
  storage. Back up both the SQLite database and `inbox/evidence/`; private
  runtime must remain on persistent mounts. Browser recovery drafts assist failed
  page saves but are not the durable store. Existing account scope is shared.
- The separate eleven-company gene-editing research mission remains incomplete
  as documented in `GENE-EDITING-LANDSCAPE.md`. This demonstration does not
  establish editing programs, commercial availability or research completeness
  for all watchlist companies.

## Persistence / rollback

Keep the existing data/inbox runtime mounts. On first use the database and tables
are created without modifying trusted files. Back up the database with SQLite's
backup API or with the app stopped, and retain the evidence directory. To roll
back the feature, revert the code while retaining these private runtime files;
do not delete captured knowledge or replace a production inbox with preview data.
Public static export never enumerates the workspace database or routes.


## Page overview follow-up

Every page now has keyboard-accessible **AI summary** and **Contents & excerpts**
tabs. The contents table follows the current block order, shows section names,
source/analyst labels and short excerpts, and links directly to stable block IDs.
Jump links focus the destination and work after reload. The summary is generated
manually through the existing configured-model option, with a clearly labeled
compact evidence digest when AI is unavailable or deselected. It uses captured
statements, passages and notes. With the AI option selected, saved article blocks
also contribute their complete stored text, source URL, immutable source version
and availability label to Perplexity at `https://api.perplexity.ai`. URLs provide
attribution; the model does not refetch them. Unfeatured sources and incoming
feed cards are excluded. Custom endpoints cannot receive full-article summaries.
This full-article destination was explicitly authorized by the operator.
Last-generated time is stored separately from the last page-material update.
Changed curated blocks or linked item revisions mark the summary out of date;
feed arrivals do not regenerate it. Generating the overview leaves curated blocks
untouched, preserves history and supports retry/stale-version checks. Overview
text and citation references are included in Markdown/JSON export.


## Compact research grid

Pages default to a compact sheet with numbered rows, briefing selection,
block type, two-line information excerpts, review state, linked source and
updated date. Expand a row for the existing full source/editor controls;
Document view preserves the full document layout. View choice is saved with the app account. A row filter searches the curated page without changing its order or
saved content. Contents/citation jumps reveal the matching row and clear filters.
The overview can collapse while retaining its summary/contents tabs.

Validation: 75 targeted regression tests passed; browser checks covered filtering,
row expansion, selection, document/grid switching and source jump links. A live
Perplexity probe returned HTTP 401 with `insufficient_quota` in the local environment;
the loaded key matches the operator keys file, but the API project needs credits. The preview retains a clearly labeled evidence digest and an actionable quota notice. Deterministic
provider fixtures verify saved article text, source links, citation scope and the
approved destination restriction without making CI depend on live credentials.


## Reader-focused intelligence brief

AI page overviews use an editorial structure: The picture, Key developments,
Why it matters, What to watch, and substantive analyst questions when present.
Paragraphs retain scoped source citations. A single review notice replaces
repeated generated/unverified prefixes; full review metadata stays in expanded
source rows. The supporting deterministic digest remains stored as provenance
rather than being appended as a second summary. Fallbacks remain explicitly
labeled and source trust gates are unchanged.

The prompt includes publication dates, distinguishes announcements from outcomes,
keeps hybrid breeding distinct from gene editing, and restricts implications to
the supplied material. Model fluency is not evidence of factual correctness;
human review remains required. The grid foregrounds companies and developments
rather than internal block types and review-state strings. The overview opens
by default and uses a compact two-column reading layout on larger screens.

Local workspace regressions: 18 passed. The live preview was regenerated and read
for usefulness and unsupported inference; operator API credits now permit live
completion. Prior quota failures remain in revision history.


## Dense document cards

Document view uses an ordered, responsive card grid: company/section headings,
compact findings, smaller source attribution, and expandable source passages,
article text, evidence actions and page notes. Saved briefing bodies are folded
behind a short preview. Comparison tables and relationship maps receive wider
cards. Card row spans are measured with ResizeObserver so shorter cards do not
leave full-row gaps; the observer is disconnected on rerender/view switch.

Placement removal is an accessible × icon with hover/focus label. Reordering
controls appear on card hover or keyboard focus and remain visible on touch
screens. The underlying block order, item references, source text, review gates
and autosave behavior are unchanged.


## Highlight shortcuts and complete findings

The selected-text capture menu shows keyboard hints: L Research & Learn,
S Quick save, F Capture fact, R Link relationship, N Add note, V Variety workspace,
D Choose destination, O Open workspace and Escape Close. Recent visited/saved
workspaces appear as three quick-save destinations on 1–3. Successful-save actions
also expose O/D/U/Escape for open/change/undo/close. Shortcuts are scoped to the
visible capture panel; typing fields, modifier combinations, IME composition,
repeat events and active saves are excluded. Recent page IDs stay browser-local;
workspace pages and captures retain normal durable storage and review gates.

V reuses or creates the singular Variety workspace and saves the preserved
selection there as source material, without promoting it to a trusted variety
record or inventing an entity identity. Existing provenance/retry behavior is
retained. The preview contains the dedicated workspace; its keyboard test
placement was undone after verification.

Grid findings expose a full-text hover/focus preview and click/Enter/Space inline
expansion. Expanded cards show the original selected quote immediately when no
separate statement exists. Preview content is plain text, scrollable and
Escape-dismissible. No source text is truncated in stored records.

Validation: 38 capture/workspace, reader and authentication regressions passed;
JavaScript syntax and diff checks passed. Browser checks confirmed full finding
focus/click, recent destination hints and V saving the highlighted text to the
Variety workspace, followed by undo of the test placement.


## Source-date chronology

The grid displays source publication date rather than capture/update date. It
sorts newest source first by default, supports oldest first, and uses most recent
item update as a secondary sort for equal source dates. Undated source/page
material sorts last in either direction. From/To date filters are inclusive and
exclude undated rows when a range is active; Clear dates restores them. Text and
date filters combine. Source/citation jumps clear filters to reveal their target.
The sorting direction is saved with the app account and does not reorder the underlying
curated document blocks. Update timestamps remain available in date-cell tooltips.

Browser validation used archived 2021, 2025 and 2026 publications: ascending and
descending chronology and a 2025-only date range passed. A shortcut typed into an
analyst note stayed text rather than saving; test input was discarded.


## Remembered layouts and berry destinations

Document is now labeled Cards (the previous stored view choice remains compatible).
Grid column borders support pointer/touch dragging and keyboard resizing: Left/
Right adjust 10px; Shift adjusts 50px. Widths, column order, selected view, source ordering and
Cards-per-row preference are stored in the app for the signed-in account, across
workspaces, reloads and devices connected to the same app deployment. Cards may use fewer columns on a narrow window, retaining the preferred
count for larger windows. Reset layout restores default widths and automatic
card count. These preferences follow the signed-in app account; browser values are only an initial migration source.

Four empty, private default berry workspaces are created idempotently in runtime
storage with stable identities. Existing content/revisions are never overwritten.
The highlight menu always shows Blueberry B, Blackberry L, Raspberry R and
Strawberry S before other actions and recent destinations. These keys save the
preserved selection directly to the corresponding workspace as unverified source
material. Research & Learn moves to A, Quick save to Q, and Link relationship to
K to avoid key conflicts; F/N/V/D/O and numbered recent destinations are retained.

Validation: 39 workspace/reader/auth tests passed, including durable berry defaults
and captures across reopen. Browser checks verified pointer and keyboard column
resizing, width persistence after reload, remembered Cards selection/column count,
all four fixed berry shortcut labels, and R saving into Raspberry workspace. The
preview test placement was undone after verifying its destination. No trusted
berry or variety schemas or facts were created by these defaults.


## Account layout persistence and column reordering

Authenticated GET/PUT `/api/workspaces/preferences/layout` stores layout values
under the current app account identity in the private SQLite store. The request
cannot choose another account. Saved settings include view, widths keyed by
stable column identity, a permutation of column IDs, card count and source sort.
A new device reads app settings before rendering; legacy browser values import
only when the account has no saved settings. Default layouts use null widths.

Revision checks reject simultaneous stale-device writes; idempotency receipts
make retry after an uncertain response safe. Saves are serialized and survive
navigation via keepalive requests. Failure/retry status is visible. A stale
layout asks the user to reload rather than overwriting another device silently.
Preferences are excluded from generic workspace history access and public output.

Drag a column heading to reorder, or use Alt + Left/Right while its heading is
focused. Border dragging and keyboard width adjustment remain separate. Widths
stay associated with column identity when moved. Reordering keeps source dates,
selection and expansion attached to the correct cells. Reset restores default
order/widths/card count in the account.

Validation: independent API clients read the same saved account layout; other
accounts cannot retrieve it or reuse its retry receipt. Stale writes, malformed
orders/widths and cross-origin mutations are rejected. Browser checks confirmed
keyboard and pointer column moves, resizing after moving, and restored order and
width after reload. Physical second-device access was not exercised.


## Reading view and final device-recall checks

The row-number/# column is hidden from the grid. Stable block IDs remain internal
for links, expansion, capture and history; persisted column IDs stay compatible
with prior layouts. Normal reading also hides selection checkboxes. Select for
briefing explicitly enables them in Grid/Cards and explains their purpose: choose
material for Generate cited draft; no selection means the whole curated page.
Cancel selection clears the selection, and switching pages clears it as well.

The account-layout regression now writes Grid/view, custom column order and
widths from one independent client, updates them from a second, and verifies the
result from the first client, a fresh third client and a reopened SQLite store.
It also verifies account isolation, retry receipts, stale-write protection and
rejection of invalid layouts. Browser verification uses separate storage origins
(127.0.0.1 and localhost), separate signed-in sessions and the same application
account/backend to check that layout recall does not depend on browser storage.

Incoming coverage reuses `_news_cards.html`, the News metadata presenter and
News card styles, with the existing pop-out Reader (Article/Brief, source links,
reading controls, previous/next and close-to-return). Feature article, Annotate
and Dismiss on this page stay attached to each card. Refreshed cards announce the
shared intelligence update event; reader binding is idempotent and resolves the
current card position after updates. The feed remains private, metadata-only and
outside synthesis until featured. Publisher access limitations use the existing
Reader fallback rather than a different workspace reading flow.

Shared-card follow-up validation: 40 workspace/reader/auth tests passed, including
reader links, save controls, workspace actions and escaped publisher metadata.
Browser checks covered open, next story, saved article text, access fallback and
close-to-return. JavaScript syntax and diff checks passed.

Connections filters use a compact wrapping toolbar: entity search, review state,
entity type, hypotheses and related knowledge. The entity card now lists the
workspace’s configured entity/crop/technology/topic/geography feed scope and
existing page entity links. Add uses known entity suggestions and saves to the
appropriate feed facet; remove clears that entity from tracking facets and page
entity links without editing captured evidence, relationships or trust. Feed
pause and ANY/ALL matching remain unchanged. Entity notes are collapsed when
empty. Grid findings also list the tracked entities.

Browser verified entity add, save, reload and remove; the original preview scope
was restored and persisted. Twenty workspace regressions and JS syntax passed.

## Linked Landscapes and long-page navigation

Pages retain up to eight Landscape IDs in the private SQLite record. Link from
either the workspace or a saved Landscape view; the opposite surface derives
its backlink from that same record. The gene-editing research lens is a built-in
choice and uses its complete adjacent-inclusive roster. Saved overview and
Explorer selections keep their stored selectors. Unlinking removes the shared
association without editing either surface’s canonical evidence or claims.
Landscape pages expose linked workspace notes, saved-capture counts and the
current combined brief as explicitly labeled analyst research.

Overview generation resolves current Landscape programs, company scope, source
references, review states and gaps alongside curated workspace evidence. Each
Landscape has a distinct citation with an internal jump to its view. Its material
fingerprint participates in summary freshness; an archived/unavailable view
shows an error and blocks regeneration until repaired. A generated combined
brief must cite page evidence and every linked Landscape, and stays subject to
the compact reading limit. Shared underlying sources are not independent
corroboration. Generated prose remains review-required. The operator explicitly
approved sending saved article text, notes and linked Landscape context to
api.perplexity.ai; a live combined generation succeeded in the isolated preview.

The preview’s original seed had four tracked companies and an invalid legacy
Ohalo ID. A one-time migration now restores the eleven canonical roster IDs,
links the breeding lens and copies existing research publications/aliases into
the isolated preview without replacing later review. All 11 company names
resolve; the lens shows 25 programs, four partnership claims and 30 sources.
The migration preserves content and subsequent user removals/unlinks on restart.
Research access, identity and commercialization gaps remain explicit.

A sticky quick-navigation bar jumps to Overview, Research, Landscapes, Entities,
Connections and Coverage. It expands the relevant row in Grid view and clears
filters that would hide the destination. Header/nav measurements keep jump
positions below both bars; narrow screens scroll the navigation horizontally.
It changes no saved view preference or canonical record.

Validation: 161 workspace, gene-editing, Landscape overview/Explorer, reader and
auth checks passed (one existing ReportLab deprecation warning). New regressions
cover linking from either side, origin rejection, unlinking, source fingerprints,
required combined citations and one-time roster repair. Browser verification
confirmed eleven resolved entities, reciprocal research display, successful live
Perplexity generation with page + Landscape citations and Grid section jumps;
Cards preference was restored. No merge or production deployment.

## Social Listening references and navigation

Social Listening’s real/imported/manual post rows and Reader expose Save to
workspace, using the existing destination/recent-workspace picker and retry/undo
flow. A social placement stores only its observation ID and mode. Post text is
resolved from Social Listening on read, not copied into workspace storage,
history, recovery drafts or model packets. Removed, excluded, expired and fixture
observations cannot be added; previously saved unavailable observations show a
placeholder. Opening the post returns to its Social Listening reader. Automatic
AI summaries exclude social post text. Capturing source statements or promoting
social observations remains a separate existing review decision.

The product is labeled Workspaces and appears directly in the primary navigation:
News, Personal Digest, Map Explorer, Social Listening, Workspaces, Landscape,
Companies, bold Learn, then More. Private authoring entries remain absent from
public static navigation.

Landscape Explorer uses compact headings/filters/tables and distinct evergreen
structure, blue analysis/source context and amber gaps/disputes, with matching
dark-mode colors. The generic workspace banner was removed. Only named/saved
Landscape views expose their specific workspace association. Gene Editing and
Advanced Breeding is grouped under Saved Explorer views as the built-in research
view; saved-view scope behavior is unchanged.

Validation: 172 workspace/social/removal/Landscape/reader/auth regressions passed;
24 workspace tests passed after final reference validation. JS syntax and diff
checks passed. Browser verified primary navigation order, bold Learn, removal of
the generic banner, the named-view grouping and light/dark contrast. The isolated
preview contains no live social posts; social save/retry/removal and non-copying
were verified using isolated test records, without collecting or inventing live
observations. No additional model export permission is inferred for social text.
