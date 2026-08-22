# Evidence Berry Tagging Backfill V1

**Mission:** Data-quality repair (2026-08-22, branch `feature/evidence-berry-tagging-backfill-v1`), directly following Blackberry/Raspberry Vertical V1's own finding: ~45% of trusted Evidence carried no `berry_ids`, hiding real content from every berry-scoped count (TD-071), and `deterministic_tagging.py` had zero French vocabulary for any berry (TD-072).
**Scope discipline:** classification completeness, not acquisition coverage. No source added, no UI touched, no Fact/Assessment/Signal/trust field modified.

## 1. Measured gap

Before this mission: **1,266 total trusted `data/evidence/*.json` records, 692 (54.7%) with `berry_ids`, 574 (45.3%) without.**

All 574 untagged records share a single `source_type`/`media_format`: `news_search`, and a single `captured_date`: **2026-08-06** -- one specific historical bulk-seed batch, not a spread of ongoing gaps. Source ids are all the generic `source-20260806173428-*-berry-*` reference sources (e.g. "berry-harvest-forecast", "berry-export-volume", "usda-gain-report-berry") created on the platform's original bootstrap day. Trusted evidence captured on any date *after* 2026-08-06 (3 records total, dated 2026-08-15/21) was **already 100% tagged** -- the historical gap and the current pipeline are cleanly separable, not the same problem.

Classifying the 574 by running the existing, word-boundary-safe `deterministic_tagging.infer_berry_ids_from_text()` against each record's own `title` + `summary` (no article-body fetch):

| Category | Count | Disposition |
|---|---:|---|
| A. Deterministically single-species | 254 | Backfilled |
| B/multi. Genuinely multi-berry (2+ species named) | 21 | Backfilled, multi-tagged |
| C/D. No deterministic species term in title/summary | 299 | **Left untagged** |

A manual, random 20-record sample of the 299 confirmed this is the correct disposition, not a missed vocabulary term: company/category-level mentions ("Room for Berry Category Growth," "Driscoll's and partners purchase major stake in Costa Group" -- Driscoll's/Costa are real multi-berry companies but the title names no species), explicitly mixed content ("Mixed berry program expands..."), and genuinely off-topic items that landed in a "berry" source bucket by scraping error ("J. Berry claims two major awards with Texas A&M AgriLife **hibiscus** hybrids" -- a person's surname, not the fruit; "Froebel Partnership launches pilot phase of new CPD package," an education story with zero berry content). None of the 299 named a species this project's vocabulary doesn't already recognize.

## 2. Tagging paths audited

- **Publication draft enrichment** (`app/services/publication_enrichment.py::apply_deterministic_tags`, called from `enrich_publication_draft`): calls `infer_berry_ids_from_text()` against `title + publisher_description + summary + extra_text`, but does so **before** AI enrichment (`apply_ai_payload`) overwrites `summary` with its own generated text later in the same function -- the deterministic pass sees the real article's own text, not AI commentary. This is the active, current path for every draft created via `scripts/process_discovered_media.py --enrich`.
- **Relevance screening** (`app/services/relevance_screening.py`): separately calls the same `infer_berry_ids_from_text()` at discovery time to populate `likely_berry_ids` on the discovered-item record (metadata triage, not the trusted/draft Evidence object itself).
- **Article ingestion / spoken media / patent-PVR / commercial observations**: all funnel through the same `apply_deterministic_tags` path once a draft object exists; no separate, divergent tagging logic was found for any of these media classes.
- **Older migrated Evidence** (the 574 records): predates `deterministic_tagging.py` being wired into the real ingestion path at all -- these were bulk-inserted directly as trusted records on the platform's bootstrap day, before any auto-tagging step existed to run against them. This is the precise root cause: a **historical legacy gap** from data seeding, not a language/vocabulary gap, not multi-berry ambiguity, and not operator omission (no human ever had a chance to omit a tag on a record created by a bulk script).

**A second, real, latent risk found while tracing this** (not an active bug, but a landmine for future tooling): 126 of 854 inbox draft records (14.8%) are currently untagged. Re-running `infer_berry_ids_from_text()` against their *current* (post-AI-enrichment) summary finds 11 that would newly match -- but every one of those 11 matches is a false positive caused by the AI enrichment's own **negation language**, e.g. a real summary reading "*This article does not appear directly relevant to competitive intelligence on core berry crops (blueberry, strawberry, raspberry, blackberry).*" naively text-matches as if it named all four species. The real production code path is safe today only because `apply_deterministic_tags` runs *before* that AI text exists, not because the matcher itself understands negation -- confirmed zero contamination in the trusted corpus this mission touched (the 574 untagged trusted records are all pre-AI-enrichment content). Registered as new debt (TD-073) rather than fixed, since it is not currently causing wrong data and a robust fix would require detecting arbitrary AI-generated negation phrasing, which is out of this mission's metadata-repair scope.

## 3. Vocabulary reconciliation

Before this mission, `deterministic_tagging.py`'s `BERRY_TERMS` had English + partial Spanish (`frambuesa`, `zarzamora`, `mora` added in Blackberry/Raspberry Vertical V1) but **zero French or Italian** for any berry, while `relevance_screen.py`'s `berry_identity` gate already recognized both. Reconciled additively:

| Berry | Added to `deterministic_tagging.py` | Deliberately NOT added |
|---|---|---|
| Blueberry | French `myrtille`/`myrtilles`, Italian `mirtillo`/`mirtilli` | -- |
| Strawberry | French `fraise`/`fraises`, Italian `fragola`/`fragole` | -- |
| Raspberry | French `framboise`/`framboises`, Italian `lampone`/`lamponi` | -- |
| Blackberry | -- | French `mûre`/`mûres`, Italian `more` -- both remain excluded. **This mission re-confirms why word-boundary matching alone does not make either safe**: `mûre` is the ordinary French adjective for "ripe" and `more` is an extremely common English word; a real sentence can contain either standalone with zero connection to blackberries, so even the word-boundary fix below does not neutralize the risk the way it does for a substring collision. |

**Real bug found and fixed** (not previously documented): `infer_berry_ids_from_text()` used a plain Python substring check (`term in lowered`), not word-boundary matching, unlike `relevance_screen.py`'s own `_word_present()`. This meant "mora" (blackberry) would false-positive-match inside ordinary Spanish words that merely contain it as a substring -- `morado` (purple), `enamorado` (in love), `memorable`, `moraleja` (moral of the story). Verified live: `infer_berry_ids_from_text("Estaba enamorado de las fresas")` returned `['berry-strawberry', 'berry-blackberry']` before the fix (the second tag entirely spurious) and `['berry-strawberry']` after. This bug's *historical* impact on already-tagged trusted Evidence was checked and found negligible (at most 1 low-confidence suspect record out of 146 blackberry-tagged records, found via title/summary text search only), because the untagged legacy batch this mission backfills is overwhelmingly English-language -- but it would have meaningfully corrupted *this mission's own backfill* had it not been fixed first, since the new Spanish-language matching this mission relies on (`zarzamora`) is exactly the kind of term at risk. Fixed by reusing the exact same `(?<!\w)term(?!\w)` pattern already proven safe in `relevance_screen.py`. `deterministic_tagging.py` had zero direct unit test coverage before this mission -- added `tests/test_deterministic_tagging.py` (8 tests, covering the regression, multi-berry/caneberry dual-tagging, and the new French/Italian terms).

Per this mission's own explicit warning, `caneberry`/`caneberries` (added in the prior mission) and `berry`/`berries`/`fruits rouges` (category-only, French collective term) were re-examined and confirmed correctly scoped: `caneberry` deterministically means "raspberry and blackberry together," a real, safe dual-tag, not a guess at a single species; the generic category terms remain entirely absent from `BERRY_TERMS` (they were never added, and this mission did not add them) since they would force false single- or even dual-species specificity onto genuinely unscoped category mentions.

## 4. Dry-run report

Full dry-run output (`python scripts/backfill_berry_tags.py --dry-run`):

```
scanned: 1266
already_tagged: 692
backfill_single_berry: 254 (blueberry 172, strawberry 65, raspberry 10, blackberry 7)
backfill_multi_berry: 21
left_untagged_no_deterministic_match: 299
total_backfilled: 275
```

Verified samples, one per berry (all confirmed against the record's own real summary text, not assumed from title alone):

- **Blueberry**: `ev-20260806173542-3757-costa-registers-five-new-blueberry-varie` -- "Costa registers five new blueberry varieties in Laos" -> `berry-blueberry`.
- **Strawberry** *(via the newly-restored word-boundary-safe matcher, real regression case)*: confirmed no strawberry-tagged record in this batch was affected by the "mora" bug; a representative real match, `ev-20260806173542-173c-...` "Raspberry shortage in India..." -> `berry-raspberry` only, no spurious `berry-blackberry`.
- **Raspberry**: `ev-20260806173542-173c-raspberry-shortage-in-india-drives-devel` -- "Raspberry shortage in India drives development of local varieties" -> `berry-raspberry`.
- **Blackberry**: `ev-20260806173541-de69-fall-creek-acquires-berryplant-berrytech` -- "Fall Creek acquires Berryplant, Berrytech to expand genetics portfolio" -> `['berry-raspberry', 'berry-blackberry']` (summary: "...two leading Italian companies...specialise in the genetics, hybridisation, and propagation of raspberries and blackberries").
- **Multi-berry, 4-species**: `ev-20260806173554-8b8d-usda-philadelphia-terminal-market-fruit-` -- a USDA terminal-market price report whose own summary explicitly prices "raspberries...blackberries, blueberries, strawberries" -> all four, correctly.
- **Spanish/French**: none present in this specific untagged batch -- checked explicitly (`arándano`, `frambuesa`, `zarzamora`, `myrtille`, `framboise`, `fraise` all searched for across the full 574-record pool, zero hits). This batch is 100% English-language content; the Section 3 vocabulary reconciliation protects *future* trusted promotions of the platform's already-active Spanish/French sources, not this specific historical batch. `tests/test_deterministic_tagging.py` exercises real Spanish (`zarzamora`, `frambuesa`, `arándanos`) and French (`myrtille`, `framboise`, `fraise`, and the `mûre` exclusion) cases directly, since none exist in the real data available to sample here.

## 5. Backfill rule

Deterministic title+summary text match only, using the existing, now word-boundary-safe `infer_berry_ids_from_text()`. No article body fetch. A record is left untagged whenever the matcher finds nothing -- explicitly including every category-only mention ("berry," "berries," "fruits rouges" alone), every multi-berry-company mention that names no species, and every off-topic item. **False specificity was treated as strictly worse than missing classification throughout** -- no berry was ever inferred from a company name, source id, or source `berry_coverage` config; only from the record's own text.

## 6. Applied results

`python scripts/backfill_berry_tags.py --apply`: 275 records changed (254 single-berry, 21 multi-berry). Every change is additive-only: `berry_ids` grows from `[]` to a non-empty list, and a new `berry_tagging_provenance: {method, version, applied_at}` object is added (new optional field, `schemas/evidence.schema.json` updated to document it). A rigorous, fully-programmatic key-by-key diff across all 275 changed files (comparing each file's pre-mission git blob to its current content) confirmed **zero other field changed on any record** -- `status`, `review_state`, `title`, `summary`, `source_authority`, and every Fact/Assessment/Signal file are untouched.

## 7. Idempotence

Second `--apply` run: `total_backfilled: 0`, `already_tagged: 967` (692 + 275, exact), `left_untagged_no_deterministic_match: 299` (unchanged). Zero additional changes, as required.

## 8. Current pipeline fix

No fix to the live ingestion path was needed for the core question Section 9 asks (does current ingestion still create newly-trusted Evidence with obvious species terms untagged) -- the historical gap is fully contained to the single 2026-08-06 legacy batch, and the 3 trusted records created since are 100% tagged. The one real, adjacent finding (Section 2's negation-language landmine, TD-073) was deliberately **not** patched with a fragile text-pattern fix, since it is not currently producing wrong data and the robust fix (restructuring when/what text `apply_deterministic_tags` is allowed to see) is a larger change than this mission's metadata-repair scope justifies.

## 9. Downstream impact

| Berry | Trusted Evidence before | After | Delta |
|---|---:|---:|---:|
| Blueberry | 484 | 671 | +187 (+38.6%) |
| Strawberry | 292 | 367 | +75 (+25.7%) |
| Raspberry | 191 | 218 | +27 (+14.1%) |
| Blackberry | 146 | 167 | +21 (+14.4%) |
| **Overall tagged rate** | 692/1,266 (54.7%) | 967/1,266 (76.4%) | +21.7 pts |

Search berry-filtering (`app/main.py`'s `berry_ids` filters on Live Intelligence, Company Recent Intelligence, Global Search, Source listings) now sees all 275 newly-tagged records for the first time -- no code change was needed there, since those paths already filter on `berry_ids` and simply had nothing to find before. Commercial Positions inputs and Variety-linked intelligence are **unaffected**: none of the 275 backfilled records carry a `commercial_observation` or `patent_filing` object (checked directly), and no `entity_ids`/`fact_ids`/`relationship_ids` were touched, so variety-footprint and commercial-position computations see identical inputs to before. `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`'s "Mainstream news" row updated with the new per-berry/untagged counts (this is the only Coverage Matrix row affected, since all 574 untagged records shared that one intelligence class).

**This is not a recall improvement.** No new competitive event was discovered, no new source was run, and no new draft was created. The underlying facts a human reviewer already published were already correct; only their machine-readable species metadata was repaired. Every percentage in this section describes measurement completeness, not intelligence coverage.

## 10. Blackberry impact

Blackberry trusted Evidence depth increased materially in relative terms (146 -> 167, +14.4%) but remains, in absolute terms, the thinnest of the four berries by a wide margin -- still roughly a quarter of blueberry's count. Blackberry's **Variety catalog depth** (12 raspberry / 1 blackberry tracked Variety entities, established in Blackberry/Raspberry Vertical V1) is **completely unchanged** -- this mission touched zero files under `data/entities/`, confirmed via `git status`. The two are genuinely separate facts: blackberry now has measurably more discoverable trusted Evidence than the Coverage Matrix previously showed, but the platform's structured knowledge of *which named blackberry varieties* exist is exactly as shallow as it was, because that gap has a different root cause (CPVO's variety-name-seeded query mechanism, documented in `CANEBERRY-LIVE-RECALL-SET-V1.md` Section 10) that this metadata-repair mission does not touch.

## 11. Raspberry impact

Raspberry's real live recall (9/9, 100%, per `CANEBERRY-LIVE-RECALL-SET-V1.md`) was genuinely being **underrepresented in stored, berry-scoped Evidence counts** before this mission -- the 27-record raspberry gain (+14.1%) includes real, previously-invisible-to-filtering stories (e.g. "Raspberry shortage in India drives development of local varieties and domestic production," "Costa registers five new blueberry varieties in Laos" tagged where it also names raspberry activity in a multi-berry summary). This confirms the prior mission's own live-recall finding was not an isolated anomaly: raspberry content genuinely exists in the corpus at a healthier rate than `berry_ids`-filtered views alone would have shown.

## 12. Multi-berry handling

21 records were multi-tagged, from 2 to 4 species, always because the record's own summary explicitly names each tagged species (verified by hand for every 2+ sample shown in Section 4, not merely assumed from the count). No record was forced to pick one "primary" berry -- `berry_ids` is, and remains, an unordered array, and the schema places no cardinality limit on it (confirmed: `berry_ids` is not in the schema's `required` list, and its `items` type has no `maxItems`). This proves genuinely multi-berry publications stay representable exactly as they are, with no information loss from forcing a single tag.

## 13. Static / public leakage

All 275 changed records were already-trusted, already-published `data/evidence/*.json` records before this mission -- adding `berry_ids` metadata to an already-public record does not newly expose anything that was previously private; it only makes an already-visible record correctly *findable* under a berry filter it should always have matched. `build_static.py`'s own leak self-check (verifying no unpublished draft id/title appears in `generated/`) was run after the backfill and passed clean -- see Validation.

## 14. Technical debt

- **TD-071** ("~45% of trusted Evidence carries no `berry_ids`..."): **substantially resolved**. The specific 574-record gap it documented is now 299 (all genuinely, correctly untagged per Section 1's Category C/D). The *general* risk the debt entry named -- that untagged content can hide real per-berry intelligence from measurement -- is real and permanent in principle (any future bulk import could reintroduce it), so the entry is updated to `resolved for the 2026-08-06 legacy batch; general risk noted` rather than deleted, per the mission's own instruction not to manufacture busywork but also not to overclaim.
- **TD-072** ("`deterministic_tagging.py` has zero French vocabulary for any berry"): **resolved**. French (and, going further than originally scoped, Italian) vocabulary added for blueberry/strawberry/raspberry, matching `relevance_screen.py` exactly; blackberry's French/Italian terms remain deliberately excluded for the same documented collision reasons as the existing `mûre`/`more` exclusions in `relevance_screen.py`.
- **New: TD-073** -- the negation-language landmine described in Section 2 (a hypothetical future draft re-tagging pass would inject false positives from AI enrichment's own "not relevant" phrasing). Real, precisely evidenced, not currently causing wrong data, deliberately not fixed this mission.
