# Mission 3 — Core News and the shared Reader

October 1, 2026. Branch `feature/news-reader-consolidation`, stacked on Mission 2. Implemented review checkpoint, not merged or deployed.

## Analyst job and behavior

**Scan → scope → read → save → return.** `/today` and plain `/news` now share the approved dense Glasshouse News home. Thirty-six metadata cards per page retain available preview images, source/publication date, headline, summary, company/region context and icon actions. Newest publication always sorts first, regardless of priority, capture time or tier. Publication timestamps are normalized before sorting; undated reporting has a separate view. Quick dates are past 7 days, past 30 days and year to date; custom bounds are inclusive. The default is all dated reporting, never a silently widened empty date range. Browser timezone is submitted with filters; a missing timezone uses explicitly disclosed UTC.

Berry and country selections are multiple; countries use the existing `IntelligenceQuery` vocabulary and stored containment relationships. Search, company/subject, existing custom list and assigned tier intersect the selected scope. An absent personal company tier is shown as Untiered in this selector, not automatically assigned the old feed's implicit Tier 2. Existing explicit tiers, watch and muted values remain intact. Company favorite editing/shared migration remains in the next Companies mission; no unsupported favorite filter is advertised here.

**Trusted** contains news sources supporting active canonical Facts and independently passing source-review classification. **Unreviewed** is the raw news lane, including already-reviewed sources with a distinct Source reviewed label. Source publication review does not verify every claim. Archived/withdrawn facts, cached status strings, automatic discovery, thumbs and saves cannot confer trust. The existing deterministic berry-news qualification screens unrelated generic reporting; it creates no review or relevance decisions.

The same `#v2ReaderOffcanvas` used by Digest overlays the right side without reallocating grid columns. Article shows actual available publisher paragraphs; missing/partial/access-wall content is disclosed with an explicit load action and separate publisher link. Brief emphasizes the summary, labels escalated facts separately, preserves source statements and keeps source context collapsed. Feedback/save/newspaper icons use the shared two-second hover descriptions and immediate keyboard focus descriptions. Article/Brief reading locations, completion, browser history, focus return and wider reading reuse Mission 1's state and scripts. No People directory or permanent sidebar is added to News.

## Acquisition and privacy

GET News, reader and refresh-status routes do not collect. Opening an old `?item=` link opens the reader without automatically capturing its body or marking reading complete. The grid does not read the full capture store or hydrate article/transcript bodies for cards. Reviewed published records remain authoritative over cache records; no private intelligence is copied into public static output.

Refresh news is an explicit authoring-only POST using the existing bounded Google/specialist/official public discovery lanes. Paid Perplexity/Exa/APITube lanes and lead body enrichment are disabled. It runs under the existing shared collection lease, writes private cache and standardized operational health, and reports partial/error outcomes. The UI offers an updated-feed link on completion rather than resetting an open reader. Cross-site mutations are rejected. Worker-local queue serialization prevents duplicate refresh starts in one worker; durable distributed jobs and multi-user state isolation remain open platform debt. Browser tab closure does not cancel an accepted collection. Discovery success is not exhaustive recall.

Article images are displayed when existing source metadata supplies them. Newly discovered RSS snippets can lack images or useful excerpts; this mission does not fabricate media or collect all full articles on page load. Illustrative images remain explicitly labeled in the isolated review runtime only.

## Scope bridges and compatibility

News's map link carries multiple berries, countries and review lane through `IntelligenceQuery`. On return, News date/company/list/tier/search/timezone filters are restored; changed map geography/berry/review scope wins. Only validated local News return paths and known filter keys are carried. The existing map's raw view now reads retained daily and packet captures as well as published source records, with canonical records authoritative. Its trusted snapshots still exclude raw captures. Date/company/list/tier parity, the full-width region table, operating/growing region storage and public market statistics remain the next Map mission; the link and collapsed explanation disclose this boundary.

The preceding News workspace remains `/today?view=legacy`; the daily briefing remains `?view=briefing`. The old edition stays `/news?view=archive`, and existing `/news?date=...` bookmarks keep their old edition behavior. `/saved` continues its Digest compatibility redirect. Publication review, Reading Queue, statement confirmation, Learn, packets and specialist tools remain reachable in the shared More navigation. No legacy collection/confirmation action is retired by changing the main entry point.

## Validation

Deterministic checks cover publication ordering, timezone boundaries, all date ranges and empty ranges, active-fact/source-review independence, compound berry/country/list/company/tier scope, unknown-country empty coverage, pagination, metadata-only cards, feedback/save continuity, pure GETs and explicit public-only collection/failure health. Existing feed-first route regressions now explicitly exercise the retained legacy workspace; the default home has separate new integration tests. Records validation and static-public safety remain required. Browser QA covers the image grid, reader, mode/width controls, focus/history return, scoped review switching and mobile overflow. Final results are reported with the review PR.

## Next missions

1. Map Explorer: production region-table layout, persistent sourced company/variety regions and public market statistics, scope parity without date-filtering long-lived regions or annual statistics.
2. Companies/Varieties: shared favorites/tiers/list editing, A–Z directory, editable logos/links/People tabs and photo candidate review continuity.
3. Consolidated Landscape, Learn, Meeting Prep, Reports, Monitor and Operations: preserve audited workflows/URLs, implement accepted visual learning/research, then close the visual workflow guide against actual behavior.
