# Share company tracking with Global Watchlist

Global Watchlist previously had its own monitoring groups and imported berry
tiers, but could not use the shared company favorites, assigned tiers or custom
lists. An analyst can now filter its table, selected profiles, comparison,
captured news and PDF by those same shared marks. Profiles reuse the existing
company tracking controls and protected write endpoints; edits return to the
same Watchlist scope. Company lists are created and renamed in Companies.

Assigned company tiers remain independent of imported berry-specific tiers.
Existing monitoring groups, follows, memberships, import provenance, history and
legacy tier values remain intact. Nothing automatically assigns a tier or
combines stores. A company excluded by the new filters is named explicitly;
clearing those filters restores its selection. An empty explicit selection
never falls back to unrelated companies, news, notes or PDF rows.

Only shared mark/list fields enter the Watchlist model. Personal Digest reading
state and subscriptions remain account-scoped. The existing shared-state save
path preserves other accounts. There is no schema migration, collection change,
provider request, canonical identity change or human review action.

The layout brings the working table closer to the top: smaller heading and
inline counts, a folded filter panel with visible active scope, secondary links
and evidence guidance behind disclosures, and a comparison action beside the
table heading on desktop. All filters, original column identities and shared
resize/reorder/hide/search/sort/CSV/layout controls remain available. At the
reviewed desktop viewport the table begins around 496px, compared with 838px in
the initial iteration. Phone profiles keep editing controls within the page;
the spreadsheet scrolls horizontally inside its own region.

## Validation

- 52 affected checks pass for Watchlist, company tracking and Help. New coverage
  verifies directory parity, combined/invalid filters, empty/partial explicit
  selections, PDF scope, input immutability, safe returns, origin protection,
  legacy tier retention and shared edits across two accounts with private Digest
  state retained. The runner records zero attempted external connections.
- Native desktop/390px review uses an authenticated disposable public-seed copy.
  Favorite, assigned tier, list creation/membership, combined filters and explicit
  exclusion/recovery are exercised. Native input confirmed the final recovery;
  earlier automation/navigation delays remain in the ignored evidence. No live
  data is used or changed. Table headers/column IDs are retained.
- The three-page fictional PDF is rendered with Poppler and visually inspected.
  It includes readable list/tier scope and company tracking alongside the
  separate imported classification. Source URLs, review labels and the literal
  user note remain intact. Rendering leaves its complete model unchanged.
- This draft follows Help #510 and frozen integration #506. Current-head CI and
  fresh production-copy release acceptance are separate gates. It is not covered
  by the pending #506 release approval and is not deployed.

Evidence: ignored `inbox/watchlist-shared-tracking-20261104/`; PDF rendering under
`tmp/pdfs/watchlist-shared-tracking/`. Cold catalog performance, source depth and
human-owned name/photo decisions remain open in the mission checklist.
