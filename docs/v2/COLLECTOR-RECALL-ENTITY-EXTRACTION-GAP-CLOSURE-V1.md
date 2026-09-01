# Collector Recall + Entity Extraction Gap Closure V1

**Purpose:** Close downstream miss classes on the frozen 22-row genetics recall benchmark by fixing general collector and extraction mechanisms. Not a completeness score. Not Source onboarding (Claude's lane).

**Owner:** Grok / Cursor.

**Frozen input:** `data/imports/missed-intelligence-recall-audit-v1/benchmark.json` — 22 rows, unchanged.

**Classifier:** `app.services.recall_audit.classify` remains the one taxonomy.

## Failure table (live `29e44e6` / origin at worktree start)

User-stated counts at prompt time were 7 ITEM_MISSED / 3 ENTITY_MISSED / 1 FULLY_REPRESENTED. Live scoring of the unchanged 22-row file was used as ground truth:

| Class | Count |
|---|---:|
| SOURCE_UNKNOWN | 1 |
| SOURCE_KNOWN_NOT_COLLECTED | 5 |
| SOURCE_COLLECTED_ITEM_MISSED | 8 |
| ITEM_COLLECTED_ENTITY_MISSED | 2 |
| ENTITY_FOUND_IDENTITY_UNRESOLVED | 1 |
| DATE_CHRONOLOGY_FAILURE | 1 |
| GEOGRAPHY_LINKAGE_FAILURE | 2 |
| FULLY_REPRESENTED | 2 |

### SOURCE_COLLECTED_ITEM_MISSED (8)

| ID | URL / source | Current app state | Root cause |
|---|---|---|---|
| RA-EU-BK-03 | FreshPlaza Loch Katrine / `source-freshplaza-global` RSS | No published Evidence for this URL | Historical / live RSS window. Source is configured; item aged out. |
| RA-EU-BK-04 | Hutton `/scientific-services/` / `source-20260824-james-hutton-news` | News RSS `item_limit: 10` | Wrong channel: breeding page is not in the news feed. |
| RA-UK-RB-01 | Fruitnet “New raspberries put on show” / Fruitnet RSS | Not in published Evidence | Historical / live RSS window. |
| RA-UK-RB-02 | GPG `/crop/raspberries/` / GPG news RSS | Crop pages not in news feed | Wrong channel. |
| RA-SA-BB-01 | Fall Creek `/commercial-fruit-growers/` / sitemap Source | Include filter was `/blog/` only | Path filter, not a missing Source. |
| RA-SA-BB-02 | Fruitnet MegaEarly 2025 harvest | Not in published Evidence | Historical / live RSS window. MegaEarly has no Variety entity. |
| RA-US-BB-01 | HortiDaily Everlast/Nova / HortiDaily RSS | Not in published Evidence | Historical / live RSS window. |
| RA-US-BB-03 | FreshFruitPortal Apex URL / FFP berries feed | Direct URL not stored | Wrapper capture of a different publisher is not this item. |

### ITEM_COLLECTED_ENTITY_MISSED (2)

| ID | Publication | Extraction state | Root cause |
|---|---|---|---|
| RA-SA-BB-03 | `ev-nda-za-variety-list-2025` exists | Summary names AzraBlue/AtlasBlue; `entity_ids` only Sekoya/Eureka/Twilight | Corpus discovery already extracted those names; scoring never used the mention pool. Candidates are not persisted. |
| RA-US-BB-04 | Apex GNews capture exists | Company linked; no Apex Variety | Title is `news_search`; registry/table path skipped it. Need title-only launch pattern. |

### Other Grok-lane rows

| ID | Class | Root cause / disposition |
|---|---|---|
| RA-US-BB-ID | ENTITY_FOUND_IDENTITY_UNRESOLVED | `variety-fc11-164` exists; Everlast is not in aliases. HortiDaily announcement is not in the corpus. **Left unresolved** — no in-corpus authoritative proof. |
| RA-SA-BB-DATE | DATE_CHRONOLOGY_FAILURE | Operator pointer is `ev-topfruit-megacrisp` (`published_date` null). Honest false-friend. **Not filled from `captured_date`.** Mention builder no longer substitutes captured_date. |
| RA-EU-BK-GEO | GEOGRAPHY_LINKAGE_FAILURE | Variety has no `geography_ids`; linked HortWeek Evidence already has UK/US. Classifier now unions linked-evidence geography. |
| RA-US-BB-05 | GEOGRAPHY_LINKAGE_FAILURE | Apex capture `geography_ids: []`. Do not infer US from Fall Creek HQ. **Remains a geography miss.** |

Claude's lane (untouched): RA-EU-ST-01 SOURCE_UNKNOWN; RA-EU-BK-01, RA-UK-RB-03, RA-US-BB-06, RA-EU-ST-02, RA-EU-ST-05 SOURCE_KNOWN_NOT_COLLECTED.

## Fixes (generalizable)

1. **RSS/Atom `rel=next` pagination** (`max_feed_pages`, default 3, cap 8) for `article_rss` and `news_search_rss`. Tomorrow's item behind an Atom 15-item ceiling can surface.
2. **Per-include-pattern item windows** plus Fall Creek include of `/commercial-fruit-growers/` (existing Source, required path-filter fix).
3. **Caneberry catch-net** adds `cultivar` and `PBR` to the existing Google News query. No new overlapping searches.
4. **Historical planner** `plan_uncollected_eligible_urls` / `load_committed_benchmark_urls` — collection-eligible host, URL not in published Evidence, staging plan only.
5. **Scoring uses one corpus-discovery pass.** NDA table names become identity-unresolved candidates, not silent Varieties.
6. **Title-only launch patterns** on `news_search` / `trade_press` / `company_press_release`. Apex title works; arbitrary body capitals do not.
7. **Mention `published_date`** is published_date only. Unknown stays unknown.
8. **Geography** unions `geography_ids`, geography-typed `entity_ids`, and one hop of linked Evidence. No sibling leakage, no HQ inference.
9. **URL match** is canonical URL of the same item. FreshFruitPortal ≠ Fruitnet GNews wrapper.

Roberto / Italian-Berry class (cultivar-index Fact/Evidence, variety-dense trade article, breeder catalog/table) is unchanged and still covered by `tests/test_variety_corpus_coverage_v1.py`.

## Classification movements (benchmark JSON unchanged)

| ID | Before | After |
|---|---|---|
| RA-SA-BB-03 | ITEM_COLLECTED_ENTITY_MISSED | ENTITY_FOUND_IDENTITY_UNRESOLVED |
| RA-US-BB-04 | ITEM_COLLECTED_ENTITY_MISSED | ENTITY_FOUND_IDENTITY_UNRESOLVED |
| RA-EU-BK-GEO | GEOGRAPHY_LINKAGE_FAILURE | FULLY_REPRESENTED |

FULLY_REPRESENTED: 2 → 3.

Item-missed rows stay item-missed until collection + review actually publishes them. Pagination, path windows, catch-net, and historical planning are the tomorrow-path for those classes.

## What this does not do

- Edit expected external results in the 22-row file.
- Auto-onboard Italian Berry, Bayer, NDA, or CFIA.
- Promote AzraBlue / Apex to trusted Varieties.
- Guess Everlast ≡ FC11-164.
- Treat captured_date as published_date.
- Infer geography from free text or company HQ.
- Deploy (Cursor/Grok has no VPS credentials).
