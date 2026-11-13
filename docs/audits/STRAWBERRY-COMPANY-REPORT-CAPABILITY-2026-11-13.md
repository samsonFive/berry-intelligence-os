# Strawberry company report capability audit

Audited November 13, 2026 against canonical `6f74665b`, including the finished report library merged in PR 574. The primary local checkout is an older feature branch; this audit used an isolated canonical-based checkout.

## Finding and placement

Berry Intelligence OS has the components for research and report authoring, but it cannot yet reproduce the complete 27-company, 55-entry news review as one native workflow. The completed deliverable belongs in **Reports & Briefings → Reports → Research reports**. Use existing saved company lists and research surfaces as inputs, with the finished library as the home for dated, downloadable versions.

The accompanying integration reads private authored artifacts through the same catalog format in persistent runtime storage and adds an optional workbook download. The report files themselves are kept outside this public source repository. It does not create trusted Evidence, approve source claims, activate collection, or add a second report model.

## Current ability

| Capability | Current implementation | Material limit for this report |
|---|---|---|
| Finished reports | `report_library.py`, `/reports/library/{id}`, HTML reader and finished PDF downloads | Canonical PR 574 initially supports HTML/PDF only. This integration adds optional XLSX and a private runtime catalog. Registration is an operator-managed catalog change; there is no in-app upload. |
| Saved company cohorts | `personal_digest.py` company lists and Competitor News Packets | Reuse existing membership rather than another list model. Preserve requested unresolved names outside the canonical selection. |
| Exact news window | Competitor News Packets accepts inclusive from/through dates and up to 100 known subjects | Its capture is Google RSS and queries across berries. It is not the full archive-first, strawberry-specific editorial research process. |
| Report scope | `/reports/new`, company/variety/geography multi-select, berry and archive or archive-plus-web mode | Manual UI exposes rolling days. Exact ISO dates can be interpreted from query text but lack a dedicated start/end control. Unmatched names can be left out. |
| Ask Berry OS | Research Desk scopes a question and hands off to Report Builder | Research Desk truncates companies to five. A 27-company request must not silently use this limit. The explicit Report Builder company list is not subject to that same five-company cap. |
| Archive and external research | Topic retrieval, public source cache, discovery, source passages and event grouping | Generic limits of 40 archive matches and 40 discovery candidates do not guarantee each requested company receives a search and explicit outcome. |
| Saved drafts and editing | Private section-based reports, source snapshots, analyst edits, regeneration and citation validation | There is no company/development/source row model matching the spreadsheet. Topic reports yield attributed source passages, not this complete editorial ledger. |
| PDF generation | Existing server-side ReportLab export for working reports | Preserve this exporter and feed it a reviewed news-report view model. |
| Excel generation | No Report Builder XLSX exporter for this report's rows | Serving the existing workbook is separate from generating future workbooks. Other CSV/JSON exports use different schemas. |
| Workspaces | Source captures, linked research context and cited overviews | Useful as the research workbench. Link to the finished report instead of making another catalog. |
| Upload Report intake | Source attachment intake and publication review | Unsuitable as the home for this synthesis: it would mix report output with original source evidence. |

## Code evidence

- Finished catalog and file allowlist: `app/services/report_library.py`; cards and reader: `app/templates/reports_index.html`, `report_library_detail.html`; private routes: `app/main.py` near `reports_index_page`.
- Report scope and report types: `app/services/report_builder/scope.py`, `packet.py`; `app/templates/report_new.html` and `_report_scope_picker.html`.
- Five-company Research Desk limit: `app/services/research_desk.py` (`MAX_COMPARE_COMPANIES` and scope parsing).
- Archive and discovery limits: `app/services/topic_retrieval.py` and `topic_discovery.py`.
- Section-based drafts and grounded output: `app/services/report_builder/reports_store.py`, `synthesis.py`, `topic_report.py`, `pdf_export.py`.
- Cohort and exact-window primitives: `app/services/personal_digest.py`, `competitor_news_packets.py`, `app/news_packet_routes.py`.
- Workspace research context: `app/living_workspace_routes.py`, `app/services/workspace_landscapes.py`.

## Proposed generator using existing features

1. Add a **Company news review** preset to **Build a report**. Accept an existing company list or an explicit roster, strawberry scope, fixed publication start/end and an as-of date. Keep unresolved requested names visible. Link here from saved lists and relevant Workspace pages.
2. Build an archive-first research packet for each company using current topic retrieval, identities, source roles and event grouping. Then expand through bounded public research for the gaps. News-packet date parsing and cohort mechanics are reusable; its Google-only capture must not be presented as complete research.
3. Record a per-company outcome: searched with qualifying findings, searched without qualifying findings, blocked, undated, identity unresolved, or still incomplete. No company may disappear because another company filled a global top-N limit. Keep provider budgets and run progress explicit.
4. Save structured report entries alongside the existing report draft: company identity, headline, publication date, event timing, factual summary, news angle, material qualification and source references. Preserve stable entry IDs, source snapshots and analyst edits. Cross-company mentions may share one event without losing source attribution.
5. Generate the narrative, PDF and XLSX from that same reviewed entry dataset. Keep company-level coverage separate from individual story readiness. Preserve filings versus grants, plans versus completion, primary claims versus measured results, and original publication versus capture dates.
6. Save a dated finished version in the existing Reports library. Opening or downloading it must not run providers or silently refresh its contents. Refresh creates a new version with a visible as-of date and changes to review.

## Acceptance case

Use the retained strawberry report as the private regression case, rather than a synthetic demo. The workflow must retain all requested names, explicitly resolve or flag unresolved organizations, cover the fixed window and June exception, and preserve every included finding's source and date qualifications. Compare discovery with the retained research file, while allowing evidence-backed corrections rather than hardcoding an expected article count.

Verify that quieter companies still have a recorded search outcome, duplicate press pickups do not become independent confirmation, cross-company events do not inflate event counts, and blocked/metadata-only sources cannot silently support fully verified prose. PDF, HTML and XLSX must use the same saved version and preserve edits. No operation may approve Evidence or alter the publication/claim review gates.

## Deployment distinction

The public host responded successfully at `/healthz`, and `/reports` redirected anonymous requests to login during this audit. PR 574 was initially absent, then its release owner completed promotion at 20:47 UTC: the healthy app/sidecar pair and release ledger agreed, the library stylesheet returned 200, and report routes remained behind login. The finished HTML/PDF library is installed. This subsequent private-catalog and optional-XLSX change has not yet been deployed. Canonical merge, passing local tests and a deployment are separate facts.

Availability in production requires the normal current-head CI and release workflow, preserving the persistent `data/` and `inbox/` runtime. Record the installed commit and verify the authenticated report reader plus byte-identical PDF/XLSX downloads before calling the availability change live.

The GitHub repository is public. A private application route does not make files committed to that repository private. Finished customer research therefore belongs in `INBOX_DIR/finished_reports/`, using the existing allowlist and persistent runtime mount. Only the loader, optional export support, tests and engineering audit belong in the code change.
