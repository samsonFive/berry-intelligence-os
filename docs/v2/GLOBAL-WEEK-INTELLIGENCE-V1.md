# Global Week Intelligence V1

**Status:** Implemented 2026-09-01. Not deployed from Cursor.

## Problem

Competitor Pulse answered “what is happening around competitor X?” from
live Google News + Perplexity, without waiting for Publication Review.
The next product-level question is industry-wide:

**What changed in the berry industry this week?**

That question must work before more secondary product features.

## Architecture

```
Industry Pulse query matrix (32) + bounded extras
        |
        v
Google News RSS (primary, parallel) + optional Perplexity catch-net
        |
        v
qualify_hit / QualificationIndex   -- REUSED
dedupe_hits                        -- REUSED
        |
        v
global_week.compose_edition()      -- editorial sections, lexicographic rank,
                                     publisher diversity cap
        |
        v
GET /week  (stakeholder shell, no fetch)
GET /week/live (LIVE / UNREVIEWED edition)
        |
        v (optional)
POST /week/review -> intake_qualified_hits()
        -> Publication draft only
        -> never Evidence / Signal / Assessment
```

Reuses, unchanged: Google News RSS, Perplexity catch-net, Industry Pulse
query model, QualificationIndex, entity/geography/berry normalization,
dedupe, Publication intake.

Does **not** add a parallel retrieval stack. Does **not** wait for trusted
Evidence. Live findings remain `LIVE / UNREVIEWED`.

## Query coverage

- Base: `generate_pulse_queries()` still 32 (4 berries × 5 geographies + 12
  global topics). Industry Pulse tests stay valid.
- Week extras (bounded): 5 local-language Google News editions (Americas
  es, Europe es, Africa fr, APAC zh, APAC ja) and 1 global retail topic.
- Catch-net: existing Americas + Africa + global topics, **plus APAC and
  local-language rows** — APAC was the known weak region.
- Windows: 24 hours / 7 days / 30 days. Default 7 days. `WINDOWS` on
  `run_pulse()` is unchanged (still 24h/3d/7d).

Google News `when:` is treated as advisory. After qualification, items whose
`published_date` falls outside the selected window, or that resolve only to a
publisher homepage, are dropped. Query geography is retrieval provenance, not
a claim that the article is about that region.

## Ranking

Deterministic lexicographic order, **not** a proprietary importance score:

1. Named competitor / cultivar / regulatory event
2. Official source
3. Specialist source
4. Distinct-publisher corroboration count
5. Count of known companies/cultivars named
6. Publication date
7. Title (stability)

Each item shows those factors as `rank_reasons`. What Matters Most also
caps any one publisher at 2 items.

## Stakeholder UI

`/week` uses `base_stakeholder.html` (PR #215 shell). Nav: **This week**,
next to Today. Hidden on the static public snapshot (`static_build`).
Send to review is authoring-only and does not approve Evidence.

## Performance

The shell paints immediately. `/week/live` runs queries in parallel
(`ThreadPoolExecutor`, cap 12). First meaningful content is the loaded
edition, not a silent recall cut.

## Known gaps (product not accepted)

Live Google News RSS on 2026-09-01 (this Cursor environment, Perplexity off):

| Window | Raw | Unique | Qualifying | In-window | Older | Latency |
|---|---:|---:|---:|---:|---:|---:|
| 24h | 1463 | 477 | 91 | 2 | 89 | 9.4s |
| 7d | 1607 | 548 | 93 | 6 | 87 | 9.4s |
| 30d | 1628 | 551 | 93 | 9 | 84 | 8.9s |

Obvious public-web misses vs a bounded manual search: Fruitnet 2026-09-01 UK blueberry +11%; Guardian 2026-08-27 UK harvest; Hortifrut–Naturipe–Mountain Blue Americas expansion; APAC (Australia–Vietnam access, China prices, Japan strawberries). In-window regional tagging is empty for all four regions on 7d because titles often omit a place name. These are documented as unresolved provider/source/date-window gaps, not hidden.

## Out of scope

- Deploy (Claude/operator)
- Auto-trust
- Translation infrastructure beyond the five edition variants above
