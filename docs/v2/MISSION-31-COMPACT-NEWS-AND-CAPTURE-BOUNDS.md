# Mission 31 — Compact News filters and bounded article capture

Phone News filters now start folded into a readable summary of the actual selection. The native disclosure keeps every search, company, favorite, tier, watchlist, berry, country and date control available. Desktop starts expanded; without JavaScript the controls remain visible. Company tiers use the shared Tier 1 / Tier 2 / Tier 3 / Untiered names, with existing legacy values retained. Snapshot scope labels use the same vocabulary.

Applying filters no longer replaces an explicitly selected timezone with the browser timezone. Reversed custom dates produce a native correction message before navigation. The change does not alter matching records, newest-publication ordering or saved company/list state.

## Article capture

Explicit article capture and source/publisher preview requests preflight every redirect before requesting its destination, stop after five redirects and stream bounded content rather than downloading a whole response before slicing it. The existing article/image byte budgets and four-second capture budget remain. A response cut short by the byte limit cannot claim a full capture. Restricted or unsuccessful HTTP responses are not parsed as article text, including PDFs. Malformed ports, credentials and noncanonical numeric hosts fail safely. Public relative redirects remain supported and the exact requested article identity stays separate from the final URL.

This closes the identified redirect and whole-response download gaps. It does not establish DNS/peer pinning, universal publisher accessibility or perfect extraction. Browsing still never starts capture; source/statement review, canonical records, private cache isolation and public-static exclusions remain unchanged.

## Verification

The first combined run exposed one legacy tier-label expectation: 166 passed and one failed. The labels were corrected to the current company vocabulary. The follow-up had 63 passed, and broader acceptance then had 173 passed / one existing ReportLab warning in 35.14 seconds. The final run, including restricted/error HTML and PDF responses, had **180 passed / one existing warning in 30.84 seconds**. Exact pushed-head CI remains required.

In the actual browser, desktop filters were expanded. At 390px, News started with filters collapsed, document width was 375px and the real article preview loaded. Enter expanded the disclosure; reversed dates were rejected with an understandable message. Correcting the date and applying filters retained `tz=UTC`, the selected company/berry/date range and one matching source. The temporary viewport was reset. Desktop and phone proof images are in `artifacts/design-sprint/compact-news-filters-*.png`.

A separate explicit capture of an existing public Produce Report article succeeded under the new limits: HTTP 200, nine readable paragraphs and eight image references. Original content stays in ignored isolated Reader state. This is one source-path check, not a claim of complete publisher coverage. Canonical records validated and the governing expansion guide remains unchanged.

## Remaining release work

App-assisted market-statistics refresh/review population, retained-route and older-PR functional parity, final combined acceptance and the release/backup/rollback review packet remain open. Older successful captures without preview metadata still require an explicit offline migration decision; cards do not backfill by reading full bodies. No merge or deployment before the final human review.
