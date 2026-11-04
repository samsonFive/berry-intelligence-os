# Source intelligence bounded collection continuation — November 4, 2026

The reviewed #501 implementation and separately approved historical transcript delivery are deployed; see [the release receipt](SOURCE-INTELLIGENCE-RELEASE-501-2026-11-04.md). The user subsequently approved this follow-up as #508, now deployed at canonical `00adb635b6aac084a14b181102728994e6e62e86`; see [its release receipt](SOURCE-INTELLIGENCE-RELEASE-508-2026-11-04.md). The investigation below records the pre-release findings. Recurring activation remains unapproved.

## Current release boundary

Read-only production verification found healthy HTTPS, 281 Sources, the credit-free guard enabled, and the existing active timer selecting exactly `--pipeline news_workspace_refresh`. Live Global Watchlist #505 superseded #501's historical image while retaining its implementation. The separate combined #506 release has an active owner and shared-host preservation checks. This task does not take over that release or change its canonical base while it is being finalized. A read-only bounded source plan deferred when the shared review lock was busy; it did not acquire the lock or mutate production.

## Bounded selection fix

The runner sorted retained discoveries oldest first and sliced `--max-items` before considering whether they had already been attempted or were blocked. Three regression cases reproduced the problem: the same first item was selected three times; a current discovery lost to an old retained recording; an operator-held item consumed the only slot while actionable work waited.

Capped passes now prioritize actionable current non-backlog discoveries, then unattempted work and least-recently-attempted work. Original deterministic ordering breaks ties. Uncapped selection remains unchanged. Existing retry limits/backoff, operator intervention, publication review, extraction qualification, locks and transcription budgets still apply. Held states are read, not rewritten to make an item eligible. Caps of zero still process no items. The selection policy does not infer trust or make a new transcription/extraction decision.

## Real current video and relevance

The [publisher website](https://blueberriesconsulting.com/nosotros/) links to Blueberries TV. Its public channel page still resolves to the already registered `UCwypVNJp_DjjoLtqVCwIF4w`; no replacement identity was invented. Earlier requests returned 404. On November 4 at 18:59 UTC, both its [channel feed](https://www.youtube.com/feeds/videos.xml?channel_id=UCwypVNJp_DjjoLtqVCwIF4w) and public uploads-playlist feed returned 200 with 15 entries, including [the November 3 recording](https://www.youtube.com/watch?v=Qeq_cMsOFRc). This is a successful current observation, not a guarantee against intermittent future failures. No endpoint/config change is necessary to claim this success.

A local canary persisted at most two discoveries and created one new schema-valid current video draft; all nine existing drafts remained byte-identical. One staged feed entry was historical backlog. The current recording exposed a separate metadata-screen gap: explicit Spanish blueberry-industry phrases were absent from the shared vocabulary. The follow-up adds narrowly scoped accented/unaccented phrases for the blueberry industry and global blueberry industry. Berry dessert/general-food metadata remains excluded; a publisher name alone is not an exemption.

Authenticated local HTTP and actual browser review verify the new recording in the video filter, its original watch link and its Reader. Both return 200; the Reader explicitly says description only, with zero transcript segments. The screenshot is private `inbox/search-quality-evaluation/source-gap-current-video-reader.png`. This fresh local draft was not delivered to production, and its description was not represented as spoken transcript text.

The [Committee's official institutional page](https://frutasdechile.cl/committee/arandanos/) separately links to its current `@comitedearandanos_chile` channel. That feed returned five dated entries, newest November 2025. The existing registered channel intentionally represents a different older training archive; neither its identity nor history was replaced. The newer channel is a verified onboarding candidate, not an automatically activated collector or proof of current 2026 coverage.

## Validation and next review

Local runner checks: 24 passed. The related collection/CLI/scheduler/lock/discovery/orchestration/qualification run passed 122 tests; one known Windows TestClient publication-review route was deselected and remains required in full Linux CI. Five focused feed cases passed, including Spanish industry phrases and description-only behavior. The initial three starvation regressions failed before the fix. Required current-head CI, canonical reconciliation and bounded current-live preservation remain deployment gates for this follow-up. No runtime settings, seed records, schemas or dependency files change.

No production writes, paid requests, credit purchases, caption acquisition, STT/model calls, automatic trust promotion or new recurring activation occurred in these continuation canaries. Private receipts remain outside Git/static output.

The first production collection proposal is still one allowlisted Business of Blueberries Source, at most two discoveries/two processed items, `--skip-transcription --max-transcriptions 0 --no-model-enrichment`, and extraction explicitly disabled. Run a backed-up, bounded manual production canary under the shared locks, inspect due decisions and backlog/review yield, and verify retry/preservation before seeking recurring activation. Keep the existing News selector until that separate review. Source-audio word accuracy, fresh caption access, Exa allowance, accessible-page linked browsing, a representative sealed analyst-outcome evaluation and broader source/variety coverage remain open. Existing failed benchmarks and human identity/trait/right/footprint decisions remain unchanged.
