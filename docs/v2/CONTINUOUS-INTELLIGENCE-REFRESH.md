# Continuous Intelligence Refresh

Status: implemented, validated, not yet scheduled on the VPS as of this
document's own commit (see "Deployment" below for the exact operator step).

## What this is

A safe, bounded, unattended way to keep discovery/review current without
Johnny running `scripts/run_collection.py` by hand. It is explicitly **not**
a new acquisition architecture: every piece below is a scheduler wrapped
around the existing `scripts/run_collection.py --all` path
(`CollectionRunner` → per-source `discover_source()` → per-item
`orchestrate()`), the same code the interactive/manual flow already uses.

## Why it was needed

The Freshness + Company News Recall sprint (PR #14) proved the pipeline
works end-to-end but still required a human to type the command. Two real
problems surfaced the first time the *full* recurring path was actually run
unattended against every registered source:

1. **Podcast/video back-catalog flood.** A source with a deep back-catalog,
   checked for the very first time, staged 562 new untranscribed episode
   drafts in one pass — a real back-catalog catch-up, not a bug, but not
   acceptable *recurring* behavior either. Fixed by a bounded
   initial-discovery policy (below).
2. **Adjacent content outranking direct berry intelligence.** The live
   feed's ranking never knew about `relevance_tier` (direct/adjacent) at
   all. Fixed by wiring it into the existing ranking seam (below).

Both fixes are described in full in this document's own commit; see
`app/services/media_discovery.py` and `app/services/intelligence_feed.py`
for the code-level detail.

## Bounded initial-discovery policy (spoken media only)

`app/services/media_discovery.classify_initial_backlog()`. On a spoken-media
source's (`podcast`/`video`/`conference_video`) **first-ever successful**
discovery run (no prior `last_success_at` recorded), only a bounded recent
window is staged as current:

- the 10 most recent items (`INITIAL_DISCOVERY_MAX_ITEMS`)
- published within 30 days of the check (`INITIAL_DISCOVERY_LOOKBACK_DAYS`)
- always at least the single most recent item, even if older than 30 days,
  so a dormant show never yields zero items

Everything outside that window is **still staged** (never silently
dropped) but flagged `historical_backlog: true` on the discovered-item
record. `scripts/run_collection.py`'s `orchestrate()` checks that flag and
skips drafting for it (`state: "historical_backlog_suppressed"`), so the
Scanner review queue is never dominated by a one-time backlog dump.

**Deliberately not bounded**: `web_article` sources. Their volume is
already gated downstream by `relevance_screen.py`'s body-aware screening
before a draft is ever created — discovery-time item count was never the
article flood's cause the way it is for spoken media (a podcast/video item
gets a draft unconditionally; there is no per-episode relevance screen).

**Operator backfill**: `python scripts/run_collection.py --all
--allow-historical-backfill` stages and drafts the full back-catalog
deliberately, once, when an operator actually wants it. This also applies
per already-staged backlog items (a rerun with the flag drafts them too).

## Direct-vs-adjacent ranking (reuses PR #15's existing feed, does not fork it)

PR #15 ("live intelligence reader") already owns the live feed/reader/inline
promotion experience (`app/services/intelligence_feed.py`,
`app/templates/intelligence_reader.html`). This work does not duplicate or
parallel-build any of that — it adds one field to the *existing* ranking
function:

`_feed_sort_key()`'s first sort key is now `relevance_tier` (from PR #14's
`app/services/relevance_screen.py`): a `direct` item always outranks an
`adjacent` one, ahead of `relevance_band`/`berry_direct` (separate,
independent AI-enrichment signals that don't capture the same "is a berry
species the real subject, or one incidental mention" distinction). Items
with no tier at all — podcasts, videos, trusted Evidence, pre-fix article
drafts — are tier-neutral, ranked with `direct`, never penalized for
predating this field.

Adjacent signals are **not hidden**: a new `"adjacent"` feed filter
(`FEED_FILTERS`) surfaces them explicitly, matching the existing filter
pattern (`articles`/`spoken`/`patents`/etc.).

## Cadence and resource boundaries

- **~Every 4 hours** (`deploy/systemd/bios-collection.timer`,
  `OnCalendar=*-*-* 0/4:00:00`), the closest fixed-clock approximation of
  "every 4 hours" systemd timers support cleanly.
- **No automatic transcription.** The scheduled command always passes
  `--skip-transcription` — spoken-media items are discovered (cheap
  RSS/Atom, no audio download) but never transcribed automatically. A
  discovered-but-untranscribed item reports `transcript_status: "missing"`
  and is counted separately in the run report (`transcript_needed`) rather
  than silently looking like "no news." Transcription (local `faster-whisper`,
  requires the full `requirements.txt` local-collection stack this deployed
  container deliberately omits) stays an explicit operator action elsewhere.
- **Article body acquisition stays automatic and cheap.** `trafilatura`
  (pure-Python readable-text extraction, no system deps) is now in
  `requirements-web.txt` so the recurring collector can run real article
  acquisition + relevance screening inside the same deployed container —
  no second image, no new service.
- **Per-source cadence is not currently used to skip a scheduled check.**
  `update_cadence` (`weekly`/`monthly`/etc.) drives the `/sources` freshness
  *display* (`source_freshness.py`) but every scheduled run still polls
  every registered source's feed — a single lightweight HTTP GET per
  source, not scraping, and not expensive enough to warrant a skip-if-not-due
  gate at this scale (~15-20 sources). This is an honest scope limit, not
  an oversight: implementing true per-source cadence-gated scheduling would
  be a real architecture addition to `CollectionRunner`, not a scheduler
  wrapper change, and wasn't required to make the two real problems above
  safe to schedule.
- **Failure isolation, retry/backoff, and the run lock are unchanged** —
  all pre-existing `CollectionRunner`/`discover_source()` behavior. One bad
  source (feed timeout, malformed entry) never aborts the run; a genuinely
  wedged/overlapping invocation is a fast, safe no-op via
  `inbox/operations/collection.lock`, backed by systemd's own oneshot
  overlap coalescing at the scheduler level.
- **No auto-trust, ever.** Every discovered item still lands as an
  untrusted pending draft (or stays a bare discovered-media record if
  historical-backlog-suppressed); publication still requires the existing
  human review gate. Nothing about this scheduler changes what counts as
  trusted.

## Post-run reporting (`--json` output / `CollectionRunSummary.counts`)

New fields, additive to the existing `items_discovered`/`items_new`/
`items_known`/`publication_drafts_created`/etc.:

| Field | Meaning |
|---|---|
| `historical_backlog_discovered` | Of this run's `items_new`, how many a spoken-media source's first-ever check held back as backlog |
| `historical_backlog_suppressed` | Items whose orchestration was skipped this run because they're flagged historical backlog |
| `direct_review_ready` | Web-article drafts tagged `relevance_tier: "direct"` that reached `awaiting_publication_review` this run |
| `adjacent_review_ready` | Same, tagged `"adjacent"` |
| `irrelevant_rejected` | Items screened and confirmed irrelevant before any draft was created (`state: "skipped_irrelevant"`) |
| `transcript_needed` | Spoken-media items with `transcript_status: "missing"` (discovered, not yet transcribed — never conflated with a failure) |

`items_new` (per source, summed) is already the accurate "genuinely new
since the last successful run" figure — it comes from
`discover_source()`'s own dedupe-identity check, not a backlog re-walk.
`items_processed` remains a re-walk of the full known-item backlog each run
(existing, pre-Continuous-Refresh `CollectionRunner` behavior, needed so
retryable/pending items keep getting revisited) — read `items_new` and the
table above for "what's actually new," not `items_processed`.

## SOURCE COVERAGE status line

`app/services/source_freshness.aggregate_source_coverage()`, surfaced on
the existing `/sources` page (no new route, no new subsystem): `N current ·
N due · N stale · N failing`, plus the most recent successful check across
all sources as "Last refresh." Deliberately does **not** report a "next
scheduled refresh" inside the app — the app has no way to know whether a
scheduler is actually installed, and fabricating a next-run time was
explicitly ruled out. Once `bios-collection.timer` is installed (see
Deployment), the real next-run time is always the next 4-hour UTC clock
boundary (00:00 / 04:00 / 08:00 / 12:00 / 16:00 / 20:00 UTC, ± the timer's
5-minute randomized delay) — a deployment-level fact, not something the
running app process tracks.

## Company/entity Recent Intelligence — unchanged, reused

Automatically discovered articles continue to flow into PR #14's existing
`recent_intelligence_for_entity()` mechanism exactly as before (matched via
`entity_ids`/`berry_ids` on the same draft records this scheduler produces)
— no second company-news subsystem was built or considered for this work.

## Regression tests

- `tests/test_media_discovery.py`: bounded backlog policy (first-ever run
  bounds to the recent window; never yields zero items for a dormant show;
  `--allow-historical-backfill` stages everything; a second run's genuinely
  new item is never flagged backlog).
- `tests/test_collection_runner.py`: new counts (`direct_review_ready`/
  `adjacent_review_ready`/`irrelevant_rejected`/`transcript_needed`/
  `historical_backlog_discovered`/`historical_backlog_suppressed`).
- `tests/test_intelligence_feed.py`: direct outranks adjacent at equal
  band/date; the `adjacent` filter isolates without hiding; tier-absent
  items rank with direct, not penalized.
- `tests/test_source_freshness.py`: `aggregate_source_coverage()` counts
  each state correctly, reports the true most-recent success as
  `last_refresh_at`, and never fabricates a next-run field.

`scripts/run_collection.py`'s `orchestrate()` closure itself (the
historical-backlog skip branch, `relevance_tier` propagation) is thin glue
over already-tested functions (`process_discovered_article()`,
`media_discovery`'s backlog flag, `OrchestrationResult.relevance_tier`) —
consistent with this project's existing convention of testing the
underlying service functions rather than the CLI's `main()` directly (see
`tests/test_article_refresh.py`'s own comment on this same boundary).

## Deployment (operator step — do this once, on the VPS)

Repo artifacts already exist; nothing runs until these are installed. Run
as a user with `sudo` (matches this project's existing
`scripts/vps_bootstrap.sh` convention):

```bash
cd /opt/berry-intelligence-os
chmod +x scripts/collection_cron.sh
sudo cp deploy/systemd/bios-collection.service deploy/systemd/bios-collection.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bios-collection.timer
systemctl list-timers bios-collection.timer   # confirm the next scheduled run
```

To test the service unit itself once, synchronously, before trusting the
timer:

```bash
sudo systemctl start bios-collection.service
journalctl -u bios-collection.service -n 100 --no-pager
```

To deliberately backfill a source's full back-catalog once:

```bash
BIOS_COLLECTION_EXTRA_ARGS=--allow-historical-backfill ./scripts/collection_cron.sh
```

No passwords or secrets are touched by any of the above; `collection_cron.sh`
only wraps `docker compose exec` against the already-running `app`
container using the deployment's existing `deploy/.env`.
