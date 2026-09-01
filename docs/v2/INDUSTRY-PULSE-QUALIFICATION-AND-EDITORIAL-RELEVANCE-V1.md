# Industry Pulse Qualification + Editorial Relevance V1

Provider-neutral discovery qualification. Answers: **is this result
plausibly useful berry-industry competitive intelligence?** Not a Source
onboard, not Evidence, not a homepage change, and not a production
provider switch.

**As-of:** 2026-09-01. Started from bake-off merge `07d2b39`
(PR #207). Frozen genetics recall `data/imports/missed-intelligence-recall-audit-v1/benchmark.json`
is unchanged (SHA-256 `88b219f0822384c2a220bf55cfc0e38899f51fa370f8dee61e7a53db55091e27`,
LF bytes as stored in git).

Claude's Perplexity Pulse activation is a separate lane. This mission does
not touch provider activation, VPS, `/`, or `/today`.

---

## 1. Existing qualifier weaknesses (V0 audit)

`qualify.py` as of bake-off V1 (`qualify_hit_legacy` now, product code no
longer calls it):

1. Hard rejects were thin: recipes/lifestyle plus a BlackBerry-device
   pattern that still required `hit.berry == "blackberry"`.
2. After `screen_relevance`, **any** `_STRONG_INDUSTRY` match
   (`genetics`, `breeder`, `patent`, `license`, `grower`, …) **or**
   `university` **or** weather **qualified**, even with no berry crop in
   the title/snippet.
3. Query `berry=` provenance was enough to keep a hit in the industry
   path. Cannabis genetics, livestock genetics, grape cultivar pages,
   avocado plant-patent history, and job titles like `Director of Breeding`
   therefore qualified.
4. Authority was not separated from relevance. A `.gov` host was not
   rejected for being non-agricultural (FDA PMA, Job Corps).
5. Reasons were a single opaque string (`qualifying: berry market/…`),
   not an inspectable list.
6. No editorial topic. No source-class context.

Product qualification is now `app/services/industry_pulse/qualify.py`.
Legacy exists only to score BEFORE metrics.

---

## 2. False-positive taxonomy (from bake-off live examples)

Not exhaustive. Used to design layers, not to hardcode titles.

| Class | What it looked like | Why V0 let it through |
|---|---|---|
| Raspberry Pi | `raspberry pi` / GPIO compute | crop word `raspberry` |
| BlackBerry device | smartphone / IP litigation / RIM | `blackberry` + optional `patent` |
| Cannabis | seed banks, strain naming, High Times | `genetics` / `breeder` |
| Recipe / foodservice | smoothies, calories, menus | sometimes rejected; residual food noise remained |
| Consumer nutrition | superfood / breakfast berries | overlap with recipe class |
| Jobs / recruiting | `Director of Breeding`, postdoc vacancies | industry vocabulary in HR copy |
| Livestock / veterinary | livestock genetic conservation | `genetics` without a berry crop |
| Unrelated produce | grapes, avocado patents, other fruit | `cultivar` / `patent` |
| Generic retail | weekly ads | already partly rejected |
| Gardening / hobby | home growing guides | crop name + weak industry |
| Unrelated scientific | Ozempic, biologics | query provenance only |
| Unrelated `.gov` | FDA device PMA, Job Corps | host looks authoritative |
| Berry-word ambiguity | strawberry-colored PC case | crop word, no industry |
| Event / lifestyle | music festival, pets of the week | harvest/variety collisions |

---

## 3. Frozen qualification benchmark

Path: `data/imports/industry-pulse-qualification-v1/qualification_benchmark.json`

Named **`qualification_benchmark.json` on purpose**. Coverage Assurance
auto-loads `data/imports/*/benchmark.json`. Do not rename this file to
`benchmark.json`. Do not edit rows merely to improve metrics.

**Size:** 34 frozen entries.

- 18 expected QUALIFY (Google, Perplexity, and synthetic regressions)
- 16 expected REJECT
- Includes cultivar-dense, PBR, university, market/supply, unknown Source,
  Italian Berry / G-Viva, Apex table, Planasa, Fall Creek M&A, Zimbabwe
  hectares, and the residual metaphor borderline `BL-02`

`BL-02` ("Blackberries, genetics and stupid science") is frozen **expected
qualify** so V1 does not overfit a reject rule to that title. Residual
metaphor risk is documented, not trained away.

---

## 4. Qualification architecture

Layered, deterministic, provider-neutral. No LLM in the primary path. No
opaque quality score. No universal authority score.

`QualificationIndex.compile(...)` once per pulse/bake-off run (company
names, variety names, Source/universe host classes). Do not rebuild per
hit.

Every hit gets:

```
QUALIFY | REJECT
- reason(s)
editorial_topic?  (only when deterministic)
source_context    (class, not a score)
```

### Layer 1 — hard exclusions

Compiled regexes, title+snippet (+ URL/host for unrelated `.gov`):

- Raspberry Pi (`raspberry pi`, `raspi`, `gpio`)
- Cannabis cultivar/product context
- BlackBerry device/company unless fruit-blackberry context
  (`cultivar|grower|harvest|fruit|primocane|nursery|seedless`)
- Recipe / foodservice / consumer nutrition copy
- Jobs (`we're hiring`, title leading `Director of|Postdoc|Hiring`)
- Livestock / veterinary
- Unrelated science (PMA, biologics patent, Ozempic)
- Event noise (music festival, pets of the week)
- Gardening hobby if no industry terms
- Retail promo if no industry terms
- Unrelated produce (potato/grape/apple/avocado/…) if **no berry crop named**
- Unrelated `.gov` (`fda.gov`, `accessdata.fda.gov`, `jobcorps.gov`,
  `cdc.gov`) unless berry crop **and** food-recall language

`.gov` is not agricultural relevance. USDA / CPVO / plantvarieties.eu are
`government_agriculture`. FDA device pages are not.

### Layer 2 — positive berry-industry context

Qualify only with berry-crop identity in title/snippet **or** a named
company/cultivar from the compiled index, plus industry terms
(production, trade, genetics, PBR, grower, harvest, …).

Do **not** infer berry solely from `query.berry`. Do **not** infer
geography from Company HQ. Query provenance is retained on the hit for
novelty/region rollup; it is not a qualification substitute.

### Layer 3 — source/context modifiers

Deterministic classes, never a score:

- `government_agriculture`
- `government_unrelated`
- `university`
- `breeder`
- `trade_press`
- `company_newsroom`
- `general_press`
- `unknown`

Unknown Source is **not** auto-rejected. Unknown Sources are the point
of the catch-net.

A trade-press / breeder / ag-gov host plus an explicit named berry crop
may still qualify when industry terms are thin. That preserves short
cultivar-dense titles.

---

## 5. Editorial topic classification

After QUALIFY only, and only when evidence is explicit:

| Topic | Evidence |
|---|---|
| Variety / Genetics | cultivar, PBR, breeder, CRISPR, primocane, … |
| Competitor Move | acquisition, merger, partnership, launches, … |
| Market / Supply / Trade | acreage, export, harvest, pricing, weather, … |
| Research / Regulation | university, extension, field trial, CPVO, … |
| Other / unclassified | left `None` when uncertain |

Do not force a category. Front-page mapping uses the same names the
authenticated `/today` already has; this layer does not write `/today`.

---

## 6. Frozen precision / recall

Scored by `score_benchmark()` using the real V0 function vs current
`qualify_hit`. Not a composite score.

| | Total | Qualifying | False positives | False negatives | Precision |
|---|---:|---:|---:|---:|---:|
| BEFORE (V0) | 34 | 25 | 7 | 0 | 0.720 |
| AFTER (V1) | 34 | 18 | 0 | 0 | 1.000 |

**Before false positives (all now REJECT):**

- `FP-CAN-01` cannabis seed bank
- `FP-CAN-02` cannabis strain naming
- `FP-JOB-01` Fall Creek breeding job
- `FP-JOB-02` Wageningen postdoc vacancy
- `FP-LIV-01` livestock genetic conservation
- `FP-PROD-01` finger grapes
- `FP-PROD-02` Hass avocado patent

**Recall losses (previously qualifying expected-qualify that V1 now
rejects):** none.

Manual inspection: all 18 expected-qualify rows still QUALIFY, including
G-Viva / Italian Berry, Apex table, USDA PBR, OSU extension, unknown-Source
Rijk Zwaan, Zimbabwe hectares, Fall Creek M&A, primocane blackberry, and
Planasa.

Residual risk: `BL-02` metaphor still qualifies (by freeze design).

---

## 7. Live retest

Production pulse still defaults to Google News RSS. Perplexity production
activation had **not** merged (`origin/v2/intelligence-os` still `07d2b39`
at retest). Bake-off Perplexity ran because credentials were present; it
does not change `run_pulse()`'s provider.

Live Google News RSS is non-deterministic (TD-039). These counts are this
run, not a completeness score.

### Industry Pulse (32 Google News queries, 2026-09-01, second pass)

| Window | Unique | Qualifying | Novel | Known | Rejected |
|---|---:|---:|---:|---:|---:|
| 24h | 26 | 2 | 2 | 0 | — |
| 3d | 35 | 2 | 2 | 0 | — |
| 7d | 77 | 7 | 6 | 1 | 70 |

Prior V0 pulse the same day: 7d 79 unique / 4 qualifying. Pairwise seedless
blackberry and `east-fruit.com` Ukraine blueberry variety strategy still
qualify. Newly rejected on this pass: BlackBerry **stock**, school-cafeteria
harvest, Raspberry Pi, recipes.

**7d rejection reasons:** no berry-crop identity 27; berry without industry
17; BlackBerry device/company 10; Raspberry Pi 5; recipe/foodservice 5;
event noise 3; unrelated produce 3.

**7d editorial topics (qualifying):** market/trade 4; variety/genetics 2;
unclassified 1.

**Region (7d unique):** global 75/6 qualifying; europe 1/1; americas 1/0;
africa 0; apac 0. Query-yield still global-heavy (TD-105).

**Berry (7d unique qualifying):** blueberry 2, strawberry 1, raspberry 2,
blackberry 2.

**Residual live pulse FPs (not frozen, not overfitted):** a Shaq blueberry
harvest video; a community raspberry-harvest “bright spot”; an urban
“blackberry debate” planting column. Legitimate market/variety rows were
kept.

### Bake-off slices A–F (comparable to PR #207)

Bake-off `false_positive_rate` is **non-qualifying / unique** (a reject
rate), not labeled precision. Labeled precision lives on the frozen 34-row
set.

| | Google News (V0 bake-off) | Google News (V1) | Perplexity (V0) | Perplexity (V1) |
|---|---:|---:|---:|---:|
| Unique | 114 | 113 | 104 | 103 |
| Qualifying | 19 | 28 | 20 | 20 |
| Reject rate | 0.833 | 0.752 | 0.808 | 0.806 |
| Novel qualifying | 5 | 9 | 12 | 11 |
| URL overlap G/P | 0 | 0 | 0 | 0 |
| Shared hosts | 5 | 4 | 5 | 4 |

Google qualifying **rose** because bake-off now compiles the same
`QualificationIndex` (named companies such as Planasa / Fall Creek) and
because harvest/production/trade stories keep qualifying. The qualifying
examples are cultivar/M&A/trade-press rows (Planasa Genetics Forum, Fall
Creek/Berryplant, NC State blackberry, primocane blackberry, Bloom Fresh /
Inka’s, Rijk Zwaan, AVA Monet), not cannabis/jobs/livestock.

Perplexity qualifying count stayed ~20 while the **composition** changed:
cannabis 3, jobs 1, livestock 1, unrelated `.gov` 1, gardening/hobby 1,
unrelated produce 11 are now explicit REJECT reasons. G-Viva / Italian
Berry still qualifies. GardenWizz is now REJECT gardening/hobby.

URL-identity overlap remains 0. Shared hosts this run: `cals.ncsu.edu`,
`freshfruitportal.com`, `freshplaza.com`, `perishablenews.com`.


---

## 8. Future second-stage model (not implemented)

If residual ambiguous cases (metaphor, dual-use `patent`, short titles
on unknown hosts) become the bottleneck **after** this layer, a bounded
second-stage classifier could take QUALIFY+uncertain rows only. V1 does
not call an LLM in the qualification path.

---

## 9. Performance

Indexes and regexes compile once per run. Qualification is title+snippet
only. Cheap enough for hundreds/thousands of discovery hits
(`test_qualification_is_cheap_over_hundreds`).

---

## 10. What this does not do

- No production provider switch
- No VPS / deploy
- No trust mutation, no Source onboard, no Evidence write
- No `build_static` / `feed.html` / `today.html` leakage
- No hardcoded benchmark URLs or publisher allowlists in rules
- No universal authority score
