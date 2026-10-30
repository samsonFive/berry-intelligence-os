# Market references for the countries selected on the Map

Market research previously offered only countries with an existing catalog
record, while the Map already supported many more country selectors. Saved
statistics for those selectors could also disappear from a country-filtered
Map or snapshot. The research picker now reuses the Map's selectable country
identities. A unique catalog country takes precedence; a reference-only ISO
selector does not create an intelligence record, relationship or footprint.
Ambiguous catalog country codes remain unavailable for research.

France also had missing ISO metadata in the existing boundary asset. A small,
explicitly sourced correction makes its existing polygon selectable without
changing geometry or the original GeoJSON. It applies only to the one named
feature while both original codes remain the expected missing-value markers.
Changed or ambiguous source metadata requires another review. Other missing
boundary codes, including Norway, remain unresolved; this is not a claim of
complete worldwide selection or statistical coverage.

The code mapping is supported by [UN M49](https://unstats.un.org/unsd/methodology/m49/)
and [Eurostat's France series](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/apro_cpsh1?format=JSON&lang=en&freq=A&crops=S0000&geo=FR&time=2025).

## What an analyst can do

1. Select a country and berry on Map Explorer.
2. Open **Check & review market figures**. The explicit Eurostat source check
   covers strawberries in Germany, Spain, France, Italy, Netherlands, Poland
   and Portugal. Other available country/berry combinations use the existing
   explicit research action and its provider requirements.
3. Compare the captured figures with current references. Nothing is selected
   or saved automatically. Choose only the sources and figures actually checked.
4. Save selected reference context to the shared analyst runtime. This does not
   approve news, claims, company presence or variety growing regions.
5. Return to the same Map scope or choose individual figures for a Market
   Snapshot and PDF. Country names, source units, annual periods, original
   source links and source-update dates accompany the numbers.

The picker contains 236 available countries and areas on the unchanged public
seed. A later catalog record for the same unique country does not make an
earlier saved ISO reference disappear; saved records are not rewritten.

## Captured reference material

The retained October 29, 2026 Eurostat JSON-stat response reproduces seven
country groups and 14 source figures for calendar year 2025. The three added
country groups are:

| Country | Area, 1000 ha | Harvested production, 1000 t |
| --- | ---: | ---: |
| France | 3.71 | 74.05 |
| Italy | 4.33 | 123.83 |
| Poland | 28.2 | 168.9 |

The source was updated October 27, 2026. That date is not represented as a
publication date. Missing yields remain missing; none are calculated. Original
flags, zero/missing distinctions, category definitions and units are retained.
Countries are not added together or allocated to companies. The versioned
capture under `data/imports/map-market-references-2026-10-28-expanded/` is marked
`reference_capture_for_review`; it does not modify the published reference seed.
These figures are not current-year production estimates or live news.

## Review and limits

All 136 affected checks pass, with one existing ReportLab deprecation warning.
They cover source/country/crop mismatch rejection, explicit country selection,
unchanged public references, private/shared research boundaries, ISO-only and
mixed scopes, later catalog identity, missing coverage, original units, source
provenance and PDF output. Desktop and 412px phone review used a disposable
public-seed runtime and fictional account. Only France was saved in that fixture;
other proposed countries and production data were untouched.

PDF review caught internal catalog terminology in the country summary and an
omitted section being described as a data gap. Snapshot exports now show country
names and retain actual coverage gaps, without treating unselected sections as
missing data. A dataset update is labeled separately when no publication date
is supplied. Existing report edits and citation/source numbering are unchanged.

The original 31 accepted requirement definitions and order, protected expansion
guide, canonical entities, rights/CPVO/variety schemas and footprints, Trade and
Weather normalization, raw boundary geometry and published reference seed are
unchanged. This child follows Learn #437 and carries its catalog history. It
needs its own exact-head checks and intended release review. Platform #433 was
separately approved and deployed October 29; this Map work is excluded from it.
Human source/catalog decisions and broader world/crop coverage remain open.
