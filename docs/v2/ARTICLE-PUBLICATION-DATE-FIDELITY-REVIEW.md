# Keep article dates separate from page updates and latest-news dates

October 7, 2026. Follow-up to the variety source-coverage investigation; stacked
on draft #323. No canonical data or review decisions change.

## Observed defect and repair

A bounded current-source recovery retrieved the Produce Report BluGenix article
but assigned October 7, 2026 as publication date. Native inspection showed the
article's own date block says June 8, 2026; October 7 belongs to latest-news
sidebar items. The existing page-wide date heuristic could then override an
earlier discovery date, making old news appear new in filters and packets.

The shared article-acquisition service now accepts only complete, valid dates
from explicit publication metadata, current-article structured data, or marked
article publication-date blocks. It ignores modification dates, arbitrary body
dates, footer years and unrelated articles. Conflicting dates within a tier stay
unknown. When the page has no supported publication-date evidence, the existing
discovery-feed fallback stays intact. It does not substitute capture time.

The artifact retains `publisher_metadata`, `publisher_display_date` or `unknown`
as its date basis. Acquisition version is now `article-acquisition-v2`; prior
stored artifacts remain untouched. No new acquisition pipeline, provider,
qualification, identity/claim writer or domain schema is introduced.

## Actual bounded recovery

The original four-source run used the existing `scripts/reacquire_sources.py`
against a task-private inbox. Produce Report and SEKOYA yielded pending current
copies; the university trial page yielded no readable body and HortWeek returned
403. These remain availability outcomes, not four successful captures. The
original copies, errors and audit are retained privately.

The corrected two-source run audited code commit
`e09bfd1c3df102e1b19d2669dddec4108a8b4f6a`:

| Source | Observed result | Publication date / basis | Review |
| --- | --- | --- | --- |
| Produce Report BluGenix | Six paragraphs, 338 words | 2026-06-08 / publisher display date | Pending |
| SEKOYA story page | 33 paragraphs, 339 words | Not established / unknown | Pending |

Both still classify as current content changed relative to the older saved
record; a correct date does not affirm historical fidelity. The run records
matching trusted-data hashes before/after, zero new extraction-ready IDs and
zero analyst decisions. Raw bodies, audit details and source copies remain in
ignored task-private inboxes. No body was sent to an AI endpoint. No blocked
source was bypassed. This pilot is not an independently reviewed recall score
or proof of full-text coverage across the web.

## Validation and remaining work

93 acquisition, refresh, outcome, reacquisition and fidelity checks passed,
with 73 existing dependency warnings in 8.32 seconds. Regression cases cover
sidebar contamination, current-article structured-data binding, changed-date
metadata, malformed/ambiguous dates, actual CMS markup and end-to-end draft
date reconciliation without trusted writes. CI and native proof are recorded
in the draft description before calling the slice fully tested.

Native review of the fresh private queue confirmed two pending copies. The
BluGenix comparison shows June 8 on both the original shell and recovered copy,
with the false date-difference warning gone; content/identity warnings remain.
No decision controls were used. Screenshot proof stays in ignored
`inbox/article-date-provenance/`. Preview is localhost-only on port 18451 with
explicit task-private data/inbox paths and source polling disabled.

Parent #323 exact head `0c94f676eb275a920fe1c9bfbf87de70ff7c691a` passed all four
checks, run `37622240000`: 4,033 passed / 11 skipped / two warnings / 461.13
seconds. Its catalog/portfolio/source-content population counts are unchanged.

CAT-01/CAT-02/TD-116 remain open. Human authenticity review, bounded further
capture, table/multilingual/PDF coverage, historical and remaining portfolios,
independent name recall, real canonical identity additions and sourced traits,
rights, images and growing regions remain necessary. Unsupported localized
display dates remain unknown unless explicit machine-readable publication
metadata is available. Existing discovery freshness/sanity rules are unchanged.
No merge/deployment, extraction qualification or other-berry Landscape rollout.
