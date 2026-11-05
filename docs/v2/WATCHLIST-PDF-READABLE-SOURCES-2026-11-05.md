# Readable Watchlist PDF source references

The live export repeated record IDs beside already readable source titles and
printed the registry's machine key on the cover. The generated export clock
also included full ISO precision. These labels made the document harder to scan.

This presentation draft keeps the existing export projection and source data.
The cover gives the selected organization and captured-record counts, formats
the generated clock in readable UTC, and labels the known registry key as
"Competitor registry spreadsheet." Other operator-provided source labels remain
literal. Original source dates keep their own wording and precision.

Known citations use their captured titles. Unknown references retain their
literal identifiers, preserving a way to investigate missing metadata. The
source register keeps publisher, type, dates and original clickable URLs; a
syndicated source with a different headline also shows that original headline.
Relationship, status and confidence labels use readable words in the PDF.
Stored IDs, CSV/API data, analyst notes and source titles remain unchanged.
No trust state, identity, company role, source association or score is inferred.

## Verification

All 32 affected Watchlist checks pass with zero attempted external connections.
Coverage includes all four saved berry scopes and their PDFs, empty filtered
cohorts, explicit company filters, literal notes/titles, source links, unknown
references, older projections without a record-count field and render-model
immutability. The only new required behavior is in the PDF presentation.

A three-page fictional fixture was rendered directly from transient PDF bytes
to PNG. All three pages were visually inspected for readable
hierarchy, line wrapping, complete links and unclipped text. This fixture is
internal QA, with invented company/source labels; it is not market intelligence
or private production acceptance. Review records remain under ignored
`inbox/pdf-readability-20261105/`.

The requirements summary also records verified live #516 and #517 and the
fulfilled exact 13-file cleanup. All 31 original accepted
requirement definitions and ordering remain identical; the complete previous
summary is retained in checklist history.

This draft is separate from #517. Current-head CI and its own release review
remain required before merging or deploying it.
