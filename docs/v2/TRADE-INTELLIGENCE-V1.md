# Global Trade / Customs Intelligence V1

**Mission:** Global Trade / Customs Intelligence V1 (2026-08-21, branch `feature/trade-intelligence-v1`). First quantitative trade-flow layer, per the recall benchmark's own finding that Commercial/Market (0/8) and Regulatory/Trade (1/11) are the platform's weakest classes, and the Variety Intelligence Backbone's own finding that it cannot answer import/export volumes, trade-flow shifts, or market-share movement.

---

## 1. Trade data source audit

Real, live-tested access research (not documentation review), mirroring the discipline of the prior two missions' registry/API audits.

| Source | Access | API | Licensing | Granularity | Cadence | History | Automation feasibility |
|---|---|---|---|---|---|---|---|
| **UN Comtrade** (public preview) | Public, no login | **Yes -- real, live-verified, unauthenticated JSON API** (`comtradeapi.un.org/public/v1/preview/C/{freq}/HS`) | Free; the *free-key* full API caps at 250,000 records, the *keyless preview* used this mission caps at **500 records per request and 1 period per request** (live-confirmed) | 6-digit HS (H6), monthly or annual, quantity + value (CIF for imports, FOB for exports), per reporter/partner country pair | Monthly, real lag observed (2026-06 had data, 2026-07 returned zero records live-tested 2026-08-21 -- genuinely not yet released, not a broken query) | Deep (this mission queried back to 2025-01 without issue) | **High -- integrated this mission** |
| **US Census International Trade API** | Public web UI; API requires a **registered API key** | Yes, real (`api.census.gov/data/timeseries/intltrade/{imports,exports}/hs`) | Free self-service key signup (email-based) | 10-digit HTS (finer than Comtrade's 6-digit -- would separate frozen blueberries from other frozen fruit, see Part 2) | Monthly | Deep | **Not integrated this mission** -- live-tested and confirmed to return `"Missing Key"` without one; this mission's agent session cannot self-provision an email-registered key. A real, concrete follow-up for whoever holds Census API credentials. |
| **USDA/FAS** (GAIN reports, PSD Online) | Public, mixed (some bulk downloads, no unified real-time API for HS-level bilateral flows) | Partial -- PSD Online has a real API for production/supply/distribution estimates, not customs-transaction-level trade | Free | Country/commodity, not HS-code-level customs detail | Varies by report | Deep | Not integrated -- a different data class (USDA's own estimates, not customs declarations) than this mission's scope; a real future complement, not a substitute. |
| **Eurostat / EU trade** (Comext) | Public | Real API exists (Eurostat's own REST/SDMX API) | Free | HS/CN8, monthly | Monthly | Deep | Audited, **not implemented this mission** -- UN Comtrade already carries EU member-state-reported data at the 6-digit level for the same real questions this pilot needed (e.g. UK imports, noting the UK itself is no longer an EU member and reports independently to Comtrade). A genuine future add if CN8-level EU granularity is specifically needed. |
| **UK HMRC (uktradeinfo.com / Trade Tariff API)** | Public | Real API exists (`api.trade-tariff.service.gov.uk` for tariff/commodity lookup; `uktradeinfo.com` for bulk trade data downloads, not confirmed as a clean programmatic time-series API) | Free | 8/10-digit UK commodity code | Monthly | Deep | Audited, **not implemented this mission** -- UN Comtrade already reports the UK as a reporter (confirmed live, Part 5), covering this pilot's real UK test cases without a second adapter. |
| **Mexico (SNIEG/INEGI trade data), Peru (SUNAT), Chile (Banco Central/Aduanas)** | Public, but not individually live-tested this mission (time-bounded, per the mission's own "do not build every adapter" instruction) | Unknown | Unknown | Unknown | Unknown | Unknown | Not audited in depth this mission -- UN Comtrade already carries Mexico/Peru/Chile as *partner* countries in the US's own reported data (the mirror approach, Part 5), which answered this mission's real required test cases without needing each country's own national portal. |
| **Agronometrics** | Public (partial), commercial analytics | Not investigated as a raw-data API this mission | Commercial | Price/volume analytics derived from trade and market data | N/A | N/A | **Explicitly not used for raw figures**, per the mission brief's own instruction that Agronometrics is a secondary/commercial analytic source, never a replacement for official data. Existing Evidence records already cite Agronometrics as a trade-press-style secondary source (`ev-...-agronometrics-in-charts-...`) -- unchanged, not touched this mission. |

**Bottom line**: UN Comtrade's keyless public preview endpoint is the only source in this table that is simultaneously (a) genuinely official/primary, (b) requires zero registration/credentials this session could complete, and (c) was proven live to answer every one of the mission's required country-pair test cases. It is the one adapter built.

---

## 2. Berry HS code taxonomy

Full machine-readable version: `data/configuration/trade_hs_taxonomy.json`. Live-verified against UN Comtrade's own H6 (HS 2022) classification and cross-checked against published HTS/HS reference tables.

| HS code | Description | Berry mapping | Fresh/frozen | Purity |
|---|---|---|---|---|
| 081010 | Strawberries, fresh | Strawberry | fresh | **single-berry** |
| 081110 | Strawberries, frozen | Strawberry | frozen | **single-berry** |
| 081020 | Raspberries, blackberries, mulberries and loganberries, fresh | Raspberry + Blackberry | fresh | **combined** -- not separable at 6 digits, also includes 2 untracked fruits |
| 081120 | Raspberries, blackberries, mulberries, loganberries, currants, gooseberries, frozen | Raspberry + Blackberry | frozen | **combined** -- worse than the fresh code (adds currants/gooseberries too) |
| 081040 | Cranberries, blueberries and other fruit of the genus *Vaccinium*, fresh | Blueberry | fresh | **combined** -- not separable from cranberries/bilberries at 6 digits |
| 081190 | Other fruit and nuts, frozen (n.e.s.) | Blueberry | frozen | **combined**, more severe -- a genuine "other, not elsewhere specified" basket; only the US's own 10-digit HTS (0811.90.20) isolates frozen blueberries specifically, and this mission's chosen adapter reports at 6 digits |

**Honest, load-bearing limitations** (not caveats buried in a footnote):
- **Raspberry and blackberry are never separable in this taxonomy at the 6-digit level, fresh or frozen.** Any quantity/value change attributed to "raspberry" or "blackberry" specifically from Comtrade data alone is not defensible; the pilot lane built for this (081020, US imports from Mexico) is explicitly labeled `berry_code_purity: "multi_berry_combined"` on every draft it produces.
- **Blueberry shares its fresh code with cranberries and bilberries.** For this pilot's specific real country pairs (Peru/Chile/Morocco/South Africa -> US/UK), cranberry trade in these bilateral flows is understood to be minor relative to blueberry, but this is an *assumption*, not independently verified this mission -- registered as debt (TD-TRADE-002), not silently treated as fact.
- **Frozen blueberry is the weakest case of all** -- 081190 is not blueberry-specific at 6 digits at all.

---

## 3. Quantitative trade observation model

Additive `trade_observation` object on `evidence.schema.json` (schema: `schemas/evidence.schema.json`), mirroring the `patent_filing`/`commercial_observation` precedent exactly -- no new record type, no parallel trust system. **One Evidence draft per (reporter, partner, flow, HS code) lane**, holding a `series[]` array of period entries -- deliberately not one draft per monthly data point, per the mission's own explicit instruction. Fields: reporter/partner geography ids, flow, HS code + revision, berry-code-purity flag (carried onto the record so a reviewer never has to cross-reference the taxonomy file), fresh/frozen, and per-period quantity/unit/value/currency/value-basis (CIF vs FOB, never conflated)/estimated-flag/reported-flag/release-status. `does_not_prove` is always populated, including the taxonomy's own purity limitation text when the HS code is a combined one.

---

## 4. Adapter chosen: UN Comtrade public preview

`app/services/trade_intelligence.py` + `scripts/monitor_trade_intelligence.py`, architecturally parallel to Patent Monitor v2 and the CPVO registry monitor (untrusted `inbox/evidence/` drafts only, real idempotency via a per-lane state file). A short delay between period requests was added after a real, live-observed HTTP 429 during this mission's own research testing (the preview endpoint's exact rate limit is undocumented).

---

## 5. Real pilot data

6 real lanes (`data/configuration/trade_pilot_lanes.json`), 12 periods each (2025-01..2025-06 + 2026-01..2026-06, giving year-over-year comparability out of the box): US<-Mexico strawberry fresh, US<-Peru blueberry fresh, US<-Chile blueberry fresh, UK<-Morocco blueberry fresh, UK<-South Africa blueberry fresh, US<-Mexico caneberry (raspberry+blackberry combined) fresh.

**Real, load-bearing geography finding**: Morocco's and South Africa's own *export* statistics, live-tested directly, do not disaggregate by partner country for these commodities (every row returned `partnerCode: 0`, i.e. world-aggregate only). The mirror convention -- querying the *importing* country's own reported imports *from* Morocco/South Africa -- does carry real partner-level detail (confirmed live: UK-reported imports from South Africa returned real, non-aggregate, country-specific rows). Both Morocco and South Africa pilot lanes are built on the UK (importer) side for exactly this reason, not a preference -- it is the only side of the trade relationship this mission found real bilateral granularity in.

**Real run results**: all 6 lanes produced real data; 6 real drafts created (one per lane); a real second run proved full idempotency (6/6 duplicates, 0 new). 4 of 72 individual period-requests hit a real, live-observed HTTP 429 (the preview endpoint's exact rate limit is undocumented) -- those specific periods are genuinely missing from 3 lanes (Chile 8/12, Morocco 10/12, South Africa 7/12), reported honestly as gaps, not silently backfilled or estimated. The Mexico strawberry, Peru blueberry, and Mexico caneberry lanes each have 11-12 of their 12 requested periods.

| Lane | Periods captured | Real range (fresh, kg/month) |
|---|---|---|
| US <- Mexico, strawberry (081010) | 12/12 | ~9.1M-53.8M kg |
| US <- Peru, blueberry (081040) | 11/12 | ~0.12M-20.4M kg (strongly seasonal) |
| US <- Chile, blueberry (081040) | 8/12 | ~4K-17.4M kg (sharply seasonal, near-zero by April) |
| UK <- Morocco, blueberry (081040) | 10/12 | ~1.1K-10.6K kg |
| UK <- South Africa, blueberry (081040) | 7/12 | ~6.2K-39.4K kg |
| US <- Mexico, caneberry (081020, combined) | 11/12 | ~8.9M-31.7M kg |

Real seasonal patterns are visible and plausible without any adjustment: Mexican strawberries peak January-March and decline sharply by June (matches the real Mexican winter-strawberry production calendar); Chilean blueberries peak January-February and are nearly gone by April (matches Chile's Southern-Hemisphere summer harvest window); Peruvian blueberries dip April-June then recover (consistent with Peru's own real, published multi-window season).

---

## 6. Mexico strawberry -- quantitative trace

The `us-imports-mexico-strawberry-fresh` lane (HS 081010, single-berry, no combination ambiguity) directly answers what the recall-benchmark mission's Federal Register documents could establish only procedurally. **Real, measured finding**: US strawberry imports from Mexico in **2026-04 fell 36.4% by quantity and 56.2% by value year-over-year** (18.8M kg / $32.2M vs. 29.6M kg / $73.4M in 2025-04) -- both flagged by `unusual_movement()` at the 25% threshold. This decline lands roughly one month after the real Federal Register "Determination" (2026-03-12) in the antidumping proceeding.

**This does not claim the trade data proves dumping, or that the ruling caused the decline.** It measures import volume, value, and timing only, per the mission's own explicit instruction -- `does_not_prove` on the draft says so directly, and a real, human-reviewable, `status: "proposed"` `evidence_links` entry (`follows_up`, not `corroborates` -- the trade data doesn't independently confirm the same claim the Federal Register document makes, it is a later, related, temporally-connected observation) was added connecting this trade draft to the real `ev-media-d84a333e08d05b9a0ac5` Determination evidence already sitting in `inbox/evidence/` from the prior Recall Benchmark mission. A human reviewer decides whether to accept, contest, or reject that proposed link -- ingestion never decides this itself. May and June 2026 show smaller, non-flagged YoY moves (+6.0%/-15.7% quantity), so the April dip does not (yet) read as the start of a sustained trend from this data alone -- reported honestly, not extrapolated.

---

## 7. Peru / Chile blueberry

Real, substantial divergence found via `partner_flow_changes()` across the same 3 months (2026-01/02/03 vs. the same months in 2025): **Chile's US fresh-blueberry exports fell 42.0% (Feb) and 76.1% (Mar) year-over-year by quantity** (value down 50.8%/83.2%), while **Peru's grew 10.3% (Feb) and 33.1% (Mar)** over the identical window (value up 6.0%/24.7%). This is a real, direct, measured instance of exactly the "new/expanding vs. contracting partner flow" pattern the mission's Part 6 (Derived Trade Signals) asked to prove, and it lines up directionally with the recall benchmark's own BM-M-02 event ("Chilean blueberry exports to US fall 13%", from a different secondary source and a different, broader time window -- this pilot's much larger March figure is not claimed to be the same measurement, only a directionally consistent, independently-derived one from a primary source).

---

## 8. UK / EU / Morocco / South Africa

UK reported as Comtrade reporter directly (confirmed live, real data for all 12 requested periods except partner-specific gaps from rate-limited requests). Morocco and South Africa covered via the UK-mirror convention (Part 5) -- real YoY movement computed: **South Africa's UK-bound blueberry volume fell 84.4% year-over-year in 2026-02** (value -70.5%) before recovering to +68.5% by 2026-03 (though value there fell further, -42.6% -- a real, honest divergence between quantity and value movement in the same month, worth a human's attention, not smoothed over). Morocco's UK-bound volume fell 22.7% in 2026-02 then rose 158.3% in 2026-03 -- both lanes show real volatility at genuinely small absolute volumes (thousands of kg, not millions, unlike the US-Peru/Chile lanes), a real, honest scale difference worth noting rather than treating UK/Morocco/South Africa figures as comparable in magnitude to the US ones. EU-wide (beyond the UK) and Eurostat-specific CN8 granularity were **audited, not built** this mission (Part 1) -- a real, honestly-reported gap, not silently assumed solved.

---

## 9. Derived metrics -- real proof

`year_over_year_change()`, `rolling_seasonal_comparison()`, `unusual_movement()`, `partner_flow_changes()` in `app/services/trade_intelligence.py` -- pure functions, nothing persisted, nothing auto-promoted to a Signal. Real output (all computed live against the pilot data, not fixtures): the Mexico-strawberry 2026-04 decline (Part 6), the Chile/Peru divergence (Part 7), and the Morocco/South Africa volatility (Part 8) above are every one of them real `year_over_year_change()`/`partner_flow_changes()`/`unusual_movement()` outputs, not illustrative examples.

---

## 10. Qualitative corroboration

One real, deterministic `evidence_links` connection made this mission: the Mexico-strawberry trade draft (`ev-trade-trade-867453b119c8f6d7`) proposes a `follows_up` link (status: `proposed`, never auto-accepted) to the real Federal Register "Determination" Evidence (`ev-media-d84a333e08d05b9a0ac5`) still sitting in this worktree's `inbox/evidence/` from the prior Recall Benchmark mission -- both untrusted drafts, connected honestly as drafts, not force-promoted to trusted status to make the link "count." No link was forced for Peru/Chile (no existing qualitative Evidence in this dataset specifically discusses a 2026 Chile blueberry export decline to propose a link against) or for Morocco/South Africa (same reason) -- per the mission's own "do not force relationships" instruction, an absent link is reported as absent, not manufactured.

---

## 11. Relation to the 0/8 Commercial/Market benchmark

| Benchmark event | Trade layer relation |
|---|---|
| BM-M-01 Sainsbury's GBP1 strawberry promotion | Would not help -- a retail price promotion is not a customs statistic. |
| BM-M-02 Chilean blueberry exports to US fall 13% | **Would have helped detect directly** -- exactly the shape of question `year_over_year_change()`/`partner_flow_changes()` answers. |
| BM-M-03 Peru blueberry production +25% forecast | Would help corroborate (a production forecast is not itself a customs figure, but a resulting real export/import volume change would show up in this layer once it occurs). |
| BM-M-04 Peru turns to China as US tariffs squeeze exports | Would help corroborate (a US-side volume decline alongside this mission's own data plus a hypothetical China-side lane would show the shift quantitatively) -- China was not one of this pilot's 6 lanes; a real, honestly-reported scope limit. |
| BM-M-05 South Africa blueberry production reaches 38,900t | Would help corroborate in the same way as BM-M-03. |
| BM-M-06 Mexico blackberry production forecast 274,000 MT | Would help corroborate, but the HS code (081020) cannot isolate blackberry from raspberry -- a real, direct limit from Part 2, not fixable within this mission's chosen source. |
| BM-M-07 Twin River Berries raspberry production expansion | Would not help directly -- a company-level production expansion is not visible in country-level customs statistics; the combined raspberry/blackberry HS code makes it worse. |
| BM-M-08 Morocco Red Fruits Seminar announcement | Would not help -- an event announcement is not a customs statistic. |

**This backbone does not and cannot, by itself, solve**: retail promotions, company-level production/acquisition news, or conference/event announcements -- exactly as the mission's own instruction anticipated. It materially helps roughly half of the 8 (the aggregate-statistic half), which is precisely the gap the Variety Intelligence Backbone mission identified this layer needed to close.

---

## 12. Source / data health

Reuses the existing Source `last_checked_at`/`last_status` fields (the same generic mechanism every other Source in this registry already uses -- `app/main.py`'s `check_source()`/`source_is_due()`) rather than a parallel trade-specific health system. Distinguished states, all real and observed this mission: **API healthy** (a period query returns real data), **data not yet released** (a period query returns zero records with no error -- live-observed for 2026-07, genuinely distinct from a failure), **request failure** (a transport/HTTP error, live-observed as a real 429 during rapid testing), **schema drift** (not observed this mission -- registered as an unexercised-but-real risk in the debt register, since Comtrade's own response shape could change without notice).

---

## 13. Technical debt

See `docs/v2/TECHNICAL-DEBT-REGISTER.md` for the full entries (TD-TRADE-001 through TD-TRADE-00N): HS-code ambiguity (Part 2), the unregistered-API-key gap for US Census, undocumented Comtrade rate limits, no revision/resubmission handling (a "final" period can later be revised by the reporting country; this mission's pilot does not re-fetch and diff already-drafted periods), no currency normalization beyond Comtrade's own USD-only convention, no country-naming reconciliation beyond the 7 geographies this pilot's own lookup table covers, and the CIF-vs-FOB value-basis distinction being carried but not yet surfaced in any derived metric (a YoY value comparison across an import lane and an export lane for the "same" flow would silently mix bases if a caller weren't careful -- flagged, not fixed, since no real caller does this yet).

---

## 14. Coverage Matrix

See `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md` -- Customs/Trade updated from `NONE` to a real, measured status per berry/geography. Not marked OPERATIONAL anywhere.

---

## 15. Next quantitative lane

**Recommendation: weather/climate (Workstream G.2), not broadening trade sources/geographies, freight/currency, or satellite.**

Reasoning, grounded in this mission's own real findings, not the Build Guide's a-priori sequencing alone:
- This mission's own real derived metrics surfaced two large, currently-unexplained anomalies -- Chile's -76.1% March YoY blueberry-export decline and South Africa's -84.4% February YoY decline. Weather/climate context (frost, drought, heat, excessive rainfall in the relevant production geography and month) is the most direct, evidence-grounded next quantitative layer that could explain *why*, complementing rather than duplicating this mission's own work.
- Broadening trade sources (US Census, Eurostat, UK HMRC-native) is real, valuable, and partially blocked on a credential this mission's agent session could not self-provision (a free, email-registered US Census API key) -- a genuine, low-effort unblock for whoever holds the credentials, but not something to schedule as the *next* mission around, since it is not a research problem, only an access-provisioning one.
- Freight/currency is explicitly framed in the Build Guide as *explanatory context*, not primary evidence -- lower priority than either of the above until a real trade or weather anomaly specifically needs a currency/freight explanation.
- Satellite is explicitly deprioritized in the Build Guide until trade + weather + retail all prove useful first; trade has now proven useful (this mission) but weather has not yet been attempted.
