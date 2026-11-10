# Prospective News coverage pilot

Set `BIOS_NEWS_PROSPECTIVE_START_UTC` in the runtime environment of the existing scheduled News refresh to an explicit UTC timestamp, such as `2026-11-12T00:00:00Z`. It opens a fixed 14-day window, inclusive at the start and exclusive at the end. An unset value leaves the pilot off. The refresh records only observations made during the configured window. Starting after the configured time leaves the earlier interval unmeasured.

The app service in `deploy/docker-compose.yml` passes through the value from the deployment environment. Choose the start only after the candidate is released and the independent source sampling has been set up.

The pilot uses the normal keyless scheduled refresh. UI-triggered refreshes and known-URL replays do not produce pilot receipts. The private SQLite ledger is under `inbox/operations/news_prospective/<window>/observations.sqlite3`. `runs` records refresh and projection status plus route outcomes. `observations` stores the earliest timestamp per normalized URL, provider, route, and stage. It contains no title, snippet, body, query text, or operator data.

- `raw` means the discovery route returned the URL.
- `qualified` means it passed the collector's metadata checks before date filtering and deduplication.
- `news_eligible` means the saved record matched the default unreviewed News projection across all pages after the refresh. This does not measure when an individual reader opened the feed.

Join the ledger to an independently collected, frozen reference cohort. An observation is not automatically a reference event. `independent_reference` stays false in collector receipts, and `exact_url_candidate` distinguishes direct article-shaped URLs from wrappers and homepages. A stored publication date is day precision from the discovery provider. Use an independently verified public-visibility timestamp when scoring 24-hour latency, and report dates with unknown times separately. Report original URL and event recall separately, and separate projection failures from completed empty checks.
