# Continue Competitor Source Strategy work — controlled activation

Work in `C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-competitor-source-strategy-v1`,
branch `research/competitor-source-strategy-v1`. Read
`artifacts/competitor-source-strategy-v1/CHECKPOINT.md` first. Do not
re-run the web research from scratch — 33/33 roster coverage is settled.

This branch is research/planning only. **Actually registering a live
Source or running collection is a different, separately-authorized
mission** — do not do either here without explicit new instruction, and
if authorized, strongly consider doing it on its own branch (e.g.
`integration/competitor-intelligence-v1`, already referenced by this
mission's own exclusion list) rather than this one, to keep "research" and
"activation" as separately reviewable, separately revertible checkpoints.

## Settled facts — do not re-derive

1. 33/33 roster rows have an explicit strategy or explicit unresolved
   state; 0 silently omitted. See `data/imports/competitor-source-strategy-2026-09-15/`.
2. 21 candidate sources verified live (`HTTP 200` feed or sitemap,
   permissive-enough robots.txt) across 19 companies, all fitting the
   existing `article_rss`/`sitemap_xml` adapters — no new adapter needed.
3. 5 companies (Denning Blueberries, Expoberries, Marionnet, Splendor
   Produce, IQ Berries) have no confirmed automated discovery path after
   real search effort — manual monitoring only, honestly reported, not a
   gap to keep chasing without new evidence.
4. California Giant: TLS-fingerprint blocked (re-cited from
   `fix/astra-news-reader`, commit 721a20a) — do not attempt a workaround.
   UC Davis: HTTP 403 confirmed twice, not yet root-caused (no A/B test
   run) — a real next step, not done here.
5. First activation wave (12): 8 already-configured-never-run + Wish
   Farms, Ozblu, Oishii, Fruitist. The Berry Collective is explicitly
   withheld (identity ambiguity) despite being technically ready.
6. 23 focused tests pass, `scripts/validate_records.py` passes, no
   canonical entity/relationship/Source data was touched.

## Next concrete steps, in order

1. Get explicit human sign-off on which of the 12 first-wave entries to
   actually activate, and on the specific unresolved questions flagged
   for Mountain Blue (Content-Signal robots.txt policy), UC Davis (access
   re-diagnosis), Well-Pict (connectivity retry), and The Berry Collective
   (identity confirmation).
2. Only after sign-off, on a separate branch/mission: register real
   Source records (through this codebase's existing governance — see
   AGENTS.md's Source Coverage Gap Closure V1 precedent for the expected
   discipline: every new Source carries a real `discovery.adapter` block,
   never the legacy bare `type:rss/keyword` path) and, separately again,
   decide whether/when to actually run collection against them.
3. If the entity-identity-integrity workstream picks up the possible
   AgroBerries/BerryWorld and Gem-Pack/Well-Pict corporate-affiliation
   findings noted in `duplicate-risk-assessment.json`, that is real,
   separate identity work — not something to resolve by editing Source
   strategy alone.
4. Do not silently promote any `no_supported_source` entity to a stronger
   state without new, real, cited evidence.

## Runtime / housekeeping

Use `../berry-intelligence-os/.venv/Scripts/python.exe`. Git needs
`-c safe.directory=C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-competitor-source-strategy-v1`
per command. `scripts/_gen_competitor_source_strategy_v1.py` is a one-time,
kept generator (not runtime) — re-running it overwrites its own output
files idempotently but does not touch anything else.
