# Investigation export verification

11 November 2026. Status: targeted backend, authenticated local export, fixture
layout and current-corpus layout checks passed. Export UI and G2 remain pending;
this record is not V1 or production acceptance.

The private routes are `POST /api/investigations/v1/export/preview` and `/pdf`.
Both accept explicit context, section IDs and an explicit synthetic-annex boolean.
The PDF additionally requires the preview's content hash. Changed scope, output
selection or record/source basis returns 409. There is no export store, provider
call, acquisition, canonical edit or source-body hydration.

Selected sections cover readout, complete relationships, portfolio, geography,
typed comparison and complete relevant developments. Development export uses the
same governed model and exact filters, paginated beyond the six-card rail.
Standing/company, source-geography and full-profile comparison bases are declared
separately. Sources retain their actual IDs, dates and review semantics. Missing
observations remain unknown. A sensory lens alone never includes demo values.

Actual checks on the final exporter source:

- All 16 tests in `tests/test_investigation_export.py` passed together in 5.49s.
  The deterministic HTTP test ran outside the Windows sandbox to allow
  TestClient's loopback socketpair; it tests the isolated router's private gate,
  not the complete application-session middleware.
- The fixture contains 13 retained developments. The final row and all 13 exact
  references appear in the PDF; the six-card display limit does not truncate it.
- Tests cover preview conflicts, output-selection conflicts, source-body
  exclusion, unchanged canonical inputs, explicit synthetic isolation/annex,
  strict sections/context, actual-versus-requested geography applicability,
  related-context source labels, and explicit demo-subset/unknown-ID handling.
- A seven-page fixture PDF was generated with the existing ReportLab/Noto
  infrastructure, rendered with bundled Poppler at 96dpi, and every revised page
  was visually inspected. No clipping, overlap, unreadable tables, lost tail
  rows, stranded section heading, or missing synthetic-axis label was observed.
  The fixture's Chinese title rendered visibly through the existing CJK fallback.
- The first layout pass exposed a section heading at a page foot and overly
  prominent scope notes. Pagination and information hierarchy were corrected,
  then the complete revised seven-page set was inspected again.

Local intermediate proof is under
`artifacts/experience-consolidation/pdf-review/fixture-investigation-layout.pdf`
and `revised-page-1.png` through `revised-page-7.png`. The driver is
`render_fixture.py` beside them. They are deterministic layout fixtures, not
current production intelligence or presentation deliverables. No credentials or
account values are present. Poppler logged standard-font/CJK substitution notices;
the inspected fixture glyphs were readable. This is not proof for every language
or every possible real-corpus paragraph length.

The registered protected app also produced an actual authenticated local-corpus
preview/PDF through Chromium: Blueberry, Chile/China/Peru, all six sections, no
synthetic annex. It contained 82 relationship rows, 42 portfolio rows, 10 geographic
rows, 71 developments and 111 exact source references. The empty comparison was
explicit because no cohort was selected. The intermediate 44-page PDF is retained
as `artifacts/experience-consolidation/v1/current-investigation-before-pagination.pdf`.

That real-data review exposed orphaned relationship/source metadata and a nearly
empty continuation of scope limits. Each relationship, source reference, news
card and scope-limit block now stays together when it fits a page. The same
current-corpus payload was regenerated locally as a 42-page PDF, rendered with
Poppler at 72dpi, and all pages inspected in four contact sheets; pages 1, 12,
16, 25, 26 and 42 were also inspected individually. No clipping, table overlap,
stranded section title, orphaned reference metadata or empty continuation page
was observed in this final set. It retains the complete final source reference.

Final current-corpus layout proof is
`artifacts/experience-consolidation/pdf-review/current-investigation-layout.pdf`,
`current-final-page-01.png` through `current-final-page-42.png` and four
`current-final-contact-*.png` sheets. `render_current.py` records its read-only
generation basis. This proof makes no provider request and changes no records.

After integration onto canonical `1ebaab37`, the explicitly provider-disabled
authenticated local server generated the final 42-page output over HTTP as
`artifacts/experience-consolidation/v1/current-investigation.pdf` (127,058 bytes,
111 references). Its content hash is
`51d25a1f2e12b7157fae50de9e10b07f80bd1e459e66a6e5738d072f6771c261`.
Extracted text matches the fully reviewed local rendition except generation time;
the authenticated file's first/last pages were rendered and inspected too. No
synthetic annex or specimen labels appear in that ordinary PDF.

A separate explicit readout-only export with Amber/Fern selected in
`demo_specimens` produced a three-page PDF at
`artifacts/experience-consolidation/v1/current-investigation-with-synthetic-annex.pdf`.
All three pages were rendered at 96dpi and inspected. Its standalone final panel
declares fictitious/synthetic overall liking, the full 1–9 axis and limits. It
contains Amber/Fern and omits Birch; explicit selection did not broaden to all.

An anonymous POST to the actual protected app's preview route reached the login
page (redirected HTML response), exposing no domain JSON. Both actual exports
used memory-only credentials, no runtime/model turn, and the owned local server
was stopped afterward. The isolated route test separately covers its authoring
gate and 409 basis conflicts.

Remaining integration checks: mount the preview/export UI after the visual gate
and run final-head release checks. Synthetic annex selection must remain explicit
in that UI; an unavailable selected specimen refuses the annex rather than
silently broadening it.
