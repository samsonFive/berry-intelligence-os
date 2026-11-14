# Company news review preset

The existing Report Builder has a Company news review entry point at
`/reports/new?report_type=company_news_review`. Paste one company per line or
choose an existing saved company list, set inclusive publication dates, and
optionally select a berry and a public research focus. Starting research is an
explicit action; opening a saved report never initiates discovery.

## Research and review

The preset resolves exact directory names and aliases without silently dropping
unresolved requests. Each company is searched independently. It checks stored
platform publications, pending source records and retained public-source captures
before bounded public discovery. Archive-only mode makes no discovery calls.
Existing discovery providers, source capture, quote holds and output exclusions
remain authoritative. Workspace annotations and synthetic artifacts are not
primary news sources.

When a fresh public capture supplies text for a URL already retained as platform
metadata, the saved source keeps the observed platform record pointer and its
earlier review state separately. The new text remains unreviewed. Those pointers
are observed exact-URL matches, not exhaustive duplicate or same-event inventory,
and capture/intake dates do not become original first-seen dates.

One retained dataset contains the requested cohort, fixed date window,
per-company outcomes, source versions and editable developments. Publication
dates are distinct from event and retrieval dates. Metadata-only, undated,
identity-unresolved and other insufficiently supported results remain visible
leads. Empty results and bounded or failed searches remain explicit; completing
a batch does not establish complete market coverage.

Research checkpoints after every company. Pause stops after the current company;
resume attempts the remaining companies. Interrupted workers require an explicit
resume. An active worker cannot be replaced by another request. Analyst edits,
inclusion decisions and review labels survive later checkpoints. Refresh creates
a new report version and preserves the earlier report.

The native reader has an overview, persistent company navigation, a focused
company view and separate source/coverage details. Editors retain submitted text
on validation errors and reject stale edits. A body-supported verification lead
can be included only after explicit report review and an in-window publication
date. That decision qualifies the report row only; it does not approve the source,
identity or Evidence.

## Downloads and privacy

PDF and Excel downloads use the same saved rows and analyst edits. The workbook
contains Companies, Developments and Scope sheets, with inclusion flags and
clickable source links. PDF includes selected rows with company navigation and
cited sources. Included rows must retain valid source references. Export bounds
produce an explicit error rather than truncating content. Source passages remain
in the private research snapshot and are not duplicated into exports.

These routes inherit private Reports access controls and are excluded from the
public static build. The preset creates no canonical company, Publication, Fact,
Signal or Assessment. Existing human source and claim approval remain separate.

Finished library reports may optionally specify a confined `files.reader` JSON
asset. Valid company-report data uses the native reader; an absent or invalid
optional reader leaves the existing HTML/PDF presentation available. The
registered report artifacts remain unchanged on read.

A private library entry may also register optional `files.coverage` HTML and
`files.coverage_xlsx` attachments. The report and Coverage Assurance link to
these dated reconciliation artifacts. They retain their own qualification and
open checks; registration does not score a benchmark, refresh research or change
source trust. Coverage HTML opens as a full page with external resource requests
and form submission blocked. Inline filtering requires an explicitly registered
`coverage_script_sha256` base64 hash; scripts are blocked by default. Original
report downloads remain separate.

## Coverage repair remains separate

Web additions identify candidates for a coverage audit; they are not automatically
collection misses. A defensible audit first qualifies and groups events, then
checks acquisition, readable capture, company attribution, review and query
visibility separately. An unreviewed captured article is an acquisition hit,
although its absence from a useful product surface can still be a product gap.

Use Source Universe, existing collection/backfill lanes and Coverage Assurance
for reviewed repairs. Preserve first-seen dates and distinguish historical repair
from prospective discovery. Replaying known events establishes repair of those
cases; an independent held-out event set is required to measure normal recall.
Source health, source volume and successful report generation are not recall
measurements. No automatic source onboarding or recurring audit is introduced.
