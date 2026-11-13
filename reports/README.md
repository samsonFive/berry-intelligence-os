# Research reports

Finished research reports are shareable documents for reviewing a variety's identity, characteristics, commercial context, and unanswered questions. The Regina profile is the reference example. The standard is descriptive; recommendations, decision gates, and review deadlines belong only in reports explicitly commissioned for that purpose.

## Standard variety profile

Start with [the variety and commercial profile template](templates/variety-commercial-profile.md). Use four pages when the available material supports that length; add pages when useful detail would otherwise be lost.

1. **Findings first:** a short opening that explains what the variety is, the most relevant known details, and any identity limitation that materially affects interpretation. Follow with a compact evidence-position table and an accurately captioned supporting image when available.
2. **Identity and context:** breeding background, company roles, ownership and rights, agronomic characteristics, and fruit/postharvest information. Distinguish a commercial name from an authenticated cultivar denomination. Keep similarly named crops separate.
3. **Comparisons and open questions:** show relevant varieties side by side using comparable, geographically scoped information. Describe missing information and records that could answer the questions; do not invent performance rankings or decision thresholds.
4. **Research links:** individually clickable citations and source titles, with dates, relevant pages, and a short explanation of what each source contributes.

Use concise headings, bullets, and tables. Expand abbreviations on first use. Keep company roles, acquisition announcements, and completion dates precise. Promotional claims remain attributed claims; missing information is not evidence of absence. Use an industry-neutral viewpoint without assuming a particular client.

Keep retrieval detail, methodology, confidence definitions, excluded identity matches, and repository integration in a separate `research-notes/` document. Qualifications that change how a finding should be understood stay next to that finding. Supporting images must identify their source and whether they depict the subject variety, a comparator, or unspecified material; do not imply that a comparator's patent or retail image depicts the subject.

## Authoring and export

Keep the editable source in `reports/`. Place local images under `reports/assets/`. The renderer embeds those images and the shared stylesheet into the HTML, so the finished HTML needs no network access to display. External citations, image-source links, and video links remain clickable in HTML and PDF.

```powershell
python scripts/render_variety_report.py reports/regina-blackberry-intelligence.md --html reports/regina-blackberry-intelligence.html --pdf reports/downloads/regina-blackberry-variety-profile.pdf
```

HTML generation uses Python's standard library. PDF generation uses the locally installed Playwright and Chromium; export does not install dependencies or retrieve external content. It runs during authoring, not when someone downloads a report.

The supported Markdown subset is headings, paragraphs, unordered and numbered lists, tables, bold/italic text, links, local images, reference definitions such as `[R01]: https://...`, and explicit `<!-- page -->` breaks. Citation groups such as `[1,2,3][R01]` produce three separate source links. Keep table cells and list items on a single source line. Reference definitions require HTTP or HTTPS URLs; local images must remain within the source document's directory tree.

Before adding a finished report to the Reports library:

- Check material statements against their sources and keep the full research notes.
- Render and visually inspect every PDF page for readability, clipped content, and table breaks.
- Confirm the page count and that source, image, and video links survive PDF export.
- Keep the finished PDF under `reports/downloads/` and add only the intended HTML/PDF pair to the library catalog. Research notes and other working files are not automatically served.

The finished-report library is separate from generated Report Builder drafts. Adding a report does not create trusted Evidence, variety records, assessments, or recommendations, and does not deploy the application.

## Library and direct downloads

In Berry OS, use **Reports & Briefings → Reports → Research reports**. Each report has an in-app reader and a **Download PDF** button. The download serves the finished artifact; it does not regenerate the report or contact a research provider.

The allowlist in `reports/library.json` contains `reports` entries with `id`, `title`, `subtitle`, `summary`, `published_date` (`YYYY-MM-DD`), `berry_id`, `page_count`, and `files` (`html` and `pdf` paths relative to `reports/`). IDs use lowercase letters, numbers, and single separating hyphens. Both files must exist within this directory tree for the report to appear. Missing or invalid entries are not exposed.

The library inherits the existing private Reports access controls and is excluded from the public static build. The application package includes the catalog, finished HTML, and `downloads/` PDFs; supporting notes and authoring assets are not served by these routes.
