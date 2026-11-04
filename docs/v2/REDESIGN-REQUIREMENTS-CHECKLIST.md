# Berry Intelligence — requirements and current status

Updated November 4, 2026 (UTC). This is the active checklist. The complete
[previous records](REDESIGN-REQUIREMENTS-CHECKLIST-HISTORY.md#november-4-2026-consolidation--previous-active-records)
remain in history; dated “current” headings there do not supersede this page.
No accepted requirement is deleted or marked complete by this consolidation.

## What is live

Approved [#490](https://github.com/samsonFive/berry-intelligence-os/pull/490),
tested head `10d49757`, is merged and independently verified live at `3ffe5bad`.
Its approval is fulfilled. It retains the redesign, consolidated navigation,
four-crop Landscape, dense image-rich News/Reader, company/variety workflows,
reporting, 27 visual Learn lessons and the visual Help explainer.

Workspaces, company favorites/tiers/lists and saved Explorer views are shared.
Only Personal Digest and layout settings are account-private. All five accounts,
including Chris.H, were preserved; review logins do not consume a real account's
first-login Help behavior. The #490 release retained 65 profiles, 10,540 existing
JSON records, four databases and 1,115 stored research files, with no data or
human-decision changes. These are release-time counts, not a fresh current census.

## Work still open

| Area | Remaining work | Completion evidence |
| --- | --- | --- |
| Daily-use speed / TD-122 | Deep cold catalog pages still take several seconds. Continue full-request and next-click optimization from live #490. | Consistent complete-workflow improvement, current-edit/output parity, browser review, all four checks and fresh production-copy preservation. |
| Catalog coverage / CAT-01, CAT-02 | Work through the 77-subject current/historical source plan, unavailable originals and disclosed portfolio gaps. Add cited identity/trait/rights/region/photo depth without inferring canonical facts. | Accounted original passages, disclosed coverage limits and actual human decisions. The 32-source expected-name audit needs independently supplied human answers. |
| Supplied photos / VAR-01 | Keep 143 candidates /144 associations, 32 unclear cells and two organization holds in review. | Human spelling, identity and role decisions; a spreadsheet association does not prove a breeder/owner role. |
| Map / MAP-02 | Review the 24 country/crop references and 51 original-unit figures across eight countries; retain two UK discrepancy holds. | Human selections, period/unit/crop/geographic scope and linked originals. No automatically trusted figure or growing footprint. |
| Learn / LEARN-01, LEARN-02 | Expand source-linked visual depth and citation/media quality. The one authorized provider acceptance run is complete and remains an editable AI draft. | Preserved user edits/history, appropriate media attribution and human review. No additional paid research request or retry is authorized. |
| Release / REL-01 | Prepare each useful final change for review; preserve data, settings, mounts and rollback. | Current-head checks, native review, fresh preservation and separate explicit merge/deploy approval. |

The live scoped public source corpus is 539 sections /2,073 literal occurrences
and 1,333 derived review keys, with 11 unreadable sections and 143 follow-ups.
These are not 1,333 approved varieties, complete portfolios or worldwide recall.
Canonical name/code/role/rights/trait/region, source authenticity, statement,
photo permission and extraction qualification decisions remain separate gates.

## Prepared work and experiments

- Source-only [#494](https://github.com/samsonFive/berry-intelligence-os/pull/494)
  at `0b60c5fe` passes all four checks /6,325 tests and public-seed desktop/phone
  review. It adds two explicitly historical Well-Pict labels as unreviewed leads,
  without replacing existing records. Fresh production-copy rehearsal and a
  separate release approval remain; its proposed counts are not live counts.
- [#493](https://github.com/samsonFive/berry-intelligence-os/pull/493) is closed
  unmerged. Complete-cost public-seed Linux testing made the separate-preparation
  flow about 27% slower overall, despite faster prepared reads. Its code, tests
  and evidence are retained. No preparation/background job is being deployed.
- The new owned portfolio identity batch at `b76792c0` passes 288 focused checks.
  [Linux diagnostic 41760146303](https://github.com/samsonFive/berry-intelligence-os/actions/runs/41760146303)
  at measurement-only `26c0cd43` is still completing validation. No speed,
  private-production preservation or release acceptance is claimed yet. The
  diagnostic branch must not merge or deploy.
- The server rehearsal remains subject to the existing headroom guard and the
  unanswered specific backup-mirror cleanup request. No backup deletion,
  workaround, relaxed guard or deployment is authorized by internal continuation.

[The cold-load investigation](COLD-CATALOG-INVESTIGATION-2026-11-03.md) retains
deployed gains separately from rejected experiments. Source gaps, human reviews
and performance remain in this mission; this page is not a handoff or completion.

## Later prompts retained

Floating candidate A–Z navigation, original patent/claims links, attributed
variety-photo references with session-only reveal, one-click latest News,
consent-text rejection and a clear publisher route are implemented. Article/body
availability remains source-dependent; unresolved Google wrappers are disclosed.
Original source URLs and literal authored text are preserved.

Help provides the requested visual explanation of site sections, the analyst's
Capture → Connect → Brief workflow and reporting choices. This is delivered in
the app, rather than an unfinished slide deck. Provider availability, reviewed
source status and statement truth remain distinct.

## Original accepted requirements

All 31 IDs, definitions and ordering below are unchanged. Delivery references
may name earlier releases retained in #490; read remaining limits with the
current status above. Earlier intermediate release requests are historical,
not pending approvals.

| ID | Accepted requirement | Delivery evidence / state | Remaining verification or implementation |
| --- | --- | --- | --- |
| CAT-01 | Reconcile sources against the variety catalog so visible named varieties cannot disappear silently | Live #488 at `32eefbd5` retains the source-specific company/name handoffs and the captured-article handoff delivered in #486. Companies now reuse explicit article mentions, including the retained Vicentina repair, alongside portfolio observations. The scoped public source view has 1,333 derived review keys across 539 sections; all 1,315 earlier keys and saved decisions remain. Source additions never create canonical varieties. | Human source/name/role/catalog decisions, 32 unclear photographed cells, two organization labels and the independent 32-source expected-name audit remain. Article handoff release acceptance is complete; it does not prove all article names are detected or globally comprehensive coverage. |
| CAT-02 | Build toward the most comprehensive berry variety resource, with measurable gaps and refreshed provenance | Live scoped public seed: 539 sections / 2,073 literal occurrences / 175 catalog text matches / 1,898 review needs / 1,333 derived keys. The 77-subject source plan has 67 named, seven partial, one unavailable and two identity holds. Eleven unreadable sections and 143 follow-ups remain explicit. #488 adds 44 occurrences of 34 printed names/codes and 34 held attributed photo references, without approving an identity or reuse right. | Current/historical completeness, current rights, reviewed identities/canonical authoring, cited traits/growing regions and photo permissions remain open. Source occurrences and text matches are not distinct approved varieties; named-source progress is not full portfolio coverage. |
| UI-01 | Bright, colorful agricultural Glasshouse identity; first berry icon; subtle glass, stronger contrast and hierarchy | Approved Glasshouse identity and first icon across core, intelligence, authoring, public-library and retained shells (M1–21/34/35); source prose stays literal. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| UI-02 | Immersive full-width workspace, compact top navigation, grouped More menu contained within the viewport | Full-width shared top header, contained grouped More, folded specialist destinations; live/private versus generated-public navigation tested (M20/21/35). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| UI-03 | Dense information with useful headlines, summaries, metadata and collapsed secondary context; plain language | Distinct heading/lead/body/metadata roles, compact cards/tables and secondary disclosures remain. Deployed #442 retains every source row with smaller HTML. #486 delivers the Company Intelligence hierarchy and source-text preparation follow-ups; #487/#488 retain them. Desktop/412px,required checks and fresh preservation pass for those approved releases. | The approved rendering and company/Reader presentation releases are complete. Broader TD-122 cold loading remains open. The later Reader-key experiment #489 is closed unmerged after mixed final timings; neither prototype gains nor passing output tests are a live-speed claim. Source/body completeness and human decisions remain separate. |
| NEWS-01 | Primary news-reader experience, image previews, newest first, multi-berry and country scope, custom dates and 7/30 days/YTD | Shared newest-first publication chronology, multi-berry/country/company/list/mark/date scope; 7/30 days, YTD and custom ranges; M29–31 source preview and compact phone filters verified. Desktop-review correction adds publisher-first shared visuals, labeled crop illustrations on missing/broken images, scoped retained-thumbnail capture and WebP delivery; native 36-story check found two publisher thumbnails. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| NEWS-02 | Trusted versus Unreviewed; useful/not-relevant/save/publisher icons, descriptive accessible names, delayed hover tooltips | Trusted requires reviewed source plus active escalated information; raw lane keeps actual source labels. SVG actions, accessible names and two-second hover descriptions retained. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| NEWS-03 | Right-side overlay that closes back to unchanged grid; original article within Reader and separate publisher option | Shared right-side Article/Brief overlay; publisher option, selected-source capture, independent positions and return-to-origin. M30 real article/image and M31 safe bounded capture verified. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| DIGEST-01 | Personal Digest combines saved stories, reading queue and explicitly subscribed lists | Personal Digest is live through approved platform #433, retained by Tags, #440 and #442. Two fictional accounts verified shared Workspaces and independent Digest/layout state; actual deployments preserved all five accounts, private state and databases. | Private/shared boundaries are delivered and retained. Future releases must preserve user state and real first-login history; broader content coverage remains separate. |
| CO-01 | Companies A–Z; independent favorites, Tier 1/2/3/Untiered, editable custom lists carried across views | A–Z/# directory, independent favorites/four tiers/lists across News/Map/Digest; legacy values retained only where already present. M18/35 tracking and specialist preservation; M37 source-scope parity. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| CO-02 | User-editable logo, website, LinkedIn and social links; People only within company profile with editable/highlighted contacts | Manual URL/upload/reset, collected-logo fallback, website/LinkedIn/social edits and company-only People; per-field/contact history recovery (M5/18/23), cited protected suggestions (M26). M38 native chooser/upload/save/reset succeeded in isolated state. | Release acceptance complete; actual deployed persistence is checked only after approved deployment. |
| VAR-01 | Seed supplied photo variety names with supplied companies, without pretending associations prove roles or identities | 143 photo candidates, 144 associations, 32 unclear cells retained; review UI and original photo provenance preserved (M2/6). | Human spelling/identity/role review remains; 32 unclear cells are retained, not guessed. |
| VAR-02 | Varieties visible on Map with editable and source/news-populable Growing regions; company Operating regions as another layer | Shared editable Growing/Operating region tables and country map layers; article/statement prefill (M23), cited editable proposals/current comparisons and protected review/history (M27). | Release acceptance complete. Subnational notes remain notes; exact polygons are later scope. |
| MAP-01 | Real boundary map, multi-country selection, touch/keyboard interaction, connected news/filter state and region tables with A–Z | Boundary map, multiple selected countries, keyboard/touch controls, A–Z region tables, shared news scope and selected-location snapshots (M4/28/29). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| MAP-02 | Market statistics below Map from best available public sources or explicit research population | Approved #473 deploys the explicit official-source capture support: 24 country/crop references and 51 original-unit figures across eight countries, alongside the existing baseline and research workflow. Source periods, provisional labels and two UK area discrepancies remain visible. Desktop/phone/PDF and isolated route checks pass. | Human figure selections and broader world/crop coverage remain open. The deployment does not apply unreviewed figures or resolve held discrepancies; it adds source files and workflow support. |
| PACK-01 | Competitor registry from supplied image, first group/list, export JSON schema and pipeline rules | First competitor list has 77 supplied-photo subjects with provisional identities/programs/brands retained; versioned JSON schema, stable identities and separate association rows (M2). | Schema/registry acceptance complete; unresolved human identities and optional receiving-system integration remain. |
| PACK-02 | Reviewed-news-source-only or all-news toggle; dates at generation; last generated timestamp for each successful export | Reviewed-source-only/all-news choice, generation-time dates and successful export receipts/last-generated history; individual statement approval is not required for source-reviewed packets (M2). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| PACK-03 | Fresh capture before every export, latest capture results, stable source identity, separate relationship rows, original URLs | Export requires explicit fresh per-subject capture with bounded queries, actual outcomes, duplicate handling and unchanged source URLs; failed capture cannot be mislabeled fresh (M2). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| AUDIT-01 | Audit each section's purpose, working state, duplication/zombie risk and appropriate consolidation; preserve every useful workflow | Section purpose/workflow/duplication audit and eleven-home consolidation are delivered. The retained-route audit found statement-link defects; their read-only destinations and static links are repaired in deployed #468, retained by #473. The bounded joined rehearsal passes 53 route/PDF checks. | Route rendering/access checks do not prove every form or indicate actual user adoption. Human source/catalog decisions and deeper performance work remain separate. |
| REPORT-01 | One Reports & Briefings home; executive view, selected briefs, editable reports, snapshots and news packets distinguished | Reports & Briefings task home unifies Executive view, briefs, editable reports, snapshots and packets without flattening their distinct outputs (M7/13/15/24/28/29). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| REPORT-02 | Rename War Room to Meeting Prep, keep its scope, saved takeaways and handoffs | Meeting Prep replaces War Room presentation; scope, saved takeaways, question/refresh actions, history and human handoffs retained (M7). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| REPORT-03 | Reports and exports must read as designed documents: takeaway first, clear hierarchy, no generated internal ID dumps, readable linked sources | Refined takeaway-first PDF/editor, numbered outlined findings, readable linked Source references and named appendix; literal edits/qualifications retained. #300 four checks green; five PDF pages and phone reviewed. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| LAND-01 | Landscape configurable by what/where to include | Multi-subject/place and included-section selections, source-date ranges, shared analyst-only saved views and Reader/report/brief handoffs (M8), four checks green. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| LAND-02 | Evidence-backed multi-berry Landscape, dense narrative, source/variety and dossier handoffs, comparison, saved views and complete visual exports | Blueberry continuation approved October 12. Tested release398 implements all four crops, All berries, paired comparison, shared company marks/lists, cited traits, revision-checked saved views and complete PDF/HTML/SVG/CSV exports. Browser light/dark/412px checks, saved update/archive/restore/copy, restart preservation and full selected-evidence exports pass. The guide explains the workflow and reporting choices. | Platform release #398 is merged at a2a6b4ad and verified live after the approved continuation. Comprehensive source/catalog coverage and actual human trust decisions stay open under CAT-01/CAT-02. |
| LEARN-01 | Top-level expanded Learn, detailed visual lessons/research first, pictures/diagrams/video links, interactive exploration | All27 existing lessons have interactive teaching explanations, including22 new source-linked explorations and five schematic designs; two verified photos and existing video links retain individual credits/rights. These curriculum additions are now live in approved440; original records and human edits remain. | Wider detailed lessons, attributed photos, diagrams, video/source depth and explicit research remain ongoing enrichment; educational content never approves scientific or competitive-intelligence claims. |
| LEARN-02 | Select/highlight content -> research/add to Learn -> explicit Perplexity deep research -> new learning content | Selected-text/Reader Learn actions, explicit context, durable high-effort research jobs and editable cited drafts are delivered. #473 repairs high-depth requests while retaining legacy medium jobs. #486 also delivers the actual-result presentation repair and deterministic visual-context fallback, retaining saved texts, request settings, run IDs, user edits and history. | The single authorized real high-effort request completed at provider-reported USD0.13679 and remains an editable AI draft. #480 is superseded by fulfilled live #486; no release approval is still needed for that repair. Broader citation,media and lesson-quality review remains. No further paid request is authorized; education never approves a scientific/competitive claim. |
| INT-01 | Plain-language investigation workspaces without changing review decisions | Intelligence home preserves Statements, Signals/candidates, Assessments, Recommendations, Questions, Research and native authoring. M11–17/20/35 verify named references, literal source text and separate gates. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| MON-01 | Consolidate Monitor watches/changes/alerts while retaining distinct intent and action | Monitor consolidates Watches, Alerts and Monitoring plans, retaining marks/list/multi-berry predicates, read/dismiss/pause/resume history and Reader; #283 green and M35 retained shell. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| OPS-01 | Consolidate collection, review and quality surfaces without losing specialist tools | Operations consolidates Collect, Review, Data quality and Coverage & health, retaining specialists. Source authenticity (M34) stays separate from publication/statement approval. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| GUIDE-01 | Visual explainer of site sections, analyst workflow and reporting capabilities with clear purpose/how/working state | The visual explainer is live through approved #474, merge7fa7dd53. It retains twelve site-section cards, four analyst steps, prior reporting choices and shared Workspaces guidance, and now explains company comparisons, retained coverage and accurate saved-comparison JSON/CSV behavior. All four checks pass/6,091 tests; desktop/phone, fresh isolated preservation and live verification pass. | The requested visual explainer and follow-up are delivered. Wider educational/media depth and human source/catalog decisions remain open; no new approval is needed for completed #474. |
| REL-01 | Integrate approved stack, reconcile canonical, run all gates and prepare release/rollback plan for intel.johnnyaceii.com | Approved #490 is independently live at `3ffe5bad`, tested exact head `10d49757`, retaining #488/#487/#486. All four checks pass /6,324 tests; desktop/phone and fresh isolated/live preservation retain five accounts including Chris.H, 65 profiles, 10,540 JSON records, four databases and 1,115 research files, with zero data changes. Fresh backup, rollback, settings, mounts, proxy and active/enabled schedule remain. | These approved releases are complete. #489 and #485 are closed unmerged; #485 documentation is retained in live #490. Cold-load work and human/source/identity/role/rights/photo/Map/independent recall remain here. New code releases need their own tested review and approval; no additional paid Learn run is approved. |
