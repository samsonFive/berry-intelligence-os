# Source Health and Collection Cadence Baseline

**Baseline measurement date/time:** 2026-08-16, discovery pass run ~21:19-21:25 UTC.
**Scope:** the 12 Sources in `data/configuration/sources.json` that currently
carry a `discovery` block (i.e. every Source `scripts/discover_media.py`
can actually poll). The other ~120+ Sources in the registry are
`reference`-type, human-checked entries with no discovery mechanism and are
out of scope for this document.

**This is a living operational baseline, not permanent truth.** Every number
below reflects one real, conservative discovery pass against live feeds on
the stated date. Publication cadence, feed availability, and topical mix
will drift; re-run `scripts/discover_media.py --all` and update this
document rather than treating these figures as fixed.

**Method note:** this document is measurement and recommendation only. No
Source was added, removed, or reconfigured; no adapter, RSS, YouTube,
transcription, or runner code was changed; no extraction, publication
approval, or Atomic Evidence work was performed. One discovery pass per
Source was run via `scripts/discover_media.py --all` (discovery/staging
only — no transcription, no media download). No additional YouTube caption
probes were performed for this baseline; the reasoning is in Section 5.

---

## 1. Executive summary

All 12 discoverable Sources are technically healthy: 12/12 discovery passes
succeeded with zero feed-level or item-level failures. But **operational
health and topical yield are different axes**, and they diverge sharply
here. Only 3 of 12 Sources are both actively publishing *and*
berry-specific or berry-heavy in content (`source-business-of-blueberries-podcast`,
`source-redagricola-on-the-road`, `source-blueberries-tv-youtube`). A
fourth (`source-lucentlands-podcast`) is very active but only ~10%
directly berry-relevant by title/description sampling. The remaining 8
split between broad-industry sources with occasional berry content worth
periodic checking, and three sources that are either dormant (no upload
since 2015 or 2022) or nearly devoid of berry-relevant material despite an
active feed.

Recommended posture: a small Tier-1 roster of 4 Sources checked weekly, a
Tier-2 watch list of 5 Sources checked monthly, 1 Source retained at low
frequency despite weak recent signal, and 2 dormant Sources moved to
manual/watchlist status with no routine polling. This keeps the estimated
review-eligible candidate volume in the ~25-35/month range — reviewable by
a human, not a flood.

No Source in this batch demonstrates a need for a new adapter, and no
Source demonstrates a generic acquisition defect in the existing
`podcast_rss`/`youtube_feed` adapters. No source-record correction is
recommended; the one true finding — YouTube's ~15-item Atom feed ceiling
capping visibility on `source-university-of-arkansas-division-of-agriculture`
and `source-blueberries-tv-youtube` — is a documented platform limitation,
already recorded honestly in each Source's own `discovery.notes`, not a bug
or misconfiguration.

---

## 2. 12-Source inventory

| Source ID | Name | Adapter | Publisher/platform | Feed/channel identity | Enabled | Berry relevance | Hosting/feed tech |
|---|---|---|---|---|---|---|---|
| `source-lucentlands-podcast` | Lucentlands Podcast | podcast_rss | Lucentlands (South Africa) | `anchor.fm/s/c9b3aba4/podcast/rss` | yes | broad ag/produce, occasional berry | Anchor (Spotify for Podcasters) |
| `source-business-of-blueberries-podcast` | The Business of Blueberries | podcast_rss | USHBC/NABC | `feeds.captivate.fm/blueberries/` | yes | berry-specific (blueberry) | Captivate.fm |
| `source-redagricola-on-the-road` | Redagrícola On The Road | youtube_feed | Redagrícola (Chile/Peru) | 2 playlists on channel `UCz9Pxh-IpB-_AW0qp74naIw` | yes | mixed (LatAm ag, frequent blueberry) | YouTube (native, playlist Atom feeds) |
| `source-university-of-arkansas-division-of-agriculture` | Univ. of Arkansas Division of Agriculture | youtube_feed | University of Arkansas | channel `UCXV6_ND45kOoy2_T9JI-9KA` (`@AginArk`) | yes | broad extension content, occasional blackberry/blueberry | YouTube (native, channel-level, unscoped) |
| `source-comite-de-arandanos-de-chile-youtube` | Comité de Arándanos de Chile (YouTube) | youtube_feed | Chilean Blueberry Committee | channel `UCIlsT5-0R2dIjtn95dW7Irg` | yes | berry-specific (dormant) | YouTube (native, channel-level) |
| `source-the-packer-podcast` | The Packer Podcast | podcast_rss | PMG/Farm Journal | Omny playlist feed (`omnycontent.com/.../podcast.rss`) | yes | broad produce trade, occasional berry | Omny Studio |
| `source-fresh-takes-on-tech-podcast` | Fresh Takes on Tech | podcast_rss | International Fresh Produce Association | `feeds.captivate.fm/fresh-takes-on-tech/` | yes | broad ag-tech, occasional berry | Captivate.fm |
| `source-produce-buzzers-podcast` | Produce Buzzers | podcast_rss | ProduceBuzz.com | `anchor.fm/s/589c5ce0/podcast/rss` | yes | broad consumer produce, occasional berry | Anchor (Spotify for Podcasters) |
| `source-global-fresh-series-podcast` | Global Fresh Series | podcast_rss | The Produce Industry Network | `feeds.captivate.fm/global-fresh-series/` | yes | broad global produce, occasional berry | Captivate.fm |
| `source-fresh-cred-podcast` | The Fresh CrEd | podcast_rss | Ed Bertaud | `feed.podbean.com/masonhartung/feed.xml` | yes | broad produce ops, minimal berry | Podbean |
| `source-lubera-edibles-podcast` | Lubera Edibles Gardeners Radio | podcast_rss | Lubera (Switzerland) | `luberaediblesgardenersradio.podigee.io/feed/mp3` | yes | berry-specific (dormant since 2022) | Podigee |
| `source-blueberries-tv-youtube` | Blueberries TV (Blueberries Consulting) | youtube_feed | Blueberries Consulting | channel `UCwypVNJp_DjjoLtqVCwIF4w` (`@BlueberriesTV`) | yes | berry-specific (event-driven bursts) | YouTube (native, channel-level) |

All 12 are `enabled: true` in `data/configuration/sources.json` and all
resolved via publicly documented, credential-free mechanisms (iTunes
Lookup API for podcast feed resolution; YouTube's public Atom feed
endpoint for channel/playlist video listings) — see each Source's own
`discovery.notes` for the original resolution research. Nothing here was
inferred beyond what each Source's discovery config and this pass's real
fetch results show.

---

## 3. Freshness / health matrix

One real discovery pass per Source, run 2026-08-16 via
`scripts/discover_media.py --all`. All 12 succeeded (0 feed failures, 0
item failures).

| Source ID | Items visible | Newest | 2nd-newest | Oldest visible | Last 7d | Last 30d | Last 90d | Last 365d | Apparent cadence |
|---|---|---|---|---|---|---|---|---|---|
| lucentlands-podcast | 159 | 2026-08-12 | 2026-08-03 | 2022-11-22 | 1 | 6 | 19 | 59 | ~weekly, sometimes faster |
| business-of-blueberries-podcast | 200 | 2026-07-31 | 2026-07-23 | 2021-05-27 | 0 | 3 | 9 | 32 | ~every 1.5-2 weeks |
| redagricola-on-the-road | 29 | 2026-08-11 | 2026-07-22 | 2025-07-29 | 1 | 4 | 10 | 28 | ~weekly |
| university-of-arkansas-division-of-agriculture | 15 (ceiling) | 2026-08-14 | 2026-08-07 | 2026-06-04 | 1 | 3 | 15 | n/a (feed only spans ~10 weeks) | high (whole-channel, mostly non-berry) |
| comite-de-arandanos-de-chile-youtube | 8 | 2015-04-13 | 2015-02-03 | 2014-12-27 | 0 | 0 | 0 | 0 | dormant (no upload since 2015) |
| the-packer-podcast | 100 | 2026-08-13 | 2026-07-30 | 2023-03-06 | 1 | 2 | 8 | 23 | ~every 2 weeks |
| fresh-takes-on-tech-podcast | 132 | 2026-08-11 | 2026-08-04 | 2021-04-13 | 1 | 4 | 6 | 24 | ~every 1.5-2 weeks |
| produce-buzzers-podcast | 148 | 2026-07-30 | 2026-07-16 | 2021-08-30 | 0 | 1 | 5 | 22 | ~every 2-3 weeks, irregular |
| global-fresh-series-podcast | 106 | 2026-08-12 | 2026-08-05 | 2024-01-31 | 1 | 4 | 13 | 51 | ~weekly |
| fresh-cred-podcast | 100 | 2026-08-12 | 2026-08-05 | 2022-09-05 | 1 | 2 | 4 | 23 | ~every 2-3 weeks |
| lubera-edibles-podcast | 22 | 2022-04-02 | 2022-03-29 | 2021-02-01 | 0 | 0 | 0 | 0 | dormant (no upload since 2022) |
| blueberries-tv-youtube | 15 (ceiling) | 2026-07-22 | 2026-07-14 | 2026-07-11 | 0 | 1 | 15 | n/a (feed spans ~2 weeks) | bursty/event-driven (seminar-clustered) |

**YouTube ~15-item ceiling** (documented platform limitation, not a bug):
`university-of-arkansas-division-of-agriculture` and
`blueberries-tv-youtube` both hit exactly 15 items — YouTube's public
Atom feed only ever exposes the ~15 most recent uploads per channel. This
is not those channels' total inventory. `redagricola-on-the-road` (29
items across 2 playlists) and `comite-de-arandanos-de-chile-youtube` (8
items) are below the ceiling and are very likely showing their real full
inventory for those specific feeds (a narrowly-scoped playlist and a
small, long-dormant channel respectively).

**Podcast RSS pagination**: every `podcast_rss` Source here uses a single
`feed_url` pointing at the first/most-recent page (typically 100-200
items depending on host). `the-packer-podcast`'s feed is explicitly
documented as 3 pages total (this Source's `discovery.feed_url` covers
page 1/100 most recent only) — the same single-page convention every
other podcast_rss Source in this registry uses, so it is consistent
behavior, not a Source-specific limitation.

---

## 4. Topical-yield matrix

Recent-item sample (most recent 30 items, or all items where fewer than
30 exist) scanned for berry keywords (blueberry/raspberry/strawberry/
blackberry and Spanish equivalents) in title + description. Classified
per the task's five-way scale.

| Source ID | Classification | Recent berry-relevant hits | Common topic types | Intelligence value |
|---|---|---|---|---|
| business-of-blueberries-podcast | **High berry-specific** | 30/30 (100%) | competitor/company activity, retail, production geography, market dynamics, tech adoption | High — purpose-built blueberry industry show, USHBC/NABC first-party |
| blueberries-tv-youtube | **High berry-specific** | 15/15 (100%) | seminar/conference coverage, sponsor/vendor interviews, genetics, production tech | High when active — real-time seminar circuit coverage, but bursty |
| lubera-edibles-podcast | **High berry-specific** (dormant) | 11/22 (50%) | breeding/genetics, container production, varieties | Was high; now historical-only, dormant since 2022 |
| redagricola-on-the-road | **Mixed agriculture-produce** | 9/29 (31%) | grower operations, genetics, geography (Peru/Chile), technology, investment | High — consistent recurring blueberry coverage inside broader LatAm ag content |
| comite-de-arandanos-de-chile-youtube | **Mixed** (dormant) | 3/8 nominal (38%, all pre-2015) | grower training (harvest/packing) | Low now — dormant, and the two zero-caption items are confirmed non-narrative bumpers per prior Tier-3 proof |
| university-of-arkansas-division-of-agriculture | **Mixed agriculture-produce** | 4/15 (27%) | breeding/genetics feature (Amanda McWhirt), blackberry/blueberry how-to, annual Field Day | Medium — real content exists but is diluted in a broad, high-turnover Extension channel |
| produce-buzzers-podcast | **Broad industry signal** | 4/30 (13%) | consumer/retail, category features, occasional dedicated berry episode | Medium-low — consumer-demand angle, sparse but real (e.g. "The Strawberry Queen" episode) |
| global-fresh-series-podcast | **Broad industry signal** | 8/106 full-feed (8%) | trade/import volume, consumption trends, occasional dedicated blueberry episode | Medium-low — named blueberry episodes exist but cluster in 2024-2025, not recently |
| lucentlands-podcast | **Broad industry signal** | 3/30 (10%) | breeding/genetics, market access, consumer demand, South African fruit broadly | Medium — high volume compensates somewhat for low per-episode berry density |
| the-packer-podcast | **Broad industry signal** | 1/30 recent (3%; 1 explicit blueberry-marketing episode on record) | trade policy, supply chain, marketing | Medium-low — broad produce trade press, occasional direct berry hit |
| fresh-takes-on-tech-podcast | **Broad industry signal** | 1/30 (3%) | ag-tech, traceability, automation | Low-medium — technology-adoption angle valuable when it lands on berries, rare |
| fresh-cred-podcast | **Low-current relevance** | 1/100 full-feed (1%) | freight, pricing, sourcing, operator perspective | Low — broadest produce-ops focus in the batch, weakest confirmed berry tie despite active, current publishing |

A source may legitimately be low-yield: `fresh-cred-podcast` publishes
actively and reliably but returned only one berry-keyword hit across its
entire visible 100-episode history. That is a real finding, not a
measurement gap — its focus (freight, pricing pressure, sourcing) simply
sits adjacent to, not inside, berry-specific intelligence.

---

## 5. Acquisition-cost matrix

**Podcast RSS (8 Sources):** all 8 have 100% enclosure/audio availability
(verified directly from this pass's staged item metadata — every item in
every podcast_rss Source's feed carries a resolvable audio enclosure URL).
Publisher-declared transcripts (`<podcast:transcript>` tag) are essentially
absent: `fresh-takes-on-tech-podcast` is the only Source with any declared
publisher transcripts (16/132 items, ~12%); all other 7 podcast_rss
Sources report `not_detected` on every item. That makes local Whisper
(Tier 3) the default acquisition path for nearly all podcast content in
this registry, not an occasional fallback.

| Source ID | Avg. episode duration | Publisher transcript coverage | Resource cost |
|---|---|---|---|
| lucentlands-podcast | 55.3 min | 0% | **HIGH** — this Source's own pilot episode is the project's real >70-minute local-Whisper grounding data point |
| produce-buzzers-podcast | 50.9 min | 0% | **HIGH** — longest average runtime after Lucentlands |
| business-of-blueberries-podcast | 34.4 min | 0% | MEDIUM-HIGH |
| fresh-takes-on-tech-podcast | 33.1 min | ~12% | MEDIUM — partial publisher-transcript coverage reduces but does not eliminate Whisper need |
| fresh-cred-podcast | 28.8 min | 0% | MEDIUM |
| the-packer-podcast | 27.7 min | 0% | MEDIUM |
| global-fresh-series-podcast | 27.2 min | 0% | MEDIUM |
| lubera-edibles-podcast | 17.5 min | 0% | LOW-MEDIUM (dormant — cost is moot until/unless it resumes) |

Cost estimates scale roughly with duration given the real ratio observed
in this project's prior pilot (>70 CPU-minutes for one long Lucentlands
episode on this hardware); shorter shows are not free but are
meaningfully cheaper per episode. No new transcription was run to produce
this table — durations are read directly from each feed's own
`itunes:duration` tag, and the Whisper-cost grounding reuses the existing,
already-documented Lucentlands pilot result rather than re-running it.

**YouTube (4 Sources):** `transcript_availability.status` is architecturally
`"unknown"` for every YouTube item discovered by this project's
`youtube_feed` adapter — confirmed by reading
`app/services/media_discovery.py`'s `_detect_youtube_transcript_availability()`,
which documents that YouTube's public Atom feed carries no caption signal
at all (unlike podcast RSS's `<podcast:transcript>` tag), so `"unknown"` is
the only honest value it can report without a separate, per-video page
fetch. This pass did **not** perform a new caption-inspection call against
any of the four YouTube Sources: the existing real evidence already on
record (the Tier-3 Whisper proof against `source-comite-de-arandanos-de-chile-youtube`,
which live-inspected all 8 of that channel's videos and additionally
audited ~160 real videos across 20+ other first-party agriculture/berry
channels in 6 languages) already established that YouTube's automatic
caption (ASR) coverage is comprehensive for genuinely narrated content in
every language checked, and that zero-caption videos are rare and, when
found, tend to be non-narrative (music-only bumpers). Given that existing,
broader evidence directly answers Step 4's question, adding new
per-Source caption probes here would be exactly the unnecessary
YouTube-hammering this task's network discipline instructs against, so
none were made.

| Source ID | Direct caption evidence | Likely Tier-3 fallback frequency | Resource cost |
|---|---|---|---|
| comite-de-arandanos-de-chile-youtube | Real: 6/8 videos have es-orig auto-captions (Tier 2 sufficient); 2/8 have zero captions and are confirmed non-narrative bumpers (Tier 3 reached, correctly produced no transcript) | Low, and the two known Tier-3 triggers on this channel produce no content anyway | LOW (dormant; when it was active, mostly Tier-2) |
| redagricola-on-the-road | Inferred from the broader cross-channel audit (Spanish-language content included in that audit) | Likely low | LOW-MEDIUM |
| university-of-arkansas-division-of-agriculture | Inferred (English-language, university extension channel, similar profile to audited channels) | Likely low | LOW-MEDIUM |
| blueberries-tv-youtube | Inferred (mixed Spanish/English seminar content) | Likely low | LOW-MEDIUM |

---

## 6. Health classification

| Classification | Sources | Basis |
|---|---|---|
| **GREEN** | business-of-blueberries-podcast, redagricola-on-the-road, blueberries-tv-youtube | Recent publishing, berry-specific or berry-heavy relevant signal, normal acquisition path (audio/captions available) |
| **YELLOW** | lucentlands-podcast, university-of-arkansas-division-of-agriculture, the-packer-podcast, fresh-takes-on-tech-podcast, produce-buzzers-podcast, global-fresh-series-podcast | Active and useful, but mixed/broad relevance, irregular cadence, likely Whisper-dependent, and/or (Arkansas) a platform-limited, high-turnover channel |
| **RED** | fresh-cred-podcast, comite-de-arandanos-de-chile-youtube, lubera-edibles-podcast | fresh-cred: active feed but content no longer/rarely CI-aligned (1% hit rate). The other two: no upload since 2015 / 2022 respectively — feeds apparently abandoned, not access failures |

RED here does **not** mean delete — per this task's own definition, it
means collect less often (or not on a routine schedule at all). All three
RED Sources remain configured and enabled; none are recommended for
removal.

---

## 7. Recommended collection cadence

| Tier | Cadence | Sources | Rationale |
|---|---|---|---|
| **Tier 1** | Weekly | business-of-blueberries-podcast, redagricola-on-the-road, blueberries-tv-youtube, lucentlands-podcast | The 3 GREEN Sources plus Lucentlands (highest volume in the registry, `monitoring_priority: high` in its own config, and still produces genuine berry-relevant episodes periodically even at ~10% direct hit rate) |
| **Tier 2** | Monthly | university-of-arkansas-division-of-agriculture, the-packer-podcast, fresh-takes-on-tech-podcast, global-fresh-series-podcast, produce-buzzers-podcast | Active, real cadence of roughly 1 item every 1.5-3 weeks each; checking weekly would mostly find nothing new given that pace, so monthly matches real publish rhythm without missing material |
| **Tier 3** | Monthly (retain, low expectation) | fresh-cred-podcast | Active feed, weak berry signal (1%); retained rather than dropped per this task's own instruction not to force value where there isn't any, but not worth a tighter cadence |
| **Tier 4** | Manual/watchlist, no routine collection | comite-de-arandanos-de-chile-youtube, lubera-edibles-podcast | Both dormant (2015 / 2022 respectively); a routine discovery run against either is expected to report 0 new items indefinitely, which is correct adapter behavior, not something worth spending scheduled runs on. Revisit manually if either publisher resumes |

**Note on "daily" cadence:** none of these 12 Sources publish more than
roughly once every 3-5 days at peak (Lucentlands' fastest recent
interval). No Source in this registry justifies a literal daily/weekday
check — doing so would mostly poll empty feeds. "Tier 1" here is
therefore mapped to **weekly**, the fastest cadence any real publish
rhythm in this batch actually supports; see Architecture finding (6)
below for the explicit reasoning.

---

## 8. Expected review workload (recommended roster)

Assumptions: "candidates" = newly discovered items staged by
`discover_source()`, the earliest measurable unit in this pipeline (before
transcription/extraction/draft-generation, which are separately gated and
not all discovered items will necessarily reach that stage). Figures use
each Source's real 30-day discovered-item count from this pass as the
per-period estimate.

**Tier 1 (weekly checks, 4 sources):**
- business-of-blueberries-podcast: ~3/month (~0.7/week)
- redagricola-on-the-road: ~4/month (~0.9/week)
- blueberries-tv-youtube: ~1/month on average, but bursty — a single
  seminar week can stage 10+ items at once, followed by weeks of zero
- lucentlands-podcast: ~6/month (~1.4/week)
- **Tier 1 subtotal: ~4/week average, ~14/month** (with occasional
  Blueberries TV burst weeks pushing a single week's count well above
  average)

**Tier 2 (monthly checks, 5 sources):**
- university-of-arkansas-division-of-agriculture: ~3/month
- the-packer-podcast: ~2/month
- fresh-takes-on-tech-podcast: ~4/month
- global-fresh-series-podcast: ~4/month
- produce-buzzers-podcast: ~1/month
- **Tier 2 subtotal: ~14/month**

**Tier 3 (monthly check, 1 source):**
- fresh-cred-podcast: ~2/month

**Total recommended-roster volume: roughly 30 candidates/month
(~7/week average),** unevenly distributed — Tier-1 weekly checks supply a
steady ~4/week trickle, while Tier-2/3 monthly checks each land as a
once-a-month batch of ~16 combined. This is not all "berry-relevant"
content: per Section 4's topical-yield rates, only a fraction of these
(highest for the Tier-1 GREEN sources, lowest for fresh-cred) will
actually carry berry-specific intelligence value once reviewed — the
review-eligible volume is a ceiling, not a guarantee that every candidate
is worth a human's time. That said, ~30/month (~1/day average) is a
genuinely reviewable volume for a human reviewer, consistent with this
task's instruction not to recommend generating more drafts than can
realistically be reviewed.

---

## 9. Operational failure guidance

Per `docs/v2/RECURRING-COLLECTION-RUNNER.md` (read in full for this
baseline) and this pass's own real results (0 failures of any kind across
all 12 Sources), the runner's existing retry/failure semantics already
cover every case below. No new state machine is proposed.

- **RSS temporarily unavailable:** a feed-level failure on one Source
  never stops other Sources in the same `--all` run (`discover_media.py`'s
  own design, confirmed by this pass's per-source independent reporting).
  Retryable by default; no operator action needed unless it recurs across
  multiple consecutive scheduled runs, at which point treat it as a
  possible publisher-side outage and check the feed URL manually.
- **Malformed feed item:** captured as an item-level failure
  (`result.item_failures`), reported per-item with index/identifier/error;
  does not block other items in the same feed or other Sources. This pass
  saw zero item-level failures across all 1,034 staged items, so no
  malformed-item handling was exercised live in this baseline — rely on
  the documented behavior above.
- **YouTube caption unavailable:** expected, routine — this is exactly
  the Tier 2 -> Tier 3 fallback path (`fetch_captions()` returns nothing
  usable, `acquire_youtube_audio()` + local Whisper takes over). Not an
  error condition by itself.
- **YouTube Tier-3 bot/access challenge:** follow
  `RECURRING-COLLECTION-RUNNER.md`'s "YouTube platform-access challenges"
  section verbatim — the item is classified `failure_class: retryable`
  with bounded backoff automatically, escalating to `failure_class:
  operator` only after `--retry-limit` (default 3) attempts. Documented
  guidance if it persists: re-run later (this class of challenge is
  commonly transient/IP-reputation-scoped); do not add cookie/session
  support speculatively; the existing single observed occurrence in this
  project's real-network history is treated as expected background noise.
  This baseline pass triggered zero such challenges across 4 YouTube
  Sources / 67 items.
- **Local Whisper failure:** not exercised in this discovery-only pass
  (this task explicitly did not run Whisper). Per the runner's documented
  behavior and the prior Tier-3 proof, a genuine no-speech/decode failure
  is correctly treated as a `TranscriptionError`, not a malformed
  transcript — no operator action beyond the runner's existing retry
  handling.
- **Dormant Source:** for `comite-de-arandanos-de-chile-youtube` and
  `lubera-edibles-podcast`, the correct operator behavior is exactly what
  Tier 4 above recommends — stop routine polling, leave the Source
  configured and enabled, and check back manually on a much longer
  horizon (e.g. opportunistically, not on any schedule) in case the
  publisher resumes. A discovery run against a dormant feed reporting 0
  new items is correct, expected behavior, not a fault.

---

## 10. Baseline measurement record

- **Date/time:** 2026-08-16, ~21:19-21:25 UTC
- **Command:** `python scripts/discover_media.py --all` (worktree:
  `berry-intelligence-os-source-health-baseline`, branch
  `ops/source-health-baseline`, based on `5d26571`)
- **Result:** 12/12 Sources succeeded; 0 feed-level failures; 0
  item-level failures; 1,034 total items staged across all 12 Sources'
  feeds (159+200+29+15+8+100+132+148+106+100+22+15)
- **No transcription, no media download, no caption probes** were
  performed as part of this baseline (see Section 5 for the caption-probe
  reasoning)
- **No Source configuration was modified.** No factual/configuration
  defect was found in any of the 12 Sources' `discovery` blocks during
  this pass.

Re-run this same command and refresh this document (or generate a
successor) whenever this baseline needs updating — it is intentionally a
snapshot, not a permanent classification.
