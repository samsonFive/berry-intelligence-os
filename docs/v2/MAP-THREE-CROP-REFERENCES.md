# Three separately reported berry crops in the official Map check

The existing keyless Eurostat check now requests strawberries (S0000),
raspberries (F3200) and blueberries (F3300) in Germany, Spain, France, Italy,
Netherlands, Poland and Portugal. It stays bounded to seven countries, three
explicit crop categories, three indicators and the recent annual window.
Opening Map, review or snapshot pages never fetches data.

Each country/crop keeps its own latest populated year, original source URL,
source units, cell flags and source-update time. An empty future year cannot
remove the prior populated year; missing yields remain missing. Country/crop
pairs are reviewed independently and update only the matching saved reference.
Old strawberry jobs, saved choices, stable figure IDs and history remain valid.
The published reference seed, trusted records and existing domain schemas are
unchanged. The check adds no company or variety growing footprint.

The retained October 31 response has 126 populated historical cells. Its latest
2025 references contain 21 country/crop groups and 42 figures, compared with
seven strawberry groups / 14 figures in the prior capture: 14 additional
country/crop groups and 28 figures are available for review. These are annual
source figures, not current-year estimates or newly selected Map references.
No yields were reported in this bounded response.

France blueberry cells are original 0n values. Eurostat defines this as below
reporting precision, different from a real zero. Review, Map and PDF labels
explain that distinction without changing the stored values or flags. Estimated,
provisional, imputed, forecast and low-reliability flags have readable labels;
unknown flags remain explicit. Case is preserved: n/p are distinct from N/P.
Confidential, not-for-publication, secrecy-restricted and missing cells cannot
be proposed or saved as public reference figures. Original payloads are retained
for inspection; withheld cells are never filled or inferred.

Blackberry has no separate category in this check. Other/mixed berries (F3900,
F3000), almonds (F4300), covered-only strawberries and aggregates are rejected
rather than silently assigned to one of the three crops. Worldwide coverage,
other national sources and human figure decisions remain open. Explicit public
country/berry research remains available through the existing workflow; this
change makes no paid provider calls and introduces no scheduler or new store.

Source definitions:

- [Eurostat crop production metadata](https://ec.europa.eu/eurostat/cache/metadata/en/apro_cp_esms.htm)
- [Eurostat fruit classification](https://ec.europa.eu/eurostat/statistics-explained/SEPDF/cache/1584.pdf)
- [Eurostat observation/confidentiality flags and 0n convention](https://ec.europa.eu/eurostat/data/database?node_code=tag00093)

The versioned capture is reference_capture_for_review. Validation currently
passes all 123 affected tests with one existing ReportLab warning, including
older capture replay, mixed-category rejection, per-crop years, withheld flags,
selection/history/idempotence, public isolation and scoped PDF output. Native desktop/412px review and a two-page scoped PDF review pass; there is no
phone horizontal overflow. Canonical record validation passes. Trusted static validation also passes: 1,797 pages and Pagefind, no private draft
leaks and none of the 14 new unselected crop source URLs in public HTML.
Exact-head full CI and separate release approval remain before release readiness. All 31 accepted requirement definitions
and their order, the protected expansion guide, review decisions and personal
Digest/shared Workspace boundaries remain unchanged.
