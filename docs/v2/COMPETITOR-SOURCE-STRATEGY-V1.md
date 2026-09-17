# Competitor Source Strategy V1

**Status:** Research and import-planning only. No live Source records were
created, no collection was run, and no canonical entity/relationship/tier/
priority/region data was changed. Every artifact this mission produced is
either documentation or a noncanonical import-proposal file under
`data/imports/competitor-source-strategy-2026-09-15/`.

**Branch:** `research/competitor-source-strategy-v1`
**Base:** `4e54401da040be937cc68877f410b4da7b646d65` (Company + Genetics
Relationships V1's completed checkpoint)
**Verification date:** 2026-09-15

## 1. Product problem this mission addresses

The prior mission reconciled all 33 roster companies into the entity graph
(33/33 represented) but left monitoring coverage almost entirely unbuilt:
0 linked active sources, 8 configured-but-never-run, 1 known-blocked, 24
with no supported source strategy at all. **Entity representation is not
monitoring** — a company can be a real, searchable, tier-classified entity
in this graph and still have zero real news reaching it. This mission's
job was to determine, through real public-web verification (not
fabrication), a realistic discovery strategy for every one of the 33 — even
where that strategy is honestly "we could not find one."

## 2. Where the data lives

```
data/imports/competitor-source-strategy-2026-09-15/
  competitor-source-strategy-v1.json      -- the full 33-row machine-readable contract
  competitor-source-strategy-matrix.md    -- the same data, human-readable
  candidate-source-import-proposal.json   -- 21 NONCANONICAL Source-shaped proposals
  first-activation-wave.json              -- the 12-entry bounded recommendation
  duplicate-risk-assessment.json          -- 6 named risk categories
  adapter-gap-analysis.json               -- adapter sufficiency + access-limitation findings

docs/v2/COMPETITOR-SOURCE-STRATEGY-V1.md  -- this document
artifacts/competitor-source-strategy-v1/  -- checkpoint, continuation prompt, validation output
scripts/_gen_competitor_source_strategy_v1.py -- the (kept, documented, non-runtime) generator
tests/test_competitor_source_strategy_v1.py   -- deterministic validation
```

Every row in `competitor-source-strategy-v1.json` is keyed by the
**existing** `canonical_entity_id` from
`data/imports/competitor-registry-2026-09-15/reconciliation-matrix.json` —
read, never re-derived. This mission changed no tier, priority, region,
alias, or entity/relationship record from the prior mission.

## 3. Research method

For each of the 33 roster labels: a targeted public web search for the
official domain and newsroom/press/blog section, followed by a direct
`curl` check (same honest, declared User-Agent this project's own
`article_acquisition.py` uses — `berry-intelligence-os-article-acquisition/1.0`
— never a spoofed browser identity) of `robots.txt`, the homepage, and
likely feed/sitemap paths. This is **verification, not collection**: no
article bodies were fetched, no bulk crawl was run, and a `200` on a feed
URL is reported as "a feed exists and is reachable to this client," never
as "this source is already producing usable intelligence."

**19 of 33 domains were confirmed with a real, live discovery mechanism**
(RSS/Atom feed or XML sitemap, `HTTP 200` to this project's own client).
**4 had no official website findable at all** after two search passes each
(Denning Blueberries, Expoberries, Marionnet, Splendor Produce) — reported
honestly as `identity_search_strategy_pending`, not guessed at. The
remaining 10 are either already-configured (8, from the prior mission's own
audit) or have a domain but an unresolved/unconfirmed discovery path
(Black Venture Farm, Royakkers) or a genuine access limitation (California
Giant, UC Davis, Well-Pict — see §5 and the adapter-gap analysis).

## 4. Maturity vs. monitoring state — kept deliberately separate

Per the mission's own instruction, **source maturity** (is a URL a real,
technically-reachable candidate) and **monitoring state** (what would
actually happen if collection ran today) are tracked as two different
fields on every row, never collapsed:

- `candidate_sources[].maturity` — one of: `candidate_identified`,
  `discovery_mechanism_understood`, `compatible_with_existing_adapter`,
  `requires_new_adapter`, `configured_but_untested`, `known_runnable`,
  `known_blocked`, `manual_monitoring_required`, `unsupported`,
  `identity_search_strategy_pending`.
- `recommended_initial_monitoring_state` — one of the same six states the
  prior mission's `competitor_registry.py` already uses:
  `linked_to_runnable_source`, `source_configured_never_run`,
  `source_blocked`, `discovery_pending`, `no_supported_source`,
  `manual_monitoring_required`.

**No row claims `linked_to_runnable_source` or `known_runnable` for a
candidate this mission only found via search and a single `curl` check.**
A confirmed-live feed is `discovery_pending` (technically ready, not yet
onboarded/run) — `known_runnable`/`linked_to_runnable_source` is reserved
for a Source that has actually been configured and successfully run,
which this mission deliberately did not do to any of them.

## 5. California Giant — alternative-coverage assessment

This is a re-citation of already-diagnosed, real findings from the
`fix/astra-news-reader` branch (commit `721a20a`), not a re-investigation —
re-running the same diagnostic would not produce new information and this
mission's own scope is research/planning, not acquisition engineering.

- **Official newsroom discovery:** calgiant.com has a real, discoverable
  newsroom. `robots.txt` explicitly permits all crawling (`Disallow:`
  empty) and declares a working Yoast sitemap
  (`sitemap_index.xml` → `cpt_cg_news-sitemap.xml`) listing real,
  dated newsroom article URLs, including several stories not captured
  anywhere else in this system.
- **Direct article-body access:** **blocked.** Both the sitemap and
  individual `/newsroom/` article pages return **HTTP 403** to this
  project's `httpx`-based fetcher.
- **Known HTTP 403 / bot-management behavior:** confirmed via a direct
  A/B test — the identical URL and identical User-Agent string succeed via
  `curl` and fail via `httpx`. This is a **TLS/HTTP-client fingerprint
  block** (Cloudflare bot management), not a robots.txt restriction, not a
  credential wall, and not something a URL-level workaround fixes.
- **Permitted sitemap discovery:** yes, in principle (robots.txt allows
  it) — but blocked in practice by the same fingerprint issue, so it is
  not currently a usable discovery path with this project's client.
- **Alternative primary sources:** none — Cal Giant is the only primary
  source for its own announcements; there is no second "official" channel.
- **Trade-publication coverage:** real and substantial. Historical
  captures already in this graph show AndNowUKnow, The Packer, FreshPlaza,
  Perishable News, Fruitnet, and bluebookservices.com all covering Cal
  Giant over the years — several of these publishers are NOT themselves
  bot-blocked to this project's client (FreshPlaza and Perishable News
  were proven live-reachable on `fix/astra-news-reader`). Trade-press
  coverage is a genuine, if indirect and syndication-lagged, alternative
  channel — not equivalent to the company's own newsroom, but real.
- **Manual-monitoring options:** an analyst can browse calgiant.com
  directly in a normal browser (the block is client-specific, not a
  general public access restriction) and manually stage any newsworthy
  item through the existing intake pipeline.

**Recommendation:** keep California Giant's monitoring state as
`source_blocked`, honestly. Do **not** attempt to bypass, disguise, or
weaken this project's HTTP client to defeat the fingerprint block — that
would cross from honest diagnosis into bot-detection evasion, which this
mission's own instructions and this codebase's established ethos
("report a wall honestly, never work around it") both rule out. The
correct, bounded next step (not performed in this mission) is either (a)
onboard one or two of the confirmed-reachable trade publishers as
company-scoped `news_search_rss` Sources targeting "California Giant," or
(b) flag calgiant.com for manual monitoring pending a genuine, deliberate
policy decision about this project's HTTP client identity — never claim a
trade-press Source "monitors California Giant" unless its query is
actually scoped to that company by name.

## 6. First activation wave (12 entries — see `first-activation-wave.json`)

**Tier A — zero new work, already configured, never run (8):** Advanced
Berry Breeding, BerryWorld, Costa, Fall Creek, Hortifrut Genetica, Planasa,
University of Arkansas, University of Florida.

**Tier B — newly researched, highest confidence (4):** Wish Farms (fully
permissive robots.txt, confirmed-live newsroom feed), Ozblu (fully
permissive robots.txt, confirmed-live news feed, multi-region blueberry
brand), Oishii (confirmed-live press Atom feed, high strategic interest as
a fast-growing indoor-strawberry innovator), Fruitist (confirmed sitemap,
extensive real trade-press corroboration of its $1B rebrand from
Agrovision — the single highest strategic-importance new candidate this
mission found).

**Explicitly held back from the first wave** despite technical readiness:
The Berry Collective (identity ambiguity — see duplicate-risk assessment),
and 5 more high-confidence-but-not-yet-prioritized candidates (AgroBerries,
Gem-Pack Berries, Perfection Fresh, Smart Berries, SunBelle) deliberately
deferred to a second wave to keep this recommendation bounded per the
mission's own "approximately 8–12" instruction, not because they are
low-quality — see `first-activation-wave.json`'s sibling rows tagged
`wave_2_candidate` in the full contract.

## 7. What this mission explicitly did not do

- Did not create, edit, or delete any file under `data/configuration/sources.json`.
- Did not run `scripts/run_collection.py`, `scripts/ingest_articles.py`, or
  any other acquisition/collection code.
- Did not change any entity, relationship, Evidence, tier, priority,
  region, or alias record from the prior mission.
- Did not create any Variety entity or relationship.
- Did not attempt to bypass, disguise, or weaken this project's collection
  client against any observed access restriction.
- Did not store any credential, session token, or secret.
- Did not perform broad scraping — each domain received a small, bounded
  number of `curl` checks (robots.txt, homepage, one or two guessed
  feed/sitemap paths), never a crawl.
