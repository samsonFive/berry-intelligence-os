# Mission 30 — Captured article previews and explicit retries

A real public-article check exposed two reading gaps: a successful Reader capture displayed its image inside the Reader but left News cards imageless, and an unsuccessful cached capture could be returned repeatedly when the user pressed Load available article text. New captures now supply a small exact-source preview projection to News, Personal Digest and Map Explorer. Explicit capture retries failed results; successful results remain reused.

## Delivered behavior

Full publisher text stays in the existing ignored private Reader store. An atomic save also creates a separate three-field image projection: item ID, original requested source URL and safe image URL. Card routes read this bounded metadata rather than original passages. Canonical/source records, classifications, entity associations and analyst summaries are untouched. Existing record images win. Changed source identities, unsafe URLs, corrupt/oversized metadata and overlong URLs do not produce a preview; original captured URLs remain intact.

Read-only/public rendering never reads these private projections. Private News, Digest and Trusted/Unreviewed Map share them. Snapshot exports do not hydrate article text or previews. Merely browsing still makes no capture request. Original text and images are not added to canonical records or public static output.

The explicit capture action retries unsuccessful cached results and reuses successful ones. A new capture records the exact requested URL; a known source-URL change prevents its old body or preview from being shown for a different article. Existing captures without that new field retain their original Reader compatibility. The visible unsuccessful-capture message says text could not be loaded here, allowing a retry, rather than attributing every connection failure to publisher restrictions. Shared script cache version advances.

## Verification

The first focused Reader/Digest/News/Map run had **71 passed / one existing ReportLab warning in 7.82 seconds**. Broader source body/acquisition, original Reader, snapshot and static regression acceptance had **118 passed / one warning in 15.01 seconds**. The final run, including overlong-URL preservation, had **119 passed / one warning in 13.23 seconds**. Canonical records validated; the governing expansion guide remains unchanged.

One explicitly approved public Produce Report article returned HTTP 200, nine readable paragraphs and eight image references using the normal direct capture implementation with network access. Full content remains in an ignored isolated runtime. In the actual browser, all nine paragraphs appeared in the Reader; its image and the matching News and Map card image loaded. Save → Personal Digest → Saved by you retained the same image; the temporary saved mark was then removed and the filtered Digest became empty. Other reading state and canonical data were preserved.

Desktop News/Map/Digest screenshots and a requested 390px News screenshot accompany the review. Phone viewport width was 390, document width 375, with a loaded preview and no horizontal expansion. Temporary viewport settings were reset. This one successful source demonstrates the path, not universal publisher availability or complete article extraction.

## Remaining acceptance

Older successful captures without a separate preview projection remain readable; card browsing does not backfill them by loading bodies. A deliberate offline metadata migration can be evaluated during release preparation. Wider article/provider availability and extraction quality remain explicit, and direct HTTP redirect/response bounds still need release hardening review. Phone filters are functional but occupy much of the first screen; compact filter disclosure is part of final density acceptance. Broader market refresh, canonical/older-PR parity and release/rollback acceptance remain on the ledger. Human source/statement/identity gates stay intact. No merge or deployment before final approval.
