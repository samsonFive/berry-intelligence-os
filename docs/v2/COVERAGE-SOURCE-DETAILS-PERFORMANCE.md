# Lighter source inventories with every source still available

## Released October 30, 2026

Explicitly approved #442 head `ab6256c7` merged as `3b0b4acc` with an identical
tree and deployed at 18:47 UTC. All four required checks passed, including
5,477 tests. A fresh release-time backup, bounded isolated preservation check
and live post-switch check preserved five accounts, 65 profiles, 9,854 existing
JSON records, 3,228 data files and four databases. Settings and persistent mounts
remain; the prior image and rollback compose are retained. No data addition or
human review decision was included. The live browser loaded Hortifrut's full
21-name disclosure, original-source access and review links.

On the same isolated production-data copy, large-view HTML fell from 1,758,960
to 402,847 bytes (77.10% smaller). Four repeat observations per image gave warm
medians of 3.4102 and 2.71775 seconds (20.31% faster). All rendered source bodies
matched. Raw read-model hashes differ because 72 unpersisted corpus discoveries
and 775 unpersisted portfolio discoveries generate their `discovered_at` clocks
when projected, including between unchanged-image runs. The diagnostic verified
every differing field is exactly that generated timestamp, within its own run;
all other model fields and persisted records match. No clock behavior was
changed for this diagnostic. These bounded measurements are not a universal
route-speed or complete-source-coverage claim. TD-122 remains open.

The implementation and earlier review evidence below retain their original
dated scope; references to a future release are superseded by this delivery.

## Implementation and original review

The full coverage page sent about 1.76 MB, mostly source details inside closed
rows. Large inventories now keep all source titles, warnings, counts and dates
in the dense table and fetch a source's complete detail when its row opens.
Views with at most 40 sources retain inline details to avoid an unnecessary
round trip; the measured ten-source company view remains about 103 KB.

This follows the tested literal-name/company lookup work in draft #441. It does
not change deployed #440, add catalog records or approve source/name/photo/IP
decisions. Existing direct source anchors remain. A bookmarked source opens its
row and loads the detail; other disclosures keep their normal default state.

## Measured payload and content preservation

The comparison loads original templates from exact #441 head
`fce4617e6a53d89f7855335d4d45f38950240195`, renders them over the same current
public-seed read model, and compares each source body with the extracted body
template. All 532 body renders match byte-for-byte after removing the loading
marker: 522 source sections in the large inventory and ten in the company view.
The original names, identity warnings, accounting, source limits, companies,
original URLs and review links remain attached. No review action is added.

| Public-seed view | Source rows | Original HTML | New HTML |
| --- | ---: | ---: | ---: |
| Rutgers profile filter; all portfolio sources | 522 | 1,755,702 bytes | 399,758 bytes |
| Perfection Fresh company scope | 10 | 102,739 bytes | 103,120 bytes |

The large response is 77.23% smaller. Its rows are not paginated or removed.
These are HTML-transfer measurements, not a production latency benchmark.
Current Windows TestClient observations were 4.792 and 2.895 seconds respectively;
there is no paired route-speedup claim. Discovery, reconciliation and copying
still run on the server, and exceptionally large smaller inventories can still
send large inline bodies. TD-122 remains open.

## Reading, failure and privacy behavior

An opening row announces loading without changing the filter scope. Once loaded,
it retains its detail until page reload and can be closed/reopened without
another request. A failed load offers both Try again and a normal source-check
page. The normal page works without the disclosure script and returns to the
same coverage filters and source anchor. Unreadable sources explicitly say that
names have not been checked; they are not reported as zero varieties.

The source endpoint is read-only and requires the existing authenticated analyst
workspace. It reruns current source/review projection rather than serving a
stored HTML snapshot. Full pages and fragments are private/no-store; fragments
have a dedicated response marker. The browser refuses redirects, unexpected
destinations, login pages, missing fragments and cross-origin requests. Error
paths retain the normal link and reset the busy state. The trusted public build
does not render private source links, fragments or the disclosure script.

## Review evidence and remaining work

Initial affected checks pass 136 tests with one existing warning. Native desktop
and 412px review verifies the dense table, Hortifrut's complete named list,
bookmarked Baridi disclosure, prominent unresolved-code warnings, and a real
missing-source response followed by successful retry. The error was introduced
only in the disposable public-seed copy; its original source file was restored
byte-for-byte. No production source or review state was changed. The phone
document is 397px wide with a 397px scroll width, and the shared header remains
clear of the source row. The standalone fallback retains source context and
separate name/code/status typography. Browser review found and fixed the latter
when the body moved outside the table. Final affected and exact-head CI receipts
are retained with the draft, including the stylesheet cache-version update.

Only fictional-account login and reading were used. All provider keys were
blank; no acquisition, publication, identity, reuse or claim decision ran.
Temporary browser tabs were closed and viewport overrides reset. The immutable
guide, all 31 accepted definitions/order, existing data and schema, CPVO,
footprints, Trade/Weather and the deployed platform remain unchanged. A later
release still requires current-head checks, preservation proof, backup/rollback
and actual approval. Broader coverage and human review queues remain open.
