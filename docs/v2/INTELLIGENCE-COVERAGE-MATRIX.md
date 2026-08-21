# Intelligence OS — Coverage Matrix (V2)

**Status:** Live map of real coverage, not a plan. Every number below is a direct count against `data/` and `data/configuration/sources.json` as of the date in the row/section — re-derivable at any time with the queries in "How this was measured," never hand-maintained guesswork. The point: expansion decisions (which berry, which geography, which source class to prioritize next) should read this matrix first, not rely on whoever happens to remember the last few missions' findings.

**Last measured:** 2026-08-20, canonical base `a3d1184` (before the Story Thread Subject-Attribution fix, which changed no data).

---

## 1. Berry × entity-type depth

| | Blueberry | Strawberry | Raspberry | Blackberry |
|---|---:|---:|---:|---:|
| Companies | 36 | 11 | 12 (11 real, 1 fixture) | 7 |
| Breeding programs | 9 | 3 | 1 | 0 |
| Varieties | 41 | 5 | 12 (11 real, 1 fixture) | 0 |
| Evidence | 484 | 291 | 191 | 145 |
| Patent entities (trusted) | 37 | 0 | 0 | 0 |
| Cross-berry companies (touching this berry) | 7 | 7 | 7 | 4 |

**Reading this row by row:** Blueberry is the only berry with real, review-promoted patent entities and a deep variety catalog — the original reference vertical, four missions deep. Strawberry and Raspberry each have real company/variety depth built specifically (Strawberry: Nova Siri Genetics, CIV, Eurosemillas, Rijk Zwaan, Freshuelva, Planasa's RedSayra; Raspberry: Cornell, Advanced Berry Breeding's full 7-variety list, Wish Farms, Global Plant Genetics, Berrytech, Chambers), each requiring less code work than the last (Strawberry needed one relevance-language fix; Raspberry needed zero). Blackberry has real, evidence-backed *company* presence (Plant Sciences Genetics, University of Arkansas, Driscoll's, Wish Farms all already carry blackberry in their `berry_ids`) but **zero dedicated variety/breeding-program entities** — the one berry not yet given its own depth mission.

---

## 2. Berry × source coverage

| | Blueberry | Strawberry | Raspberry | Blackberry |
|---|---:|---:|---:|---:|
| Total tagged sources (of 142) | 89 | 68 | 62 | 63 |
| Discoverable (real `discovery.adapter`, of 24) | 20 | 14 | 13 | 12 |

Every berry already has real, live-verified RSS coverage — the acquisition layer was never the bottleneck for any of the three depth missions; the entity graph was. 3 discoverable sources are berry-unscoped/generic (Blue Book Services, HortiDaily, SanLucar Newsroom) and count toward none of the four columns above but feed real cross-berry discovery for all of them.

**Known gaps** (see `TECHNICAL-DEBT-REGISTER.md` for the live-tracked versions): Growing Produce – Berries returned 403 during the Strawberry mission (TD-ACQ-002); NARBA (raspberry+blackberry association) has a real, well-formed feed with zero current items (TD-ACQ-003) — the single most obviously-relevant not-yet-useful source for Blackberry depth work, worth re-checking first.

---

## 3. Geography coverage (source `region_coverage`, all berries combined)

| Region | Sources tagged |
|---|---:|
| Global | 65 |
| North America | 58 |
| South America | 23 |
| Europe | 23 |
| Asia-Pacific | 14 |
| Africa | 7 |

North America and Europe dominate real per-company/per-variety Evidence depth (matches the real breeder geography found across all three vertical missions: US public breeding programs, Dutch/Italian/Spanish commercial breeders). Africa's 7 sources are almost entirely Morocco-focused blueberry/raspberry export coverage (a real, large, mostly generic/multi-berry Evidence cluster — see the multi-berry portability audit's note on loosely-tagged Morocco articles). No Asian domestic-market breeder source has been onboarded yet; Chinese strawberry-production coverage exists only via general trade press (Hortidaily, Produce Report), never a Chinese-language first-party source.

---

## 4. Patent Monitor recall (Google Patents JSON provider, per-berry `plant_named` query)

| | Blueberry | Strawberry | Raspberry | Blackberry |
|---|---:|---:|---:|---:|
| Provider hits (most recent real run) | 55 | 80 | 26 | 15 |
| Kept (per-query cap) | 15 | 15 | 15 | 15 |
| Trusted patent entities curated | 37 (cumulative, prior missions) | 0 | 0 | 0 |

The watchlist (`data/configuration/patent_watchlist.json`) is symmetric across all four berries by design — no berry-specific patent silo. What's uneven is *curation*: Blueberry's 37 trusted patent entities accumulated across several earlier missions' human-review passes; Strawberry, Raspberry, and Blackberry each have real, well-linked drafts sitting in `inbox/evidence/` (15 apiece from the most recent run) that have never been through that same review step. This is a real, honest backlog, not a recall problem — the pipeline works identically for all four (see the Raspberry Vertical V1 mission's manual inspection of 5 real drafts: 4/15 auto-linked with zero code changes).

---

## 5. Capability maturity × berry

Per `INTELLIGENCE-EXPANSION-BUILD-GUIDE.md` Section 17. Status vocabulary: NONE / PILOT / PARTIAL / OPERATIONAL / STRONG. "Operational" does not imply comprehensive coverage — it means the capability works and produces real Evidence today, not that recall against it has been benchmarked (that benchmarking is Workstream A's own job, not this matrix's).

| Capability | Blueberry | Strawberry | Raspberry | Blackberry |
|---|---|---|---|---|
| Trade press | STRONG | OPERATIONAL | OPERATIONAL | PARTIAL |
| Mainstream news | NONE | NONE | NONE | NONE |
| Company newsrooms | STRONG | OPERATIONAL | PARTIAL | NONE |
| Regulatory | NONE | NONE | NONE | NONE |
| Patents (US) | STRONG (37 trusted) | PARTIAL (15 drafts, 0 promoted) | PARTIAL (15 drafts, 0 promoted) | PARTIAL (drafts exist, 0 promoted) |
| PVR / rights registries (non-US) | NONE | NONE | NONE | NONE |
| Variety knowledge | STRONG | PARTIAL | PARTIAL | NONE |
| Retail observations | NONE | NONE | NONE | NONE |
| Insider newsletters | NONE | NONE | NONE | NONE |
| Jobs / careers | NONE | NONE | NONE | NONE |
| Conferences | NONE | NONE | NONE | NONE |
| Customs / trade data (structured) | NONE | NONE | NONE | NONE |
| Weather / climate | NONE | NONE | NONE | NONE |
| Satellite | NONE | NONE | NONE | NONE |

**Reading this table:** every "NONE" row is NONE across *all four* berries, not a berry-specific gap — these are the real Workstream B/D/E/F/G targets from the build guide, none started yet. Trade press, company newsrooms, patents, and variety knowledge are the only capability classes with any real coverage today, and even those are uneven across berries (Blackberry has real trade-press and patent-draft coverage but zero dedicated variety entities or newsroom source, per Section 1 above).

---

## 6. How this was measured (re-run these to refresh this document)

```python
import json, glob
from collections import Counter

def dist(pattern):
    c = Counter()
    for fp in glob.glob(pattern):
        with open(fp, encoding="utf-8") as f:
            rec = json.load(f)
        for b in (rec.get("berry_ids") or []):
            c[b] += 1
    return c

for pattern in [
    "data/entities/companies/*.json", "data/entities/breeding_programs/*.json",
    "data/entities/varieties/*.json", "data/evidence/*.json",
    "data/entities/patents/*.json",
]:
    print(pattern, dist(pattern))

with open("data/configuration/sources.json", encoding="utf-8") as f:
    srcs = json.load(f)
berries = ["berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry"]
for b in berries:
    print(b, sum(1 for s in srcs if b in (s.get("berry_ids") or [])))
```

Cross-berry-company and region-coverage counts use the same pattern against `data/entities/companies/*.json`'s `berry_ids` (companies with `len(berry_ids) >= 2`) and `data/configuration/sources.json`'s `region_coverage` field respectively — see the individual mission reports (Multi-Berry Portability Audit, Strawberry/Raspberry Vertical V1) for the exact one-off scripts used.

---

## Updating this document

Re-run the queries above at the end of any mission that adds entities, evidence, or sources — companies/varieties/evidence counts drift every depth mission; source/patent counts drift less often but should still be re-checked. Do not hand-edit a number without re-running its query; a stale matrix is worse than no matrix, since it looks authoritative while being wrong.
