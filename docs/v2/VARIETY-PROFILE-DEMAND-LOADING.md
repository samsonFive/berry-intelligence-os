# Faster variety profiles — October 23, 2026

Opening a variety should show its information without waiting for a catalog-wide
name audit. The secondary **Names needing review** section now checks names when
opened. It keeps the existing matching rules, candidate links and human decisions.
Refresh checks current data; a full-page link works without JavaScript and remains
available after a network error or expired session. An unchecked section does not
claim that there are zero matches. Public profiles and the public API expose none
of this private review material.

The Reader also avoids repeating the access-screen analysis of unchanged article
text. Text changed by cleaning is checked again. Consent screens, source edits,
partial content and Atomic source-text eligibility retain their previous behavior.
The exact-input memoization released in #409 is preserved.

## Evidence

Measurements use isolated copies of production data and the deployed #409 image
(`97f9ac3d`), with normal application startup warm-up, network disabled and an
ordinary fixture login. Two alternating pairs measured Emerald:

| Server response | Baseline runs | Candidate runs |
| --- | --- | --- |
| First profile request after startup | 2.434 / 2.228 s | 1.059 / 1.006 s |
| Second profile request | 2.071 / 1.902 s | 0.649 / 0.679 s |
| Name review, requested separately | Included in profile | 1.474 / 1.616 s |

All other profile context fields are identical. Both actual name findings match
exactly, including the full-page fallback. All 65 profiles, 9,770 protected JSON
files and account rows remain unchanged in the isolated copy. This moves secondary
work off the initial page; it does not eliminate the cost of reviewing names.

Separately, the Reader change preserves every Reader field, classification field
and Atomic source-text result across 3,462 stored sources. The 65-profile and
1,164-candidate projections also match, excluding generated discovery timestamps.
Alternating Reader-only runs improve modestly, from 2.903/3.019 to 2.685/2.663 s.
These are bounded server measurements, not a claim about all routes or devices.

Private receipts are retained under
`inbox/source-body-classification-performance/{demand,source}-candidate.json`;
the corresponding isolated VPS rehearsal directories are
`/opt/berry-platform-releases/variety-demand-prototype-20261023` and
`/opt/berry-platform-releases/source-body-checked-once-prototype-v3-20261023`.
They contain no human source/name decisions and are not a deployment receipt.

## Remaining release work

Automated route and loader checks cover deferred loading, matching/review-state
preservation, public exclusion, refresh, escaping, expired logins, timeout and
retry. Current-head full CI, browser interaction/phone review and final release
approval remain required. Native browser review could not run because the
Computer Use tool could not establish the browser URL; later continuation has
no browser automation tool available. No visual pass is claimed.

TD-122 remains partially addressed: global name scans, large candidate pages,
other route contention and representative device/network performance remain.
Catalog enrichment, source-name review, identity decisions, rights and photo
permissions are separate work and are not approved by a performance release.
