# Report reading design follow-up

The report critique remains the acceptance trigger: generated identifiers and provider citation markers must not read like content, and the report needs a visible takeaway, scannable findings and supporting sources.

## Delivered behavior

- The editor leads with the takeaway and populated findings. Undrafted sections, scope, coverage and other supporting disclosures follow them. Every section and editing action remains available.
- Stock Signals and Assessments headings read as Emerging patterns and What it could mean. Custom titles, analyst edits, intentional blanks, proposed/confidence qualifications and underlying classifications stay literal.
- Findings use numbered, outlined cards. The takeaway uses larger text, a stronger green edge and contrasting background. The PDF uses the same hierarchy, a compact scope block and a numbered source appendix.
- Known generated citation references become readable Source numbers; unresolved technical references explicitly say reference unavailable. Ordinary bracketed qualifications and all analyst edits remain unchanged. Original generated prose and IDs remain stored.
- Alphabetical source numbering is deterministic across independently built editor/PDF packets, including Strategic Question sources. Actual publication and capture dates are distinguished in the source appendix. The date cutoff now includes confirmed publication dates of cited sources, never capture-only dates.

## Verification

95 focused report, gap-research and static-safety tests passed; canonical records validated. Meaningful regressions cover literal/blank edits, unchanged report bytes, generated/unknown references, stable ordering, Strategic Question fallback, capture versus publication dates, unsafe URLs, external review markings and findings spanning pages. No paid-provider calls were used.

The existing isolated report was exported without saving or rewriting it. All five final rendered PDF pages were visually inspected; an initial takeaway-background overlap was repaired before the final inspection. Desktop and 390px requested viewport were reviewed; the phone document measured 375px without horizontal overflow. Keyboard Enter opened and closed the retained editor. Temporary viewport override was reset. Artifacts: `report-export-refined.pdf`, `report-export-refined.png`, `report-workspace-refined.png`, `report-items-refined.png`, `report-reading-mobile.png` in `artifacts/design-sprint/`.

The sample is an unfinished design-review report, not a completed intelligence conclusion. No data, trust decision, provider qualification, source approval or user report was changed. Required exact-head GitHub checks and the combined canonical release remain separate gates; no merge or deployment.

## Debt check

The existing saved sample retains an analyst-edited source list as well as the generated linked appendix; it is preserved rather than silently deleting authored content. Broader report scope/source eligibility and final editorial/combined-release acceptance remain in the requirements checklist. Location suggestions in progress are excluded from this focused report commit. No domain schema, source acquisition, maturity count or canonical guide change.

Parent draft #299 head `044b4b9853669034c2146935ce7e40413df9e72a` passed all four required checks, run `37222193634`: 3,689 passed / 11 skipped / two warnings in 360.37 seconds. This verifies company suggestions, not the combined release.
