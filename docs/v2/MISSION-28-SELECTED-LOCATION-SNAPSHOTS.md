# Mission 28 — Selected locations in Market Snapshot

Map Explorer now carries its country, berry, layer, company/list/mark and location scope into the snapshot composer and preserves that scope on return. Recorded company and variety locations are optional: the user selects each entry explicitly before including it. Opening or exporting a snapshot does not initiate research, change annotations or approve sources/statements.

## Delivered behavior

Selected entries include the saved name, country/locality, activity, status, observed/effective date, source publication date, basis, notes, limitations and original supporting URL. Unknown dates remain unknown. Trial and commercial-growing activities stay distinct. Private annotations are labeled unreviewed and their PDF is marked Internal / Confidential. A source link does not confirm the location or its commercial scale.

Location options reuse the shared region catalog and filters. A removed or out-of-scope selection returns a composition error instead of silently exporting stale/private material. Public/read-only options do not read private annotations or raw research. Locations are excluded by default; selecting a checkbox while its section is disabled does not include its private notes in the exported content.

The PDF uses compact labeled location tables, readable headings, intact qualifications and named source references. Only actually cited sources contribute to the latest-source date. Location-only exports do not derive their date or evidence count from unrelated news. Statistics-only and location-only exports likewise omit unrelated news from their source packet. Long saved notes remain intact across page breaks.

Browser review found that the map script replaced the server's snapshot link with country/berry alone. It now preserves the full form scope. Phone review also found that long notes could make a table column excessively wide; fixed column proportions, wrapped notes and a focusable scrolling region keep the table readable within its container. Guide reporting copy now describes the live capability without advertising private annotations in the public snapshot.

## Verification

Focused Snapshot, Explorer, Map, market-reference, Report, static safety and Guide checks: **132 passed / one existing ReportLab deprecation warning in 18.70 seconds**. The final Snapshot, Explorer, static and Guide follow-up had **39 passed / one warning in 16.07 seconds** after the phone-table and scope-copy fixes. Canonical records validated, whitespace checks passed and the canonical expansion guide has no diff.

The browser used an ignored, isolated loopback runtime. A fictional, human-corrected variety trial was selected through the composer; its unknown date, unreviewed basis, original URL and literal fictional qualification appeared in the selected-location table. The return link retained its variety layer and profile. Desktop and requested 390px phone rendering were inspected; the table scrolls within its container and its disclosure is accessible. Temporary viewport settings were reset. No live provider call or real/canonical location write occurred.

The actual PDF renderer produced `artifacts/design-sprint/map-locations-snapshot.pdf`, containing two explicitly selected fictional company/variety annotations. Both final pages were visually inspected: both location tables, their notes and source links fit on page one, with known gaps and named sources on page two. This is an illustrative export, not evidence of real operations or growing. Browser and phone images and a first-page PNG accompany it.

## Remaining acceptance

The current news sections retain the existing trusted country/berry snapshot scope; map news date and company/list filters do not narrow those sections. This difference is disclosed in the composer and PDF gaps and remains a cross-view requirement. Location choices use the shared location/company filters, and annual statistics keep their own periods. Trade composition, broader official market coverage/refresh, subnational boundaries, account/worker persistence, real article/media availability, older-PR parity and combined release remain on the ledger. No merge or deployment before final user approval.
