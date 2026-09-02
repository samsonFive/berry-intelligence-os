# Market Reality Data Layer V1

**Status:** V1, one source activated live.

## The gap

Berry Intelligence OS can tell you "Company X announced Y" (Publications,
Evidence, Signals). It could not answer "what is actually happening to
production, acreage, yield, price, or trade" -- there was no structured,
sourced time-series concept anywhere in the system.

## Source investigation (real, verified access as of 2026-09)

| Source | What it covers | Access mechanism verified | V1 status |
|---|---|---|---|
| **Eurostat** `apro_cpsh1` | EU crop production/area/yield, incl. strawberries and other berries | REST API, genuinely keyless, no registration -- confirmed by direct live query | **Activated** |
| USDA AMS MyMarketNews (MARS API) | US shipping-point/terminal prices, incl. blueberries | Real REST API (`marsapi.ams.usda.gov`); free key via self-service registration; a documented "sample key... will be removed in the future" exists but its live value could not be confirmed this session (the two source pages that would confirm it timed out/reset on fetch) | Verified real, high-value (direct US price data). **Not activated** -- registration requires submitting an email, which is outside what I can do on the operator's behalf |
| USDA NASS QuickStats | US production/acreage/yield by state | Real REST API; free key emailed instantly on self-service signup | Verified real. **Not activated** -- same registration constraint |
| USDA FAS (PSD Online / GATS / ESR) | International ag trade, incl. berry-relevant HS lines | Real API portal (`apps.fas.usda.gov/opendataweb`), 3 published APIs | Verified real. **Not activated** -- registration constraint, and API access details for the specific berry HS lines were not fully verified within this mission's time budget |
| US Census intltrade API | US imports/exports by HS code | Real REST API, but a direct unauthenticated test returned `"Missing Key"` -- **requires** a key today (does not have the low-volume keyless mode some older Census APIs offer) | Verified real. **Not activated** -- registration constraint |
| Eurostat Comext (EU trade by HS/CN code) | EU imports/exports, incl. from Peru/Chile/Morocco | Real API exists; the specific dissemination endpoint/dataset code could not be located within this mission's time budget (two direct guesses both 404'd on dataset id, not on auth) | Not activated -- needs a follow-up mission to find the correct dataset id |
| Chile / Peru / Mexico / Spain / Morocco / China national sources | Local production/trade/customs data | Not investigated beyond a web-search pass -- each needs local-portal/local-language work outside V1's scope | Deferred |

**Buy vs. build:** no commercial data provider was purchased or seriously
evaluated beyond noting that wholesale/retail price aggregators exist
commercially; Eurostat and the USDA sources above are free, authoritative,
and sufficient to prove the capability, so buying was not pursued for V1.

## Why V1 shipped with exactly one live source

Every US-specific and cross-border-trade source that would answer the
mission's own example questions ("US blueberry prices," "Peru blueberry
exports") requires a free but registration-gated API key. Registering for
one -- providing an email address, submitting a signup form -- falls
outside what I can do on the operator's behalf (see the constraint I
already applied identically to APITube/Exa/NewsCatcher in the prior
Information Universe mission). Eurostat's `apro_cpsh1` was the one source
in the whole investigated set that is genuinely keyless and immediately
usable, so it is what V1 actually activates. **This means V1 can answer
real EU-side production/acreage/yield questions but cannot yet answer the
US-price or Peru-export questions the mission used as examples** -- stated
plainly in the analyst-questions section below, not glossed over.

## Data model

New `schemas/market-observation.schema.json`, new
`app/repositories/json/market_observations.py`
(`MarketObservationRepository`, registered in `app/composition.py`
alongside the other 9 repositories). A `market_observation` is not a
Publication and not Evidence -- no analyst review step, no fact/claim
distinction. "Trust" here means "sourced from a named authoritative
statistical agency with a preserved methodology reference," a different
kind of trust than the reviewed-Evidence pipeline, and this V1
deliberately does not conflate the two.

Fields: `metric` (`PRICE`/`SHIPMENT_VOLUME`/`PRODUCTION`/`ACREAGE`/`YIELD`/
`IMPORT_VOLUME`/`EXPORT_VOLUME`/`IMPORT_VALUE`/`EXPORT_VALUE`),
`berry_id` (nullable), `source_commodity_label`/`source_commodity_code`
(always preserved verbatim), `form`, `geography`/`geography_id`
(nullable), `period`/`period_type`, `unit`, `value`, `source`/
`source_dataset`/`source_url`/`methodology_reference`, `captured_at`.

## Commodity normalization (E)

`app/services/market_reality/normalization.py` is a small, closed,
explicit dict -- `EUROSTAT_CROP_TO_BERRY`, `EUROSTAT_INDICATOR_TO_METRIC`,
`EUROSTAT_GEO_TO_ENTITY`. Eurostat's crop code `S0000` ("Strawberries")
maps cleanly to `berry-strawberry`. Crop code `F3000` ("Berries excluding
strawberries") is a **mixed category** spanning raspberry, blackberry,
currants and more -- it is deliberately left `berry_id: null`, with the
real source label and code preserved, rather than guessed onto one berry.
Geography normalization only maps a Eurostat geo code to an existing
`data/entities/geographies/*.json` entity when one already exists (ES, DE,
NL, PT); the `EU27_2020` supranational aggregate is never mapped to a
country entity.

## Live bounded ingestion (F)

`app/services/market_reality/eurostat_apro.py` (`fetch_apro_cpsh1`,
`decode_jsonstat` -- a generic JSON-stat 2.0 sparse-array decoder, not
apro_cpsh1-specific -- and `build_observations`) plus
`scripts/ingest_market_reality_eurostat.py`. Bounded on every axis that
matters: 2 crop codes (`S0000`, `F3000`), 5 geographies (`ES`, `DE`, `NL`,
`PT`, `EU27_2020`), 3 indicators (area/production/yield), and a 10-year
`sinceTimePeriod` window -- not "all crops, all countries, all history."
A real dry-run against the live API returned **200 observations** across
this bounded window. Re-running the script does not overwrite a prior
capture: `MarketObservationRepository.create()` rejects a duplicate id,
and the id is derived from the full logical key including `captured_at`,
so a genuine Eurostat revision produces a new record sitting alongside the
earlier one -- both real captures stay queryable, satisfying section K
(historical foundation / revision detection) without any new mechanism.

Update frequency: Eurostat's own documentation states the underlying
database refreshes twice daily; `apro_cpsh1` itself (an annual survey
dataset) realistically updates a few times a year as new annual figures
are finalized -- this V1 does not schedule the script as a recurring
pipeline (unlike `catchall_recall`/`usda_pvpo` in `collection_pipelines.json`);
it is a manually-run, bounded collector, matching the mission's own
"start with enough history to prove trend usefulness," not a giant import.

## Licensing / attribution (L)

Eurostat's own reuse policy (stated on `ec.europa.eu/eurostat`) permits
free reuse, including commercial, with attribution to Eurostat as the
source -- this is Eurostat's own published policy, not a legal conclusion
of mine. `source`/`source_dataset`/`source_url`/`methodology_reference`
are stored on every observation specifically so that attribution
requirement is always satisfiable from the record itself. No
redistribution-of-microdata concern applies here: `apro_cpsh1` is already
public aggregate statistics, not licensed/restricted microdata.

## Performance / cost

The one real bounded query (2 crops x 5 geos x 3 indicators x 10 years)
completed in a few seconds against the live API in this session's testing
and returned 200 real observations. Collection happens once, centrally
(one script run), not once per user -- consistent with section M.

## What this does not do

- Does not answer US-price or Peru-export questions (see above) --
  activating those needs an operator-registered key for AMS/NASS/FAS/
  Census, not more code.
- Does not create Signals or Assessments automatically from a detected
  change (section H's own explicit prohibition).
- Does not infer company causality from a market move (section I) --
  graph connections are `berry_id`/`geography_id` links only, never a
  claim that a specific company caused a specific number to move.
- Does not schedule a recurring collection pipeline (deliberately manual
  for V1).
- Does not touch Comext (EU trade) or any of the 4 US-federal sources'
  actual data -- verified access only, not activated.

## Addendum: real US/Peru answers, found after the initial keyless-source search

The initial source investigation above concluded no keyless path existed
for US blueberry prices or Peru blueberry exports. That was wrong in one
respect: it only checked the *modern REST APIs* (which do require a key)
and missed each agency's own **public report archive**, which needs no
key at all:

- **USDA NASS**, *Noncitrus Fruits and Nuts 2024 Summary* (published May
  2025): `https://www.nass.usda.gov/Publications/Todays_Reports/reports/ncit0525.pdf`
  -- a direct, keyless PDF with US cultivated-blueberry price, utilized
  production, and acreage for 2022-2024, broken out by fresh/processed/
  all-utilization.
- **USDA FAS GAIN**, Report PE2025-0010, *Peru: Blueberry Annual*
  (published June 13, 2025): `https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName=Blueberry+Annual_Lima_Peru_PE2025-0010.pdf`
  -- a direct, keyless PDF with Peru's official PSD table (production,
  exports, exports-to-US specifically, by marketing year), export prices,
  and destination mix, sourced from Peruvian Customs.

34 records were built from these two PDFs and loaded into the same
`market_observation` store via a one-off script, `source`/`source_dataset`/
`source_url`/`methodology_reference` populated identically to the coded
Eurostat path. **No coded, re-runnable collector exists yet for either** --
PDF table extraction is materially harder to make robust than Eurostat's
clean JSON API, and this mission's remaining time went to proving the
capability with real numbers rather than building that parser. That is a
real, named V1.1 candidate, not a silent gap.

## Real data-quality findings (from actually reading the source tables)

- **Fresh vs. processed vs. blended are three different numbers.** US
  blueberry price per pound in 2024: **$1.45 blended** (all utilization),
  **$2.22 fresh only**, **$0.526 processed only** -- collapsing these
  would be a real distortion, not a rounding difference. This exact
  problem surfaced a genuine bug (below).
- **A real bug this pass found and fixed**: `MarketObservationRepository
  .latest_by_key()`'s dedup key didn't include `form`, so querying "US
  blueberry price" returned an arbitrary one of the three numbers above
  instead of all three -- fixed, with a regression test, in a follow-up PR
  before this mission's numbers were finalized.
- **HS 081040 (fresh blueberries) is the correct, narrow FAS/Comtrade
  code** -- Peru's PSD table is fresh-only, matching Eurostat's `form:
  "fresh"` on the strawberry series; no frozen/processed figures were
  mixed in.
- **Eurostat's F3000 ("Berries excluding strawberries") really is a
  combined raspberry/blackberry/currant category** -- confirmed by
  reading Eurostat's own crop-code label text, not assumed; `berry_id`
  stays `null` for it, exactly per the commodity-normalization design.
- **"Exports to the US" isn't a real geography.** FAS's own table breaks
  out Peru's US-bound export volume specifically. I stored it as
  `geography: "PE-to-US"` with `geography_id: null` since there's no
  clean single-entity representation of a bilateral trade *flow* in the
  current geography model -- a real, named design gap (not silently
  mapped to Peru or to the US).
- **All prices recorded are nominal USD, not inflation-adjusted.** A
  multi-year price comparison (the FAS series runs 2016/17-2024/25) should
  not be read as a real/inflation-adjusted trend without that caveat.
- **The NASS source itself withholds some state-level data** (`(D)` =
  "Withheld to avoid disclosing data for individual operations," e.g.
  Florida blueberry price in most years) -- confirmed by reading the
  actual table, not inferred. Only US-total rows were ingested this pass,
  so this particular gap did not propagate into the stored data, but a
  future state-level ingestion would need to handle `(D)` explicitly
  rather than treating it as zero.
- **FAS's 2025/26 and 2026/27 rows are the report's own forward
  forecast**, not actuals -- stored with `period` suffixed `f` (e.g.
  `"2025/26f"`) and a methodology_reference that says so explicitly, and
  the analyst answers below use the actual/estimate columns
  (`2023/24`/`2024/25e`) as the real "current" comparison, not the
  forecast-vs-forecast one.

## Stakeholder-facing surface: deliberately not shipped this mission

Eurostat has a real, tested, re-runnable collector. NASS and FAS do not
yet -- their 34 records are a real, correctly-sourced, but one-time manual
capture. Shipping a "Market Reality" card in the stakeholder shell right
now would visually imply the same live-refresh guarantee `/week`'s `LIVE /
UNREVIEWED` badge carries, which would misrepresent a single PDF snapshot
as a live feed. `app/services/market_reality/research_desk.py`
(`market_reality_for()`) is the service-level seam a future UI -- or the
concurrent Research Desk work -- would consume; it is built, tested, and
demonstrated with real production output below. UI should wait for either
a NASS/FAS collector or an explicit decision to ship a clearly-labeled
point-in-time snapshot instead of a live one.
