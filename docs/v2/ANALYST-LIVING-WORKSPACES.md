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
Document view preserves the full document layout. View choice is remembered
locally. A row filter searches the curated page without changing its order or
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
The sorting direction is remembered locally and does not reorder the underlying
curated document blocks. Update timestamps remain available in date-cell tooltips.

Browser validation used archived 2021, 2025 and 2026 publications: ascending and
descending chronology and a 2025-only date range passed. A shortcut typed into an
analyst note stayed text rather than saving; test input was discarded.
