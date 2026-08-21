# Weather / Climate Context V1

**Mission:** Weather / Climate Context V1 (2026-08-21, branch `feature/weather-climate-context-v1`). Build a berry-production-context layer, not a consumer weather dashboard, in direct response to Trade Intelligence V1's own real, unexplained physical-market movements (Chile/South Africa blueberry export swings, Mexico strawberry decline).

---

## 1. Production geography audit

Existing canonical geography knowledge (`data/entities/geographies/`) is **country-level only** -- 19 Geography entities exist (Chile, Mexico, Morocco, Peru, South Africa, Spain, United Kingdom, United States, plus others not relevant to berries), each carrying an `iso_3166_1_alpha_2` code but no sub-national structure. This mission's own priority-geography list maps as follows:

| Priority geography | Country-level Geography entity | Sub-national production region (this mission) |
|---|---|---|
| Peru | `geography-peru` (exists) | `peru-la-libertad-blueberry` (new config, piloted) |
| Chile | `geography-chile` (exists) | `chile-maule-blueberry` (new config, piloted) |
| Mexico | `geography-mexico` (exists) | `mexico-michoacan-guanajuato-strawberry` (new config, piloted) |
| California | `geography-united-states` (exists, country-level only) | `us-california-central-coast-strawberry` (new config, **not piloted**) |
| Pacific Northwest | `geography-united-states` (exists, country-level only) | `us-pacific-northwest-blueberry` (new config, **not piloted**) |
| UK | `geography-united-kingdom` (exists) | `uk-kent-berry` (new config, **not piloted**) |
| Spain | `geography-spain` (exists) | `spain-huelva-strawberry` (new config, **not piloted**) |
| Morocco | `geography-morocco` (exists) | `morocco-gharb-loukkos-blueberry` (new config, piloted) |
| South Africa | `geography-south-africa` (exists) | `south-africa-western-cape-blueberry` (new config, piloted) |

**No farm coordinates were invented.** Each new production-region entry in `data/configuration/weather_production_regions.json` names a real, publicly-documented berry-growing region (Maule for Chilean blueberries, La Libertad for Peruvian blueberries, Michoacan/Guanajuato for Mexican strawberries, etc.) with a single representative centroid and an honest `coverage_caveat` acknowledging that one point is coarser than the real region. This is deliberately a config-level mapping, not a new Geography entity type -- see TD-037.

---

## 2. Weather / climate source audit

Real, live-tested access research (not documentation review alone), mirroring Trade Intelligence V1's own discipline.

| Source | Access | API | Historical coverage | Spatial resolution | Cadence | Automation feasibility |
|---|---|---|---|---|---|---|
| **NASA POWER** (public daily point) | Public, no login | **Yes -- real, live-verified, unauthenticated JSON API** (`power.larc.nasa.gov/api/temporal/daily/point`) | 1981-01-01 to near-real-time (live-confirmed: a 10-year 2015-2024 range returned in ~1.2s, 179KB) | ~0.5 degree (~50km) native grid; point query returns one representative reading | Daily, ~2-3 day release latency (live-confirmed: the 3 most recent days of a request returned the documented -999.0 fill value) | **High -- integrated this mission** |
| **NOAA Climate Data Online** | Public web UI; API requires an **email-registered token** | Yes, real, but keyed (5 req/sec / 10,000 req/day once issued) | Deep (US stations, some 1800s-present) | Station-level (finer than POWER for the US) | Daily | **Not integrated this mission** -- live-researched and confirmed to require a self-service email token this agent session cannot complete, the exact same access-barrier pattern as US Census in Trade Intelligence V1 (TD-025 precedent, now TD-036). |
| **NWS** (National Weather Service API) | Public | Real API (`api.weather.gov`), keyless | Forecast + recent observations only, not deep historical | Station/grid | Real-time | Not integrated -- forecast-oriented, not a historical-baseline source; a different data class than this mission needed. |
| **USDA climate/drought products** (US Drought Monitor, PSD Online) | Public, mixed (some bulk downloads, some dashboards, no unified global historical API) | Partial | Deep for drought classification (US only) | County-level (US) | Weekly (Drought Monitor) | Not integrated -- US-only, drought-classification-specific; a real future regional complement, not a substitute for a global point source. |
| **ERA5 / Copernicus CDS** | Public; API requires a **CDS account + personal access token** | Real API (`cdsapi`), but keyed | Deep (1940-present), finer reanalysis than POWER | ~0.25 degree (~28km), finer than POWER | Varies by product | Audited, **not implemented this mission** -- live-researched and confirmed to require account registration this session cannot complete. A genuine future add if finer resolution is specifically needed (TD-036). |
| **National meteorological agencies** (Chile DMC, SENAMHI Peru, SAWS South Africa, etc.) | Public, but not individually live-tested this mission (time-bounded, per the mission's own "prefer one broadly usable global source" instruction) | Unknown, varies by country | Unknown | Unknown | Unknown | Not audited in depth -- NASA POWER already answered every real test case this mission needed without a per-country adapter. |

**Bottom line**: NASA POWER's keyless public daily point API is the only source in this table that is simultaneously global, requires zero registration this session could complete, and was proven live to answer every one of the mission's real required test cases. It is the one adapter built. Unlike UN Comtrade's one-period-per-request cap, POWER accepts an arbitrary contiguous date range in a single request -- a real, live-confirmed architectural difference that made this mission's real acquisition far cheaper (2 requests per region: one 10-year baseline call, one comparison-window call) than Trade Intelligence V1's per-period Comtrade calls.

---

## 3. Weather observation model

Additive `weather_observation` object on `evidence.schema.json` (`schemas/evidence.schema.json`), mirroring the `trade_observation` precedent exactly -- no new record type, no parallel trust system. **One Evidence draft per production-region observation window**, holding a compact daily `series[]` for the real comparison window (2025-01..2026-06) plus a compact `baseline_by_month` summary (12 entries, one climatological mean per calendar month) reduced from a separate 10-year baseline query -- the baseline's own raw daily readings are never stored on the Evidence draft, only the reduced summary. Fields: production-region id, geography id, centroid, an honest `spatial_resolution_note`, tracked metrics, baseline period + monthly summary, and per-day max/min temperature + precipitation + source model + provisional flag. `does_not_prove` is always populated with `WEATHER_DOES_NOT_PROVE` (does not prove causation, crop damage, regional representativeness, or a durable trend).

---

## 4. Adapter chosen: NASA POWER public daily point API

`app/services/weather_intelligence.py` + `scripts/monitor_weather_intelligence.py`, architecturally parallel to `trade_intelligence.py` (untrusted `inbox/evidence/` drafts only, real idempotency via a per-region state file).

---

## 5. Real data pilot

5 real production regions (`data/configuration/weather_pilot_regions.json`): Chile-Maule blueberry, Peru-La Libertad blueberry, South Africa-Western Cape blueberry, Morocco-Gharb/Loukkos blueberry, Mexico-Michoacan/Guanajuato strawberry -- directly matching Trade Intelligence V1's own real trade-anomaly cases (California/Pacific Northwest/UK/Spain regions were mapped in config for completeness against the mission's own priority-geography list but not queried, since no real trade anomaly required them -- an honest scope decision, not an oversight).

**Real run results**: all 5 regions produced real data, 0 failures; 5 real drafts created (one per region); a real second run proved full idempotency (5/5 duplicates, 0 new). Each draft holds a real ~546-day daily series (2025-01-01..2026-06-30) plus a compact 12-entry baseline summary reduced from a real 2015-2024 (10-year) query per region.

**Real, honest data-provenance finding**: NASA POWER's own `sources` field switches between `GEOSIT` (near-real-time product) and `MERRA2` (final reanalysis) depending on how recently a date was queried -- live-confirmed by querying the same recent date range at two different points during this mission and seeing the reported model change as NASA reprocessed it. This is carried on every series entry (`source_model`) but not independently verified per day and not re-diffed on later reprocessing -- see TD-033.

---

## 6. Chile blueberry case

`weather_context_for_trade_anomaly()` run against Chile's real -42.0% (Feb) / -76.1% (Mar) YoY US blueberry export decline (Trade Intelligence V1): **yes, a material weather anomaly was found.** A real 3-day extreme-heat run, **2025-12-29 to 2025-12-31, +7.18C above the calendar-month baseline mean**, sits roughly 8-13 weeks before the reported trade decline. March itself carried real precipitation at **~363% of the climatological baseline** (59.15mm actual vs. 16.31mm expected) -- heavy rain during a blueberry ripening/harvest window is a real, documented volume and quality risk in the industry (fruit splitting, rot, delayed picking), though this pilot does not independently verify that mechanism occurred here. **One real, proposed-only `corroborates` evidence_link** was added from the Chile weather draft to the Chile trade draft (`ev-trade-trade-9c44d57e3499ea6d`), `status: "proposed"` -- a human reviewer decides whether to accept it. This is context, not proof: `does_not_prove` is populated on both records.

---

## 7. South Africa blueberry case

Same corroboration check against South Africa's real -84.4% (Feb) / +68.5% (Mar) YoY UK blueberry decline-then-recovery: **the February decline itself has no matching frost, extreme-heat, or precipitation-deficit/excess anomaly in its own window** -- reported honestly as no meaningful weather explanation found, not forced into one. A real extreme-heat run (**2026-03-09 to 2026-03-15, +8.61C**, 7 days) does overlap the March recovery period -- noted as a real, honest observation (warmer conditions coinciding with a harvest-timing rebound is plausible) but explicitly not claimed as the cause of a *volume increase*, which would be an even weaker inference than the Chile case. No evidence_link was proposed for South Africa; an absent link is reported as absent.

---

## 8. Mexico strawberry control

Mexico's real -36.4% (qty) / -56.2% (value) YoY strawberry-import decline already has a clean, independently-corroborated regulatory explanation from Trade Intelligence V1 (the real Federal Register antidumping "Determination", ~1 month prior). Used here as a **control**: `weather_context_for_trade_anomaly()` found **no precipitation deficit/excess and no frost** in the Michoacan/Guanajuato window. The only signal present is the low-specificity `unusual_temperature_window` check (see TD-035), which this mission's own findings do not feature as evidence anywhere, including here. **Result: weather does not provide an alternative or additional explanation for this decline** -- the system correctly did not manufacture a weather narrative to compete with the already-established regulatory one. This directly demonstrates the distinction the mission asked for: REGULATORY CONTEXT (Trade Intelligence V1) vs. WEATHER CONTEXT (this mission), not collapsed into "every decline gets a weather story."

---

## 9. Peru blueberry case

Peru's real +10.3% (Feb) / +33.1% (Mar) YoY US blueberry export growth overlaps real precipitation well above baseline in both months (**Feb: 173.08mm actual vs. 46.08mm expected, ~376% of normal; Mar: 200.72mm actual vs. 51.15mm expected, ~392% of normal**) -- the same weather-condition *type* (precipitation excess) found in the Chile decline case. This is reported as a real, honest complexity, not smoothed over: excess rainfall is present alongside both a decline (Chile) and growth (Peru) in the same real window, which is exactly why this mission does not claim "excess precipitation reduces supply" as a general rule. Peru's own coastal-desert, irrigation-dependent production system responds differently to rainfall than Chile's -- a real agronomic distinction this pilot does not attempt to model. No evidence_link was proposed for Peru (the mission's own instruction for this case asks only to look for consistency/inconsistency, not to force a link).

---

## 10. Production-region mapping

`data/configuration/weather_production_regions.json` -- 9 entries (5 piloted, 4 documented-only), each with a real named region, a source citation, an honest `coverage_caveat`, and `piloted: true/false`. No fake precision: every centroid is explicitly labeled a single representative point within a real, coarser production region, and NASA POWER's own ~50km native grid is stated directly on every generated Evidence draft (`spatial_resolution_note`). See Part 1 above and TD-030/TD-031.

---

## 11. Weather + trade corroboration service

`weather_context_for_trade_anomaly()` in `app/services/weather_intelligence.py` -- given a production region and a trade-reporting period, runs every derived-event check (frost, extreme heat, unusual temperature, precipitation deficit/excess, drought) over that period's own month plus a 60-day lookback, and returns a structured bundle: which checks flagged, their real dates/magnitudes/thresholds, the source, and `does_not_prove`. Nothing here writes a Signal, an Evidence record, or an evidence_link automatically -- every real link in this mission (one, for Chile) was added as a separate, explicit, human-reviewable edit at `status: "proposed"`.

---

## 12. Leading-indicator proof

Chile's real December extreme-heat anomaly (ended 2025-12-31) provided a real, honestly-computed lead time of **59 days** before the February trade period's month-end, and **90 days** before the March period's month-end (`leading_indicator_lead_time()`, a simple calendar calculation -- explicitly not a forecast model, and conservative relative to Comtrade's real publication lag per Trade Intelligence V1's own findings). **No candidate/watch mechanism was wired into `inbox/signal_candidates/`** -- the mission's own instruction was to create one "only if current architecture supports it cleanly," and a weather-anomaly-as-leading-indicator pattern is a genuinely new candidate type that would need its own review semantics, out of this mission's bounded scope. This is reported as a real, measured proof-of-concept (a genuine multi-week lead time exists in at least one real case), not as a shipped prospective feature.

---

## 13. Source health

Reuses the existing Source `last_checked_at`/`last_status` mechanism (`source-nasa-power-daily-point` added to `data/configuration/sources.json`, same pattern as `source-un-comtrade-public-preview`). Distinguished states, all real and observed this mission: **API healthy** (a region query returns real daily data), **data not yet released** (the most recent ~2-3 days of any query return NASA's own -999.0 fill value, live-observed, recorded as `is_provisional: true`, never as a failure or a real zero), **no anomaly** (a derived-event check runs successfully and returns `flagged: false` -- explicitly not conflated with a failed check, per the mission's own instruction), **request failure** (a transport/HTTP error, not observed this mission but handled identically to Trade Intelligence V1's pattern).

---

## 14. Recall benchmark relation

Reviewing the 50-event benchmark (`docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md`) for weather relevance. **No benchmark event is itself a weather-catalyst headline** (e.g. "frost destroys X% of crop") -- so this layer's real impact is necessarily corroborative/contextual, not direct detection of a benchmark event's own headline, and this section does not inflate that.

| Benchmark event | Weather / Climate V1 relation |
|---|---|
| BM-M-02 Chilean blueberry exports to US fall 13% | **CORROBORATED** -- exactly the shape of case this mission's own Chile pilot demonstrated (extreme heat + precipitation excess found in the real analogous 2026 case). |
| BM-M-03 Peru blueberry production +25% forecast | **CORROBORATED** (in principle) -- a production forecast could be checked against real precipitation/temperature trends the same way this mission checked Peru's actual 2026 growth; not independently re-tested against this specific 2026 forecast event. |
| BM-M-05 South Africa blueberry production reaches 38,900t | **CORROBORATED** (in principle), same reasoning as BM-M-03; this mission's own South Africa pilot found no material anomaly in the comparable window, illustrating the check can also honestly return nothing. |
| BM-M-06 Mexico blackberry production forecast 274,000 MT | **NOT HELPED in this pilot's actual scope** -- no Mexican blackberry-specific production region was piloted (only Michoacan/Guanajuato strawberry); the HS-code ambiguity already noted in Trade Intelligence V1 (raspberry/blackberry combined) would limit any trade-side corroboration regardless. |
| BM-T-01/T-02 Antidumping Mexico strawberries | **NOT HELPED** -- this mission's own Part 8 control case confirms weather does not add or compete with the regulatory explanation here; correctly not forced. |
| BM-C-04..08 Corporate investment in Peru blueberry | **NOT HELPED** -- investment/M&A decisions are not weather-explainable events. |
| BM-T-06/T-07 Trade-duty/tariff stories (Chile/Peru/Morocco) | **NOT HELPED** -- trade-policy events, not weather. |
| BM-R-07/08/09 Food-safety recalls (E. coli, Listeria) | **NOT HELPED in this pilot** -- contamination/handling events; a real agricultural-science link between heavy rainfall and produce contamination risk exists in principle, but this pilot did not investigate the specific recall geographies and does not claim it. |
| BM-M-01 Sainsbury's promotion, BM-M-04 Peru-China pivot, BM-M-07 Twin River expansion, BM-M-08 Morocco seminar | **NOT HELPED** -- retail pricing, geopolitical trade-flow decisions, corporate expansion, and event announcements are not weather-explainable. |
| **EARLY-WARNED** | **None of the 50 benchmark events qualify** -- the benchmark is a retrospective set of already-happened events; a genuine early-warning test requires a live, forward-looking case, which Part 12's Chile lead-time proof (not a benchmark event) is the closest this mission can honestly offer. |

This layer materially helps the same real half of the Commercial/Market class Trade Intelligence V1 already identified (BM-M-02/03/05-shaped aggregate-statistic events) by adding context, not new detection -- it does not solve corporate news, retail promotions, trade-policy stories, or food-safety recalls, exactly as the mission itself anticipated.

---

## 15. Technical debt

See `docs/v2/TECHNICAL-DEBT-REGISTER.md` TD-030 through TD-037: spatial granularity (~50km grid vs. named region), production-region centroid uncertainty, baseline-period selection (10-year pilot choice, not a 30-year climate normal), NASA POWER's own model heterogeneity/reprocessing (MERRA2 vs GEOSIT), near-real-time data latency with no backfill, `unusual_temperature_window`'s low specificity (flagged all 7 real test cases including a growth case and a control -- explicitly not used as evidence in this report), the NOAA/ERA5 credential gap, and the config-only (non-entity) production-region mapping.

---

## 16. Coverage matrix

See `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md` -- Weather updated from `NONE` to a real, measured `NONE -> PILOT` status, with a dedicated section citing the real corroboration findings above. Not marked OPERATIONAL anywhere.

---

## 17. Next quantitative lane

**Recommendation: E -- return to source/market coverage, not A/B/C/D.**

Reasoning, grounded in this mission's own real findings:
- This mission's own honest finding (Part 14) is that weather/climate context helps roughly the same narrow slice of the Commercial/Market benchmark class that Trade Intelligence V1 already reaches -- it adds *context* to already-detected trade anomalies, but detects nothing new on its own (no benchmark event is itself weather-shaped). The marginal value of broadening weather geographies (A) or adding freight/currency (B/C) is lower than closing a real, still-open detection gap.
- The Commercial/Market benchmark class is still only partially addressed (Part 14): BM-C-04..08 (corporate investment), BM-T-06/07 (trade-duty response), BM-R-07..09 (food-safety recalls), and BM-M-01/04/07/08 (retail/geopolitical/expansion/event stories) remain entirely NOT HELPED by either the trade or weather quantitative layers -- these are fundamentally qualitative/discovery-source gaps (more targeted news queries, labor/legal-press sources, food-safety-regulator feeds), not quantitative-data gaps.
- Satellite/remote sensing (D) is explicitly deprioritized in the Build Guide until trade + weather + retail all prove useful first; this mission is the second of those three, not the third (retail observation from Variety Intelligence Backbone V1 was a UK-only, variety-name-focused pilot, not a general market-observation layer).
- Returning to source/market coverage (E) -- e.g. a labor/legal-press-scoped query for BM-R-03/R-06, or a food-safety-regulator source (FDA/CFIA recall feeds) for BM-R-07/08/09 -- would directly close real, still-open, already-diagnosed gaps (see `docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md` Section 4's own root-cause distribution) rather than adding a fourth quantitative data class on top of two (trade, weather) whose own honest impact ceiling is now measured.

---

## 18. Validation

Full `pytest`, `validate_records.py`, `build_static.py`, static-leakage self-check, and `git diff --check` -- results in the completion report below. Real, bounded pilot; recurring acquisition proven idempotent via a real second run (5/5 duplicates, 0 new).
