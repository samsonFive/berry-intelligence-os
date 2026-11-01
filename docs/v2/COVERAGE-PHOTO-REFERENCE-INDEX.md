# Coverage photo reference index — November 1, 2026

Coverage was still comparing every source photo with each catalog profile, even
after validation and discrepancy notes were shared. The request-local photo
index now narrows those comparisons by the existing literal identity strings
and berry type. The original matcher still decides every returned reference.
Full-catalog ambiguity, source code/name conflicts, explicit holds, attribution,
reuse terms and saved user overrides remain authoritative.

The lookup uses the existing identity-field reader, including aliases, trade
names, denominations, breeder codes and registration text. It preserves original
source/photo order and duplicate-image replacement behavior. It validates the
same original photo population, including invalid unrelated photos, rather than
silently dropping bad metadata. Gallery and identity-review populations remain
separate because held references and optional previews have different existing
validation paths. No index is retained between requests or edits. The default
single-profile and candidate paths are unchanged.

## Actual complete-page comparison

The private comparison loads the original photo, review and profile-field
implementations from deployed canonical `f76080d0`, wires them together and
alternates them with this candidate on an isolated public-seed runtime. Both
variants use the same fictional account, disabled providers and fixed synthetic
candidate-builder clock. No production account or data is used.

| View | Baseline warm median | Indexed warm median |
| --- | ---: | ---: |
| Coverage, Rutgers profile search | 3.5272s | 3.2352s |
| Coverage, blueberry + Hortifrut | 4.8195s | 3.5249s |
| Planasa source detail, unchanged control | 2.0215s | 2.0841s |
| Blue Maldiva profile, unchanged control | 0.8209s | 0.8719s |

Each view alternates eight requests and discards each variant's first timing.
All 32 full HTML responses match their counterpart byte for byte. The two
complete typed Coverage models also match, including their 10,472,594-byte and
5,008,020-byte serialized contents. No source table, field or summary is removed.
The small control fluctuations and different gains across affected scopes mean
these local timings cannot establish production-wide speed or resolve TD-122.

## Verification and release boundaries

All 59 focused photo/profile-field checks pass. They compare every real catalog
profile's photos and review links with the unchanged unindexed path, retain
source records and saved hiding, and test every existing identity field, crop
separation, duplicate ordering, short-name rejection, global ambiguous aliases,
source code conflicts, held/invalid metadata and next-request source edits.
One prefilter regression also verifies that remaining eligible references still
reach the authoritative matcher. The broader editor, preview, review-routing and
platform integration suite passes 95 checks with one existing ReportLab warning.
Record validation and the 1,797-page static build pass with no private draft leak.

Native desktop and 412px review retains the photo-gap filter and the held Rutgers
photo. The existing review link opens both NJ09-2-1 and the uncoded photo source.
At phone width, the document is 397px wide with no page overflow; the 720px table
scrolls within its 349px container. The inventory loads no photos. Only a
fictional account is used and no human review decision is submitted.

Private receipts are under ignored `inbox/coverage-next-performance-20261031/`.
A separate custom-copy experiment was rejected after mixed complete-page
timings; this draft does not include it. Current-head CI and fresh isolated live-data preservation and actual scoped release approval remain
required. No canonical merge or production change is implied by these results.
Prepared drafts #448, #449 and #450 are excluded. The 31 accepted definitions
and their order, immutable expansion guide and human review gates are preserved.
