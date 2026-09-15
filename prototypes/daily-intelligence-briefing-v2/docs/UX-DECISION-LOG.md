# Daily Intelligence Briefing V2 — UX decision log

## Problem framing

Existing surfaces (Morning Brief, Live Intelligence, review queues, Source Health, Landscape) answer adjacent questions with inconsistent hierarchy. Stakeholders need one briefing that answers:

> What changed, why does it matter, and what needs my attention today?

## Decisions

1. **Four-zone hierarchy, not equal cards**
   - What Changed (intelligence)
   - Why It Matters (decision implications)
   - Needs Attention (review + ops failures)
   - Coverage Pulse (operational coverage)
   - Unknown-date appendix (exceptions)

2. **Publication recency bands are explicit**
   - 0–30 / 31–60 / 61–90 / older / unknown
   - Capture date is always secondary metadata
   - Unknown dates never lead

3. **Content honesty over completeness**
   - Consent pages, bot walls, empty bodies stay in Needs Attention
   - No summaries for unreadable content
   - Historical context is labeled and demoted

4. **In-app reader is primary inspection**
   - Preserves briefing scroll/filter state via `?reader=`
   - External source is secondary
   - Escape / close returns focus to trigger

5. **Landscape remains the competitor roster handoff**
   - Briefing cards deep-link with berry/region/tier/focus query state
   - Briefing does not reinvent landscape scoring

6. **One visual family with Competitor Landscape V1**
   - Warm paper canvas, navy rail, amber accent, strong section hierarchy
   - Status uses text + badge + optional color (never color alone)
   - Sticky section nav + density toggle for scan vs detail

7. **Prototype isolation**
   - All assets under `prototypes/daily-intelligence-briefing-v2/`
   - No production route / template / acquisition changes
   - Fixture-backed only; no live inbox reads

## Rejected alternatives

- Merging ops failures into What Changed (creates false currency)
- Using capture date as “freshness”
- Auto-writing implications from unreadable pages
- Building a separate genetics browser inside the briefing
