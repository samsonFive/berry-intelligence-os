# Independent Missed Intelligence Discovery + Recall Audit V1

**Purpose:** Beat the app on public genetics intelligence, then classify every qualifying miss. This is a coverage *test*, not a monitoring system.

**Owner:** Grok / Cursor (intended mission after an accidental Coverage Assurance prompt).

**Canonical SHA at scoring:** `8226a5d` (`v2/intelligence-os` at research time). Rebased onto Coverage Assurance V1 (`5d6a662`, PR #202). Coverage Assurance already copied `app.services.recall_audit.classify` and auto-loads `data/imports/*/benchmark.json`; this mission adds the 22-result benchmark, tests, and findings — not a second classifier.

**What this is not**

- Not a Coverage Assurance dashboard, route, or competing service.
- Not a completeness percentage.
- Not auto-onboarding of Sources (Italian Berry stays cited / not collected).
- Not trusted Evidence. Benchmark rows never write `data/evidence/`.
- Not Variety Universe Expansion V2 and not Report Builder internals.

## Accidental prompt vs intended mission

| Work | Where it lives | Status |
|---|---|---|
| Public Intelligence Coverage Assurance V1 | merged as PR #202 (`5d6a662`) | Canonical dashboard + source universe. Copied `app.services.recall_audit.classify` so it could land first. |
| Independent Missed Intelligence Discovery + Recall Audit V1 | this PR, rebased onto #202 | **This document + 22-result benchmark + tests.** Classifier ownership stays `app.services.recall_audit.classify` (one module, 9-class taxonomy). |

The Italian Berry finding (publisher already in trusted Evidence, absent from `sources.json`) is reused here as a live miss class, not as a reason to build a monitor.

## Method

1. Adversarial public research on five strata: EU blackberry, UK raspberry, South Africa blueberry, U.S. blueberry, EU/UK strawberry genetics.
2. Qualify only named-cultivar public items (article, first-party page, official list/registry). Bodies are not stored.
3. Compare each qualifying URL against canonical Sources, published Evidence, and trusted Varieties.
4. Classify with `app/services/recall_audit/classify.py`. Operator match pointers (`matched_evidence_id`, `matched_entity_id`, `expected_entity_id`, `expected_alias`, `expected_geography_id`, `expected_date`) are re-verified against the live corpus. Hidden provider reasoning is dropped.

Miss classes:

| Class | Meaning in this run |
|---|---|
| SOURCE UNKNOWN | Host is not a Source and not cited on published Evidence (`bayer.com`). |
| SOURCE KNOWN, NOT COLLECTED | Host is registered and/or already cited, but not collection-eligible for this item (Italian Berry, CFIA, CPVO register without a feed). |
| SOURCE COLLECTED, ITEM MISSED | Collection-eligible publisher; this URL is not published Evidence (FreshPlaza Loch Katrine, Fruitnet, HortiDaily, FFP Apex, Fall Creek `/commercial-fruit-growers/`, Hutton `/scientific-services/`, GPG crop pages). |
| ITEM COLLECTED, ENTITY MISSED | Evidence exists; the cultivar is not a trusted Variety (NDA AzraBlue; Apex capture). |
| ENTITY FOUND, IDENTITY UNRESOLVED | Variety exists under selection code; commercial name is missing (`variety-fc11-164` vs Everlast). |
| DATE/CHRONOLOGY FAILURE | Naive match to a different, undated artefact (MegaCrisp family page vs 2025 MegaEarly harvest). |
| GEOGRAPHY LINKAGE FAILURE | Record or entity lacks the expected `geography_ids` (Apex capture empty; Victoria has no geography_ids). |
| FULLY REPRESENTED | Same item and cultivar are trusted (SEKOYA Nova Produce Report; RedSayra Fruitnet). |

## Machine-readable set

`data/imports/missed-intelligence-recall-audit-v1/benchmark.json` — 22 qualifying results. Re-score with:

```text
python -c "from pathlib import Path; import json; from app.services.recall_audit import score_benchmark; ..."
```

or the tests in `tests/test_independent_missed_intelligence_recall_audit_v1.py`.

If Coverage Assurance V1 is present, this JSON is auto-loaded from `data/imports/*/benchmark.json`. Extra classes `DATE_CHRONOLOGY_FAILURE` and `GEOGRAPHY_LINKAGE_FAILURE` are part of the one canonical taxonomy in `app.services.recall_audit.classify`; do not fork a shorter enum.

## Scored findings (`8226a5d`)

Counts below are **this benchmark only**.

| ID | Stratum | Item | Class |
|---|---|---|---|
| RA-EU-BK-01 | EU blackberry | Italian Berry cultivar table (Clara/Kalika/Equa/Furia/Nemus/Loch Katrine…) | SOURCE KNOWN, NOT COLLECTED |
| RA-EU-BK-03 | EU blackberry | FreshPlaza Loch Katrine | SOURCE COLLECTED, ITEM MISSED |
| RA-EU-BK-04 | EU blackberry | Hutton blackberry breeding page | SOURCE COLLECTED, ITEM MISSED |
| RA-EU-BK-GEO | EU blackberry | `variety-victoria` has no `geography_ids` | GEOGRAPHY LINKAGE FAILURE |
| RA-UK-RB-01 | UK raspberry | Fruitnet GPG/Hutton P4/P5/F6 | SOURCE COLLECTED, ITEM MISSED |
| RA-UK-RB-02 | UK raspberry | GPG raspberries crop page (Glen Mor / Glen Eden) | SOURCE COLLECTED, ITEM MISSED |
| RA-UK-RB-03 | UK raspberry | CFIA Skye PBR | SOURCE KNOWN, NOT COLLECTED |
| RA-SA-BB-01 | SA blueberry | Fall Creek SA regional insights | SOURCE COLLECTED, ITEM MISSED |
| RA-SA-BB-02 | SA blueberry | Fruitnet MegaEarly 2025 harvest | SOURCE COLLECTED, ITEM MISSED |
| RA-SA-BB-03 | SA blueberry | NDA 2025 list — AzraBlue not an entity | ITEM COLLECTED, ENTITY MISSED |
| RA-SA-BB-DATE | SA blueberry | MegaCrisp page used as 2025 harvest | DATE/CHRONOLOGY FAILURE |
| RA-US-BB-01 | US blueberry | HortiDaily Everlast + Nova | SOURCE COLLECTED, ITEM MISSED |
| RA-US-BB-ID | US blueberry | `variety-fc11-164` missing Everlast alias | ENTITY FOUND, IDENTITY UNRESOLVED |
| RA-US-BB-03 | US blueberry | FreshFruitPortal Apex URL | SOURCE COLLECTED, ITEM MISSED |
| RA-US-BB-04 | US blueberry | Apex GNews/Fruitnet capture, no variety | ITEM COLLECTED, ENTITY MISSED |
| RA-US-BB-05 | US blueberry | Same capture, `geography_ids: []` | GEOGRAPHY LINKAGE FAILURE |
| RA-US-BB-06 | US blueberry | Italian Berry high-chill preview | SOURCE KNOWN, NOT COLLECTED |
| RA-US-BB-07 | US blueberry | Produce Report SEKOYA Nova | FULLY REPRESENTED |
| RA-EU-ST-01 | EU/UK strawberry | Bayer Baya Solara press release | SOURCE UNKNOWN |
| RA-EU-ST-02 | EU/UK strawberry | Italian Berry Baya Solara | SOURCE KNOWN, NOT COLLECTED |
| RA-EU-ST-05 | EU/UK strawberry | CPVO Malling Centenary | SOURCE KNOWN, NOT COLLECTED |
| RA-EU-ST-06 | EU/UK strawberry | RedSayra Fruitnet | FULLY REPRESENTED |

Same-class items not given their own row (documented, not double-counted): Plus Berries Kalika/Equa/Furia/Nemus (Italian Berry); Elyson NSG 48 and Giusy CIVH413 (Italian Berry).

## Patterns that beat the app

1. **Cited ≠ collected.** Italian Berry, CFIA (`inspection.gc.ca`), and NDA (`nda.gov.za`) already appear on trusted Evidence. New items from those hosts still miss unless a research-agent import happens to include them.
2. **Feed path ≠ site.** Hutton news RSS, GPG news RSS, and Fall Creek `/blog/` sitemap filters miss breeding pages, crop catalogues, and regional insights.
3. **Wrapper capture without entity.** Apex was ingested via Google News with a Peru keyword Source; company linked, cultivar and geography not.
4. **Registry chicken-and-egg.** CPVO is queried from already-tracked Variety names, so Malling Centenary never enters the monitor. The V1 EU/UK/SA import left it as `candidate_name` only; `inbox/variety_candidates/` is empty here.
5. **Selection code ≠ commercial name.** `variety-fc11-164` is trusted as unverified without Everlast.

## Operator actions this file does **not** take

- Do not add Italian Berry, Bayer, or NDA as Sources from this audit.
- Do not publish benchmark rows as Evidence.
- Do not merge Variety Universe Expansion V2.
- Do not invent a coverage score from the 2/22 fully represented positive controls.

## Tests

`tests/test_independent_missed_intelligence_recall_audit_v1.py` scores the real canonical corpus. If a later SHA onboards Italian Berry or creates `variety-apex`, those tests should fail until the benchmark is re-scored honestly.
