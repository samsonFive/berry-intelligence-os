# Mission 29 — News filters in Market Snapshot

Market Snapshot now uses the shared News selector. Company, watchlist, favorite, tier, text search and publication-date selections carry from Map Explorer into the news sections and PDF. Snapshot news remains Trusted only: source review and active supporting statements are still required. Reading or exporting does not research, capture, approve or change records.

## Delivered behavior

The snapshot uses the same complete matching set and UTC timestamp ordering as News, including all pages. Future publication dates, unsuitable source types and news relevance retain the existing shared rules. Today, past seven/thirty days, year to date, custom timezone bounds and publication-date-unknown selections retain their meaning. Actual timestamp offsets determine newest first and the latest cited source date, rather than lexical timestamp order.

Company/list names and publication windows appear in ordinary language. Generated snapshot prose no longer emits bracketed internal IDs or long inline source URLs; the named source appendix retains original links. Empty sections explicitly say no sources match instead of suggesting that an analyst needs to draft a missing narrative. Saved report prose and its review state are untouched.

Annual market figures keep their own periods; selected location entries retain their saved dates and qualifications. News dates and company marks do not silently remove these separate sections. Statistics-only and location-only packets omit unrelated news selection labels. Read-only/public request handling no longer loads private company marks/lists or private source records.

Browser review also found that the shared feed shortcut handler intercepted Enter on the Create Market Snapshot link and opened the current story. Native links, buttons and disclosure headings now keep keyboard activation; card/background shortcuts and global search/Escape remain available. Shared script references are versioned to invalidate stale browser caches.

## Verification

The initial combined Snapshot, Explorer, News, Map, PDF, shell, static and Guide run passed **164 tests / one existing ReportLab deprecation warning in 23.16 seconds**. A plain-language follow-up initially failed one old assertion that empty inventory sections must be undrafted; it now checks the intentional structured empty result and its exact no-match explanation. The final follow-up passed **103 tests / one warning in 7.40 seconds**. Canonical records validated and the governing expansion guide has no diff.

Actual loopback browser review covered empty Planasa and populated global/Costa company/date scopes: 31 Trusted records in the unfiltered map and snapshot, one matching Costa source for the custom 2026 window, and unchanged scope on return. Enter now follows the snapshot link; Enter on the selected article still opens its Reader; Escape restores focus to that story link. A requested 390px view was inspected after layout settled, with viewport width 390 and document width 375; the temporary override was reset. Desktop and phone screenshots accompany the sample.

The actual PDF renderer produced `artifacts/design-sprint/news-scope-snapshot.pdf` from the one matching stored Costa source. Both pages were visually inspected, including named company/date scope, readable source inventory, latest publication date and named source appendix. This is presentation/filter proof, not a completed market analysis or fresh source capture.

## Remaining acceptance

The browser's explicit original-article capture returned no text; ignored diagnostics identify a transport `ConnectError`, so that result does not establish publisher availability. Real capture/body/image checks remain open. Broader market refresh/coverage, Trade composition, account/worker production persistence, older-PR parity and combined canonical release remain on the requirements ledger. Exact pushed-head checks are required. No merge or deployment without final user approval.
