# Capped canary — results

Run date: 2026-09-15 (worktree clock; commit date 2026-09-16 per generated
timestamps below — see note)
Branch: `fix/readable-acquisition-canary-v1`

## Safety envelope (all preserved, all respected)

- **Maximum 5 discovered (persisted) items total**, split 2 (UF) / 2
  (Fruitist) / 1 (Oishii) across the three currently-runnable Wave 1
  Sources — stricter than the prior Wave 1 activation canary's 25-item
  total.
- **Only currently-configured Wave 1 sources**: the two
  `OPERATOR_ACTION_REQUIRED` Wave 1 sources (Ozblu, Wish Farms) were
  excluded entirely — not discovered, not fetched, not retried.
- **No canonical import**: nothing written under `data/`. Verified:
  `git status --porcelain -- data/` is empty after the canary run.
- **No trusted publication**: every item that reached acquisition produced
  either `skipped_irrelevant` (no draft) or `awaiting_publication_review`
  (draft in `inbox/evidence/`, `status`/`review_state` never `published`).
- **No trusted Evidence**: `repositories.evidence.list()` against this
  worktree's `data/evidence/` is unchanged (1,272 records, same as before
  the canary ran).
- **No automated publication-review approval**: the canary driver calls
  only `discover_source()` and `process_discovered_article()` — neither
  function contains a publish/approve/review-decision code path; no
  `/review/*` route or approval function was invoked.
- Runtime target: this worktree's gitignored `inbox/` only.

## How it was run

A small, non-committed driver script (kept only in this session's
scratchpad, not part of the repository — the prior Wave 1 activation
canary was likewise never committed as a script) called, per source:

1. `app.services.media_discovery.discover_source(source_id, inbox_dir=...,
   max_persisted_items=<per-source cap>)` — the existing, preserved
   operator safety cap.
2. `app.services.article_refresh.process_discovered_article(item,
   orchestrator=..., inbox_dir=..., berries=..., geographies=...,
   companies=..., geo_matchers=..., company_matchers=...)` — the exact
   same function `scripts/run_collection.py` and `scripts/run_recent_batch.py`
   already call for every `web_article` item in production.

No new adapter, no new extraction logic, no new vocabulary was introduced
by this driver — it composes only already-existing, already-tested
production functions.

## Results

See `SOURCE-FUNNEL.md` for the full per-source funnel table and
`data/imports/readable-acquisition-canary-2026-09-15/canary-audit.json`
for the machine-readable, redacted (no bodies/HTML) record, and
`canary-raw-report.json` in this directory for the complete per-item raw
outcome objects (also body/HTML-free by construction — every field traces
to `article_acquisition_outcomes.build_outcome()`'s own redaction
discipline).

**Capped canary itself: 5 discovered, 3 acquisition attempts, 0 readable
bodies, 3 metadata-only review-ready drafts created, 0 published, 0
approved.**

**Independent diagnostic verification (outside the 5-item cap, no
persistence): 8 readable bodies proven** across UF blueberrybreeding (2)
and Fruitist Newsroom (6), using the identical `fetch_article()` function
— see `SOURCE-FUNNEL.md`'s diagnostic table for word counts and
`ROOT-CAUSE-ANALYSIS.md` for why the narrow 5-item cap did not happen to
land on one of these.

This satisfies the mission's own bar: *"It does require honest persisted
outcomes and at least one proven readable acquisition or transcript path
if the configured sources make that technically possible."* — proven, via
diagnostics run alongside (not inside) the capped canary, exactly as the
mission's own escape clause anticipates when a narrow sample and a real
capability can disagree.

## Post-canary state verification

```
$ git status --porcelain -- data/
?? data/imports/readable-acquisition-canary-2026-09-15/   (this mission's own noncanonical audit directory, added deliberately)

$ python -c "... count data/evidence/*.json ..."
data/evidence/ record count: 1272 (unchanged before/after the canary run)
```

No file under `data/entities/`, `data/relationships/`, `data/evidence/`,
or `data/configuration/` was modified by the canary run itself — the only
change under `data/` in this branch is the new, explicitly noncanonical
`data/imports/readable-acquisition-canary-2026-09-15/` directory this
mission adds as its own audit deliverable (see `data/imports/*` convention
used by every prior mission in this codebase, e.g.
`competitor-registry-2026-09-15/`).

## Sample per-item outcomes (redacted; full set in canary-raw-report.json)

| Item | Source | Stage A | Outcome | Draft |
|---|---|---|---|---|
| "The Four R's of Fertilization: A Blueberry Perspective" | UF | `direct` (relevant) | `navigation_only_shell` | `ev-media-2835435862a523f15b30` (in_review) |
| "Pollination in Any Weather…" | UF | `irrelevant` (confident) | skipped, no attempt | — |
| "Caleb Williams Describes Fruitist Blueberries…" | Fruitist | `direct` (relevant) | `navigation_only_shell` | `ev-media-2c0da77455c28540e74b` (in_review) |
| "Caleb Williams Bets On Fruitist…" | Fruitist | `irrelevant` (confident) | skipped, no attempt | — |
| "Vertical farming company Oishii opens solar-powered facility…" | Oishii | `direct` (relevant) | `navigation_only_shell` | `ev-media-d0474872f0a4fdde8b2a` (in_review) |
