# Pending Review Query Performance V2

Date: 2026-08-23
Scope: private `/pending` query/read-model performance only

## Outcome

`/pending` now separates exact inventory/classification work from bounded card
hydration. The route reads a private, rebuildable metadata projection, applies
the existing `ids`, berry, and source filters before ranking, calculates exact
bucket counts over compact records, groups Story Threads through indexed
candidate edges, and hydrates at most 20 visible entries per bucket. The source
draft remains authoritative and `/review/{id}` / `/intelligence/{id}` continue
to read its complete article and transcript.

No review state, trust gate, bucket rule, rank weight, Source, acquisition path,
schedule, Atomic extraction setting, or model qualification setting changed.

## Profile of the previous route

The previous `/pending` request performed these stages before returning its
first screen:

1. `list_pending_drafts()` recursively read/deserialized every draft (including
   `article.paragraphs` and transcripts on a cold call).
2. Query filters were applied only after that complete inventory load. The live
   route supports `ids`, `berry`, and `source`; no additional hidden filters
   were inferred or added.
3. `_assemble_morning_brief()` loaded the complete trusted Evidence inventory,
   Entity inventory, and Source configuration. It scanned trusted titles and
   active monitoring state to build duplicate/watch context.
4. Every pending draft was expanded into a rich queue/feed presentation card.
   Entity attribution scanned every eligible entity against title and body,
   and `rank_item()` redundantly requested attribution/primary/title matches.
5. The complete ranked list was sorted and bucketed. Exact counts were useful,
   but they were coupled to rich card construction.
6. Review-now/review-soon Story Threads compared every pair (`O(n²)`), built all
   thread presentations, and compressed whole buckets.
7. Only after all of that did `_pending_triage_groups()` slice each bucket to 20.
8. Review action defaults and Jinja rendering were already bounded by the late
   slice. Reverse-reference services and signal candidates were not on this
   route; geography/berry/entity labels were derived during card presentation.

The full-corpus work was therefore draft I/O/deserialization, trusted-title and
watch scans, attribution, rank-card construction, global sort/bucketing,
duplicate-cluster handling, Story Thread all-pairs comparison, and exact counts.

## Implemented boundary

`PendingReviewQueryService` depends on the storage-neutral
`PendingDraftSnapshotProvider` protocol. The current JSON provider maintains
`inbox/indexes/pending-review-v2.json`, a private disposable read model keyed by
source filename/mtime/ctime/size and by a deterministic Entity/Source matcher
fingerprint. New, changed, rejected, saved, or published draft files are picked
up on the next request; unchanged records are reused across process restarts.
Analyst queue state is intentionally not stored in the projection, so
Dismiss/Restore is read from the authoritative runtime state every request.

The index contains compact draft metadata, the original deterministic
attribution result, and no article object, paragraph text, transcript, raw HTML,
raw content, source text, or publisher body. It is safe to delete and rebuild.
`scripts/rebuild_pending_review_index.py` prebuilds/verifies it before traffic
without logging private content.

Ranking preserves the existing score/bucket rules. All records receive a cheap
compact classification because exact counts and top-window selection require
it; rich queue/feed cards are created only after the five bucket windows are
selected (maximum 100 singles, normally fewer after thread compression). Story
Thread candidate generation uses the exact predicates' natural indexes:
canonical URL, normalized title, explicit Evidence links, primary entity, and a
seven-day company/variety window. Candidate pairs are sorted back into the
historical nested-loop order before union, preserving deterministic components
and tie behavior without a corpus-wide all-pairs scan.

## Benchmark

Command:

```text
python scripts/benchmark_pending_review.py --sizes 1500 5000
```

The benchmark generates private production-shaped drafts with article bodies
and transcripts in a temporary runtime. It logs timings/counts only, exercises
inventory reuse, compact ranking/threading, bounded action hydration, actual
Jinja rendering, and direct rich-detail JSON loading.

| Corpus | Cold restart | Warm navigation | Inventory | Rank/thread model | Actions/template | Visible / exact open | Direct detail |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,500 | 3.436s | 1.839s | 0.336s cold | 2.218s cold | 0.882s cold | 80 / 1,500 | 32.4ms |
| 5,000 | 1.476s | 1.248s | 0.330s cold | 1.021s cold | 0.126s cold | 80 / 5,000 | 0.6ms |

Both runs confirmed `list_projection_has_rich_body=false`, exact open counts,
and `direct_detail_has_article=true`. A final conservative 1,500-record rerun
after the full validation/temp-tree workload produced the table's slower but
still target-passing result. First-ever local index bootstrap ranged from 22.3s
to 147.1s at 1,500 and measured 76.1s at 5,000 on Windows, dominated by opening
thousands of individual files under real-time scanning. That is an explicit deployment
stage, not a request-stage cache miss: run the rebuild command before restart;
subsequent restarts and incremental mutations reuse the verified read model.

## Safety and regression coverage

- Indexed attribution is compared directly with the historical matcher.
- Existing pending bucket, score, duplicate/reprint, watch, and Story Thread
  tests remain unchanged and green.
- Filter intersection and exact counts are tested.
- Full-corpus classification versus bounded rich hydration is instrumented.
- Article/transcript omission, restart reuse, draft mutation, direct rich-body
  preservation, and private sidecar content are tested.
- Static generation still reads canonical trusted data only; the index remains
  below gitignored `inbox/` and is not copied to static output.

## Remaining limitation

The JSON backend still performs an `O(n)` filesystem signature scan and compact
classification to guarantee immediate mutation visibility and exact counts.
That is comfortably inside the measured targets at 5,000 records but is not a
database index; a future PostgreSQL backend should implement the same provider
protocol with indexed count/window queries. This mission does not justify or
begin that migration.
