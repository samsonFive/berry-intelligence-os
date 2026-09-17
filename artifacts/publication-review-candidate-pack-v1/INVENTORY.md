# Publication review backlog — inventory

Branch: `research/publication-review-candidate-pack-v1`, base `c95c05e51b8247a0b22f417a877088c8d7f20e6b`
(`integration/competitor-intelligence-wave3`)

## Method and honest limits

This worktree's `inbox/` (where every publication draft, discovered-media
staging record, and review decision actually lives) is gitignored and
did not exist at all before this mission touched it — a fresh worktree
starts with **zero** backlog, and (per this codebase's own documented
rule) a cloud/isolated-worktree agent cannot see an operator's real local
`inbox/` runtime either. There is therefore no persistent, committed
"current backlog" to inventory directly.

To produce an honest, real, current inventory anyway, this mission ran
**one bounded discovery + acquisition pass** (not the rehearsal pack
itself — a separate, larger-but-still-capped diagnostic run used only to
observe real, current pipeline behavior):

```
python scripts/run_recent_batch.py \
  --sources source-20260901-blueberrybreeding-newsroom source-20260915-fruitist-newsroom \
            source-20260915-oishii-press source-business-of-blueberries-podcast \
            source-redagricola-on-the-road source-blueberries-tv-youtube source-lucentlands-podcast \
  --max-per-source 3 --max-total 20 --max-tier 2 \
  --report artifacts/publication-review-candidate-pack-v1/inventory-run-report.json
```

`--max-total 20` bounds body/transcript acquisition attempts and draft
creation — the resource- and network-impacting step. `discover_source()`
itself (called internally, once per source, with no `max_persisted_items`
cap) additionally *staged* each source's own bounded recent-backlog window
to this worktree's own gitignored `inbox/discovered_media/` (up to several
hundred lightweight, ephemeral staging records per source — feed metadata
only, never fetched or processed) before the 20-item cap narrowed which of
those actually reached acquisition. This is disclosed here for full
transparency: no `data/` file was touched, nothing was published, and only
the 10 items below received a real network body/transcript-acquisition
attempt — the staged-but-unprocessed records were never fetched, screened,
or drafted, and were **not** treated as part of the "collection run" this
mission's own git discipline bounds. A future rehearsal-pack mission
should pass an explicit per-source `max_persisted_items` to
`discover_source()` directly (as the companion `readable-acquisition-canary-v1`
mission did) if staging volume itself needs to be bounded too.

## The two halves of "the backlog"

### 1. Canonical, trusted corpus (`data/evidence/`) — the "already published" half

```
$ python -c "... count data/evidence/*.json by status ..."
total: 1272
published: 1269
in_review: 3
archived: 0
rejected: 0
```

Zero of the 1,272 trusted records has a populated `article`/`transcript`
body field (confirmed directly, same check as the prior
`readable-acquisition-canary-v1` mission). No `archived` or `rejected`
status record exists in `data/evidence/` — per `app/main.py`'s real
`review_reject()` handler, a rejected draft's `status`/`review_state`
become `"rejected"` **in place in `inbox/evidence/`**; it is never
promoted to `data/evidence/`. There is no dedicated "superseded" draft
state in the codebase — the closest real mechanism is a human rejection
with `rejection_category="duplicate"` (see `app/main.py`'s
`REJECTION_CATEGORIES`), functionally the same action a "superseded" item
would receive.

### 2. This mission's own bounded run — the "what does a fresh backlog actually look like" half

10 items reached a real acquisition attempt (podcast/article body or
transcript fetch); 2 sources (YouTube-based `source-redagricola-on-the-road`,
`source-blueberries-tv-youtube`) returned **0** discoveries — both feed
URLs (`https://www.youtube.com/feeds/videos.xml?...`) returned a real,
live HTTP 404 today, a genuine discovery-level failure distinct from any
body-acquisition failure. Not investigated or fixed further — out of this
mission's scope (inventory only; the companion readable-acquisition
mission's own rule against altering extraction/discovery code for a
publisher-side fact applies here too, and a 404 feed URL needs an
operator/URL-correction decision, not a code change).

| Category (mission's own objective-2 list) | Count | Examples |
|---|---:|---|
| Readable-body drafts | 0 (this run) | none — see reconciliation below; 8 proven possible via direct diagnostic in the prior mission |
| Transcript-backed drafts | 0 (this run) | none of the 3 podcast items had a publisher transcript or captions detected at tier ≤2 |
| Metadata-only drafts (audio, no transcript) | 3 | "Inside Walmart's Berry Strategy…", "Ports and Fresh Produce Logistics \| Ep. 157", "Can Farmers Use Fewer Chemicals…\| Ep. 156" (all `source-business-of-blueberries-podcast`/`source-lucentlands-podcast`) |
| Navigation-only shells (web_article, empty body) | 4 | 2× Oishii Press Feed, 1× Fruitist Newsroom ("Caleb Williams Describes…"), 1× UF blueberrybreeding ("Florida Blueberry Growers Association") |
| Blocked/retryable acquisitions | 0 (body-level); 2 (discovery-level, YouTube 404s) | see above |
| Malformed or incomplete | 1 | UF "2025 End Of Season Data Summary Fbga Fall Meeting" — borderline relevance + `empty_body`; correctly dropped before ever reaching a human reviewer (no draft created) |
| Probable duplicates | 1 | Lucentlands "Scaling the Blueberry Industry… \| Ep. 102" — exact title + published_date match against already-trusted `ev-lucentlands-scaling-blueberry-industry-2025`; flagged at discovery time, no draft created |
| Already reviewed / published / rejected / superseded | 1,272 (canonical corpus only) | 1,269 published, 3 in_review, 0 rejected/archived (see §1) |
| (not one of the 8 listed, but observed) Confidently screened irrelevant | 1 | Fruitist "Named One Of Fast Company's Most Innovative Companies of 2026" |
| (not one of the 8 listed, but observed) Reporting discrepancy | 1 | business-of-blueberries "Navigating Super El Niño… (Part 2)" reported `awaiting_publication_review`/`review_ready: true` in the batch report but produced no file under `inbox/evidence/` — flagged, not investigated further (see `PROVENANCE-GAPS.md`) |

Total accounted for: 3 + 4 + 1 + 1 + 1 + 1 = 11 rows against 10 processed
items because the "El Niño" discrepancy item is counted once as its own
anomaly row rather than double-counted into any content-state bucket
(its real content state cannot be verified since no file exists).

## Reconciliation: why diagnostic extraction produces readable bodies while the trusted corpus has zero

Restated and reconfirmed by this mission's own fresh run (see also
`artifacts/readable-acquisition-canary-v1/ROOT-CAUSE-ANALYSIS.md`, whose
findings are unchanged and were carried into the Wave 3 integration
checkpoint verbatim):

1. **The pipeline works.** `article_acquisition.fetch_article()` and the
   podcast/video acquisition path both correctly fetch and classify real
   content. This mission's own run reproduced the identical, confirmed
   permanent failure pattern for Oishii (2 independent items, both
   `navigation_only_shell`) and a real Fruitist/UF `empty_body` case each.
2. **The trusted corpus predates the pipeline.** All 1,269 published
   records were captured before body/transcript acquisition existed for
   most of them, or via a mechanism that never populates `article`/
   `transcript`.
3. **No readable draft has ever crossed mandatory human review.** Every
   draft this mission's run, the prior `readable-acquisition-canary-v1`
   run, and the earlier `astra-repair` canary produced stayed in
   `inbox/evidence/`, `status: "draft"`/`review_state: "in_review"` —
   none was ever approved via `/review/{id}/publish`.
4. Oishii's Press page template and roughly two-thirds of Fruitist's own
   CMS "news" items genuinely lack body text on the publisher's own site
   — a real, external, permanent content-availability fact, not a defect.

**No extraction or acquisition code was modified by this mission**, per
its own explicit instruction to preserve these confirmed facts.
