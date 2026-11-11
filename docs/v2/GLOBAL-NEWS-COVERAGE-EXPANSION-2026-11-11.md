# Global mainstream and regional News expansion

This increment addresses gaps in the deployed November 11 News route inventory. Baseline production had 20 priority routes and 1,956 default-eligible stories from 353 publisher labels. Those labels include historical publications and do not establish current monitored coverage. The prospective pilot's final independent event recall, exact-link recall, precision and latency remain unscored.

## Collection changes

`industry_pulse/global_publishers.py` adds 26 metadata discovery routes to the existing priority lane: ten public feeds and sixteen seven-day site-restricted searches. Existing NYT, WSJ, Independent, LA Times and Ventura County Star indexed routes remain. New routes cover Reuters, AP, BBC, The Guardian, Huelva local desks, French and Arabic Moroccan news, Chile's Ñuble, Peru, Colombia, Quebec, British Columbia, Germany, New Zealand and India. These are discovery routes, not approved Source records or permission to acquire restricted bodies.

Priority checks increase from seven to twelve per normal refresh. With 46 enabled routes and the existing 15-minute timer, an uninterrupted rotation takes four refreshes, approximately one hour. Regional checks increase from four to six, adding native-language district queries for Quebec, Peru, Chile, Colombia, Morocco, Egypt and Germany. Reservations occur before requests, so failures yield their turn; retained rotating stories survive the next empty check. The shared pipeline lock, bounded fetches, per-route failures, News cache and private pilot receipts are reused. No separate scheduler, provider credit spend or browser-time collection is introduced.

Arabic strawberry/blueberry and German crop/industry terms are recognized before translation. Spanish price and blueberry-season wording, Chilean `frutilla`, Colombian `mora de Castilla`, and unambiguous Quebec `bleuets sauvages` / `bleuets en corymbe` are included. Generic Arabic `توت` and French `bleuet` remain insufficient for crop identity because they also name other plants. Local English translation stays on the existing offline path; source metadata determines relevance. Spanish/French/German recipe exclusions protect the broader native price vocabulary.

## Actual route evidence and limits

November 11 public reconnaissance parsed current NYT Business, Diario de Huelva, Huelva Hoy, La Discusión, La República, La Terre de chez nous, CBC BC, BBC Business/Kent and agrarheute feeds. A repeat CBC attempt timed out; scheduled outcomes remain observable. WSJ Business RSS returned January 24, 2025 entries and is deliberately not activated. WSJ remains indexed metadata coverage; eligible positive controls and body access are separate checks.

Hespress feeds returned 403 in the adapter canary and RNZ's feed returned 403 in reconnaissance. These direct routes are not activated. Indexed alternatives remain explicit, with no access bypass. Huelva Información's guessed section feeds returned 404 and the tested Europa Press channel was a stale fashion feed; none is activated. The Guardian is indexed metadata only in this increment.

The new La Discusión indexed route surfaced “Incertidumbre por El Niño y expectativa de mayores precios marcan la temporada de arándanos en Ñuble.” The previous qualifier rejected its Spanish price/season wording. The added vocabulary admits this regional lead while preserving crop and consumer exclusions. Its public blueberry-topic RSS also supplies the original article URL and November 9 publication timestamp; it replaces the shallow general feed in this increment. The all-crop indexed route remains alongside it. An engineering control is not an independent recall benchmark win. Many current general feeds had zero berry-eligible items; transport is not effective topical coverage.

Collection Ops distinguishes raw candidates from retained discovery leads after collection filtering and deduplication. Historical receipts without the new count display unknown rather than zero. Retained leads precede final News projection and do not prove event recall, source independence or trusted publication. Routes remain unverified until an actual receipt exists; stale checks follow the full rotation interval.

## Ranked remaining gaps

| Priority | Gap | Next evidence required | Owner |
| --- | --- | --- | --- |
| 1 | Independent prospective recall, precision and latency are not established | Review/freeze the independent cohort before joining the collector ledger; report event/exact-link denominators and pre/post-release strata separately | News coverage mission / analyst eligibility review |
| 2 | Search wrappers and title-only stories cannot support body-only supplier or event facts | Resolve public originals through permitted paths; measure retrieval/extraction failures and review high-impact unresolved leads | News acquisition |
| 3 | Public records are uneven globally | Verify Canadian recalls, Egyptian/Moroccan authorities and local water/labor notices before activation | News source expansion |
| 4 | Arabic raspberry/blackberry, Serbian, Vietnamese and other vocabulary/translation are incomplete | Source-specific positive/negative controls, offline translation availability and measured eligible yield | News language coverage |
| 5 | General RSS windows are shallow and site searches yield unrelated suggestions | Verify bounded section feeds or publisher-declared pagination; retain independent lanes and stage counts | News source expansion |
| 6 | Frozen historical benchmark has poor proven source-link recall | Preserve the 31-event reference and failed scores; evaluate bounded acquisition without seeding independent discovery from reference URLs | News recall audit |

The pilot remains November 11 06:38:28.804357 UTC through November 25 06:38:28.804357 UTC. Do not restart it or relabel early observations as expanded-configuration performance. Human publication and Atomic Evidence review, source-photo-first presentation, credited reference photos and zero paid translation/provider spend remain intact.
