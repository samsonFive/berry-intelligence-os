# Keyword monitor historical backfill — review checkpoint

October 27, 2026. Implemented for review; merge and deployment remain on hold.

## Use

Open a saved scoped monitor in **Keyword Monitoring**, choose **Backfill older articles**, set From/Through dates and an article limit, explicitly choose **Perplexity Search**, and start. Save term/scope edits before backfilling. The action uses the saved monitor revision and displays the external search destination and data sent. It works for monitors created using the Berry/Region builder; existing raw-expression defaults require a new scoped monitor rather than silently inferring their intended scopes.

The backfill runs separately from recurring discovery. It does not change the monitor's recurring provider, enable a scheduled job, or widen News's 30-day freshness contract. A monitor can use Google News prospectively and explicitly use Perplexity Search for historical discovery. Provider access and charges apply only when starting the explicit backfill, not when opening the editor.

Historical backfills shows persisted status, dates, collected/duplicate/skipped/failed counts and article-review links. The browser refreshes status while a run is queued/running. A stopped process does not automatically resume or issue more paid searches; after twenty minutes an unfinished status is marked interrupted and retains already saved items. One backfill can run at a time, using the existing shared collection lease. Stale monitor revisions fail before external requests. A failed provider request is visibly failed, never a successful empty collection.

## Collection and review boundary

The date range is inclusive, at most five years, and ends no later than today. The operator selects 1–20 articles. Existing bounded topic discovery issues at most six Search API requests and captures at most forty public candidates. Date constraints are sent to search and rechecked against acquired publication dates. Undated/out-of-range/unreadable results do not become backfill publication drafts. Simple Any/All terms, the selected crop and regional place names are checked against captured text. Regional matches remain search context, not verified growing footprints. Advanced operator semantics remain provider-dependent.

Public registry cultivar names justify bounded follow-up searches; no target article URLs are injected. Already acquired, paragraph-indexed text is passed to the shared `process_discovered_article` pipeline via `acquired_body`, avoiding a second fetch. Existing relevance screening, parent-publication identity checks, rejected/pending dispositions and body-conflict safeguards still apply. Existing trusted or reviewed publications are not overwritten.

Each monitor obtains one disabled manual-reference Source for durable provenance, only when a qualifying article is staged. This is not publisher auto-onboarding and has no recurring discovery adapter. The staged item's metadata connects the monitor, backfill run and provider to the existing discovered-media record. The normal publication draft contains its source URL, original date, body hash and paragraph locators. No synthesis/extraction model is called by backfill. No publication, Atomic Evidence, Signal, Fact or Assessment is automatically trusted.

Results enter the existing private publication-review inbox. Topic reports already search accessible pending publications and label them **PENDING / UNREVIEWED**. They can now cite acquired historical source passages with archive-only scope and no further provider request. Human publication and atomic-evidence gates remain mandatory. Other readers that only show published evidence still require publication review; backfill does not bypass those contracts.

## Live Floricane / Blackberry retest

The authenticated local editor started a genuine backfill for **Floricane**, **Blackberry**, **Global**, January 1–October 26, 2026, cap ten. It issued four Perplexity Search requests, discovered thirty candidates, acquired twenty source bodies and retained six date/topic-matching articles. All six staged successfully, with no collection failures. The matching articles include:

- NC State's February 8 Ervin introduction, with NC 740 and the floricane fruiting habit in the acquired body.
- Global Plant Genetics' September 1 licensing announcement for development outside the United States.
- FreshPlaza's September 3 account of that licensing milestone, UF/IFAS's May 11 production article, a July discussion and an April pruning article.

Six matching articles are not six distinct developments or six independently corroborating sources. General event clustering and relevance judgments remain separate acceptance work.

| Actual app archive-only report query | Before backfill | After backfill | Both checked primary sources cited | Web calls during verification |
|---|---:|---:|---|---:|
| Blackberry Floricans | 0 | 6 | Yes | 0 |
| Floricane blackberry developments | 0 | 6 | Yes | 0 |
| New blackberry varieties that fruit on second-year canes | 0 | 6 | Yes | 0 |

Verification called the real app's `_build_packet_and_coverage` and `topic_sections` against the isolated runtime. The archive-only web-discovery function was replaced by a raising sentinel, so any attempted web call would fail verification. Both primary sources appeared in cited findings with their original dates and pending/unreviewed labels. No canonical evidence was published. All six live drafts passed the Evidence schema. The before figure is the earlier read-through canonical archive assessment; the after figures include these newly saved pending drafts in the isolated runtime, as the report UI's normal accessible-archive contract permits.

One live backfill was completed. Automatic approval review rejected a second live run because it could incur additional external-provider charges. It was not retried indirectly. Repeat-run identity reuse is instead verified offline: no duplicate publication draft, no overwrite of the existing pending body, and duplicate counts increment. This is not a claim of a second live run.

Validation: 162 deterministic tests passed across backfill, collection settings, article processing, topic retrieval, reports, publication orchestration, shared locks and static publication safety. Canonical record validation, six live draft schema validations, JavaScript syntax and whitespace checks passed. Browser checks covered the date/provider controls, starting a background run, completion refresh and persisted review links. Private captures and runtime state remain under gitignored `inbox/collection-settings-preview/`.

This demonstrates the targeted historical acquisition path. Full Google parity, complete historical coverage, additional historical providers, resumable durable workers, automatic legacy-monitor conversion and general event clustering are not claimed. No production runtime, merge or deployment changed.

## October 28 — explicit checkpoint resume

Completed discovery results and acquired bodies now checkpoint privately before staging starts. Candidate progress is saved after each skip or staging outcome. Interrupted/failed runs with a checkpoint show **Resume saved backfill**. The action validates authoring access, CSRF, the shared collection lease and the original monitor revision. It stages remaining saved candidates without another provider search; it does not retry already recorded per-item failures. If staging succeeded immediately before a process stop but the cursor was not written, the existing duplicate safeguards preserve the prior draft. Collected-versus-duplicate counts may therefore reflect recovery rather than the first staging attempt.

A run without a completed-search checkpoint cannot resume; starting a new backfill requires the existing explicit provider selection. A shared collection lease left by a crashed process retains its existing six-hour stale timeout. No automatic scheduler or lease-bypass is introduced. Private candidate bodies are excluded from the status JSON. Historical jobs created before this checkpoint format remain readable but cannot acquire a missing snapshot retroactively. Earlier statements that there was no explicit resume describe the prior checkpoint.

Deterministic recovery verification simulated a process stop after the first staged article, then resumed the second with an external-provider raising sentinel. Both remained pending publication review; repeat execution did nothing. Missing snapshots, changed monitors, CSRF/read-only access and body-free status responses are covered. No additional paid run was used.
