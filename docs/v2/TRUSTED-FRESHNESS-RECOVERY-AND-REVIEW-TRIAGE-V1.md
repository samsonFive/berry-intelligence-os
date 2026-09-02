# Trusted Freshness Recovery + Review Triage V1

**Status:** Shipped 2026-09-02.

## Problem

The architecture audit's own read-only production forensics found the newest
published Evidence's real-world source date was 2026-08-06 (26 days stale)
because 1,710 Publication drafts were pending review against 3 ever
published and one recorded review decision in all of production history --
review throughput, not discovery volume, was the bottleneck. Competitor
Pulse V1 proved the system can *find* current intelligence on demand; it
still could not turn discoveries into *trusted* intelligence at an
operationally useful rate. This mission's job was to make the existing
trust gate usable, never to weaken it.

## What already existed (audit-first, before building anything)

`/pending` already substantially implements current-first triage:
`assign_pending_triage()` (`app/services/morning_brief.py`) deterministically
buckets every pending draft into Review now / Review soon / Adjacent /
Likely ignore / Older backlog using stored relevance_tier, calendar_age,
primary-subject/watch-match quality, and source authority -- not an opaque
score. `v2.js` already has app-wide keyboard shortcuts (j/k select, Enter/o
open, a/s/r for promote/save/reject) and bulk-dismiss for low-risk buckets.
Running this unmodified against the real 1,710-item production backlog
produced `review_now=12, review_soon=190, adjacent=4, likely_ignore=28,
older_backlog=1476` -- 86.3% of the backlog was already correctly
identified as historical, not dumped into "current."

Given that, this mission's job was **not** a rebuild. It was: audit the
real backlog composition, find what was actually broken in the existing
system against real production data, and fix exactly that.

## Real backlog composition (read-only production audit)

1,710 pending drafts: 1,662 `discovered_media_publication` (news) + 48
structured registry filings (28 CPVO PVR + 20 patent, `intake_type in
{pvr_filing, patent_filing}`, `source_tier: tier_1_primary`,
`priority.monitoring.level: high`). Queue age (by `captured_date`): 0 <24h,
17 1-3d, 0 4-7d, 1615 8-14d, 78 15-30d -- a single large historical-backfill
batch (~1615 items, one age cluster) sitting under a small, genuine daily
trickle (~17 recent items). Real-world currency (news only, by
`published_date`): 0 items <7 days old, 56 at 8-14d, 118 at 15-30d, **1488
(89.5%) older than 30 days** -- even among "direct" relevance_tier items,
90% were >30 days stale. 0 exact-URL duplicates; 22 same-title+source
near-duplicates. 0 malformed/incomplete records.

## Two real, confirmed gaps found and fixed

1. **Registry filings were invisible.** All 48 structured PVR/patent
   filings were confirmed entirely absent from every `review_now`/
   `review_soon`/`adjacent`/`likely_ignore` preview -- 100% landed in
   `older_backlog`, indistinguishable from 1,400+ stale news articles.
   Root cause: `calendar_age <= 45` judges a registry filing by its
   filing/grant date (often years old), which reflects the underlying
   legal event, not how current the *review decision* is. Fixed by giving
   `intake_type in {pvr_filing, patent_filing}` its own dedicated
   `structured_registry` triage bucket, bypassing the news-recency test
   entirely rather than forcing an ill-fitting threshold onto it. See
   TD-110.
2. **Keyboard shortcuts silently did nothing on the one page built for
   fast triage.** `v2.js`'s existing `a`/`s`/`r` handler looks for
   `[data-promote]`/`[data-save]`/`[data-reject]` inside the current card;
   `_pending_decision_actions.html` had none of these attributes on its
   buttons. Fixed by adding them, plus new `data-duplicate` (reject with
   the already-existing `rejection_category=duplicate`, previously only
   reachable via the advanced form) and `data-defer` (relabels the
   existing Dismiss action -- same semantics, keeps the file, hides from
   today's triage), bound to `d`/`x`. See TD-111.

## The Evidence "fast path" audit finding

The mission assumed a Publication-approved -> extraction-proposal ->
Evidence-Review -> approved-Evidence pipeline. It does not exist for
ordinary Publications: `evidence_role: "atomic_evidence"` (the real
extraction-proposal mechanism) is created only from transcript evidence
(`transcript_evidence.py`), never from article Publications --
`publication_review_workspace.py` says so explicitly
(`"atomic_evidence": "NOT CREATED BY THIS ACTION"`). Every one of the
1,710 pending drafts (news and registry alike) carries
`evidence_role: "publication_artifact"`, and `/review/{id}/publish`
promotes that exact record to `status: "published"` -- the same record
then counts directly as trusted `published_evidence`. **Promote already
is the one-step Evidence-creation path for this content.** There was
nothing to shorten; the finding itself is the answer -- the bottleneck was
always upstream, at the single Publication Review decision, never a
downstream stage.

## Freshness telemetry

`pending_freshness_telemetry()` (`app/services/morning_brief.py`) is a new,
compact, analyst-facing panel on `/pending` only -- never stakeholder
Today. Six real, directly computed fields, no opaque score: newest trusted
source date, current-priority pending (Review now + Structured registry),
oldest current-priority item's published date, Publications approved
today, Evidence approved today (deliberately identical to the previous
field, with an explanation why), and current-priority queue age (days
since the oldest current-priority item was captured).

## What this does not do

- Does not weaken the trust gate. Promote/Save/Reject/Duplicate/Defer all
  reuse the existing `/review/{id}/*` and `/queues/pending/{id}` services
  unchanged.
- Does not batch-approve Evidence or Publications. Bulk actions remain
  scoped to Dismiss on Likely ignore / Older backlog only (pre-existing,
  unchanged).
- Does not build a second triage/scoring system alongside the existing
  one -- extends `assign_pending_triage()` in place.
- Does not activate recurring Newsroom Intake. That gate (queued
  explicitly) is evaluated separately, after real acceptance evidence that
  the current-priority queue is not aging.

See the production acceptance run (before/after trust counts, elapsed
time) in `PROJECT-STATUS.md` and the mission completion report.
