# Social checkpoint recovery — October 7, 2026

The direct adapter collector previously advanced its in-memory cursor and last-success marker before store ingestion completed. If normalization or the page transaction failed, error reporting could persist that uncommitted cursor and skip the failed page on restart.

The collector now prepares a candidate job, commits records and that checkpoint through the existing single store transaction, then advances its in-memory job. Failure reporting retains the last durable cursor, last success and volume. A first-page processing failure keeps no success marker; failure after a completed page preserves that page's checkpoint. This change makes no source request and does not enable any collector.

Two regression cases exercise the actual Bluesky response/normalization/store path with a deliberately malformed second record, both before any success and after a retained partial page. No record from the invalid page persists; a reconstructed store retries the same cursor, saves the repaired page once and advances only then. The affected pipeline suite passed **62 tests**. These deterministic responses are test data, not evidence of live Bluesky access or a real provider outage drill.

No migration. Rollback restores previous collector code; retain the private SQLite backup. Jobs written by the old implementation after a processing failure may already contain an uncommitted cursor. Do not automatically rewrite those operator records: inspect their run history and replay from the last known complete page within an authorized budget. No production deployment, paid collection or source-rights qualification is implied.
