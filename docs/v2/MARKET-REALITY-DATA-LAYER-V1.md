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
