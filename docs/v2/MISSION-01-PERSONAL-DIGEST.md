# Mission 1 — Personal Digest and reading continuity

September 30, 2026. Implementation branch: `feature/personal-digest-mission`, stacked on the accepted design study. Review checkpoint; not merged or deployed.

## Purpose and delivered behavior

Personal Digest (`/digest`) answers **what have I chosen to read, and where did I leave off?** It combines deliberate saves, the existing reading queue and company stories from explicitly subscribed custom lists. The same exact article ID appears once with every inclusion reason. It defaults to newest published first and active reading, with completed/all/dismissed views, query, multi-berry and multi-region filters, priority and 7-day/30-day/YTD/custom dates. Pages contain up to 36 cards.

Dense Glasshouse cards retain source/date, image, preview context, review label, saved mark, inclusion labels and reading controls. Selected stories can be completed together. The shared `#v2ReaderOffcanvas` overlays the right side without resizing or scrolling the grid; Close/Escape returns focus, history and scope. Article and Brief retain separate reading positions. Wider reading is optional. The icon toolbar offers usefulness, relevance, save and a separate publisher link; hover descriptions appear after two seconds and keyboard focus reveals them immediately.

The Article view displays available stored/captured publisher paragraphs, with a conservative partial-text label. A synopsis or access wall cannot masquerade as an original article. When text is missing, an explicit action requests the existing safe public-source capture path. Failure retains a publisher link and Brief; it never produces substitute prose. Captures stay private and do not rewrite published Evidence. Brief keeps the summary prominent, statements individually labeled, company links available and coverage/review notes collapsed.

## State mapping and preservation

| Concern | Existing durable home / meaning | Digest treatment |
|---|---|---|
| Saved mark | `inbox/feed_first_state.json`, `decisions[id].saved` | Preserve existing marks; save/unsave explicitly; independent of progress. |
| News opened flag | Same decision's `read` | Preserve as legacy opened history. It does **not** mean completed. |
| Reading disposition | `inbox/analyst_queue_state.json`, `reading[id]` | Preserve unread/saved/read/dismissed/promoted and review ledger; add in-progress/reopen. Legacy queue “saved” remains a reading disposition, not a Digest saved mark. |
| Reading priority | Evidence `priority.reading.level` | Display its default; explicit personal override lives in the existing reading entry. Never mutate published priority to remove an item. |
| Reader position | Existing reading entry, `reader_positions` and `reader_mode` | Separate Article/Brief offsets. Merely remembering a position does not add an article to the queue or mark it complete. |
| Custom lists | Feed-first state, `company_lists` | Named, multiple-company membership, edit/rename/archive; start unsubscribed. |
| Digest subscriptions | Feed-first state, `digest_subscriptions` | Explicit subscribe/unsubscribe. Separate from membership, favorites, tiers, watches and notifications. |
| Feedback | Existing decision `reaction` | Usefulness/relevance only; no automatic completion, extraction or confirmation in Digest. |
| Trust and review | Existing publication/proposition stores | No writes from Digest reading, saving, feedback or subscriptions. |

Published records control text, assignments, reading tags and publication status when an exact ID occurs in both published and cached news. Retained daily news caches keep older saved articles available. A matching source URL may supply a missing preview image only. A deleted source leaves its saved mark / explicit reading history visible as an unavailable-source entry. Different source records are not collapsed by similar titles, since independent coverage and review histories must remain distinguishable.

`/saved` remains a compatibility redirect to saved marks across all reading states, carrying query scope. The old `/queues/reading` GET/POST workflows and review ledger remain available inside Digest's Existing reading tools disclosure. Live navigation points to Personal Digest; the unused Saved template is retired. Static navigation retains its published reading inventory, and no Digest pages/private personal state enter the public build.

Private file replacements are atomic. New personal writes, queue actions and primary legacy save/reaction writes are serialized within a local application worker. Multi-worker coordination and account-specific tenancy remain existing platform work; this checkpoint uses the application's operator-workspace stores.

## Acceptance evidence

- Isolated deterministic tests cover News save → Digest → complete → reopen, old `/saved` links, exact-ID deduplication, all origins, opt-in lists, unsubscribe/archive preservation, legacy opened/saved/read states, priority/history and per-mode position continuity.
- GETs do not acquire source content, change saves/reading state or mark a Morning Brief seen. Personal actions do not extract or mutate published records. Unknown IDs/actions, invalid memberships/dates/priorities, cross-site writes and read-only writes are rejected. Bulk completion validates the selection before writing.
- Retained-cache tests protect older sources and canonical precedence; concurrent personal-write tests protect other stories. Static leakage sentinels cover private list names, subscriptions, saved marks and reading-position state.
- Browser review checks four-column density, stable grid/scroll on native story click, right overlay below navigation, Article/Brief and wider reading, feedback, Close/history/focus, responsive layout and viewport-contained grouped navigation. Screenshots document the isolated review workspace; illustrative images are labeled at workspace level.
- Full local regression run: 3,355 passed, nine skipped, one outdated Saved-marker assertion. That assertion was updated to the new destination; affected tests rerun successfully. Final focused regression and GitHub checks are recorded in the PR. Record validation and the trusted public build passed.

## Boundaries and following missions

This delivers the Digest family and its shared Reader entry. Other News, Company, Map, Learn and reporting surfaces keep their existing implementations until their own migrations. The company-list store is reusable; favorite/tier and list controls throughout Company/Map/News views are not yet migrated. Prototype browser-local company marks/lists remain in the study and are not silently imported into this production store. No provider research, collection refresh, model call or notification subscription occurs on Digest loads or list subscription.

The next mission is configurable Landscape, followed by a complete visual Learn research/lesson workflow, then reporting and Meeting Prep. Keep the audit and visual guide synchronized with each delivered family; retain specialist routes until equivalent workflows and historical state have been verified.
