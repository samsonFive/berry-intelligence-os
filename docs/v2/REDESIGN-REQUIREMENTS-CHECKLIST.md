# Berry Intelligence — requirements and current status

## Evaluation scope follow-up — November 4

The same CO-01 cross-view requirement also applies to Competitive Evaluation.
Its new shared company filters now scope the live research views and complete
exports. Captured comparisons keep their resolved cohort after list changes or
archival, including record CSV; empty scope cannot fall back to unrelated data.
The existing archived research handoff uses resolved IDs and keeps legacy IDs.
See [the scoped implementation and validation](EVALUATION-SHARED-COMPANY-SCOPE-2026-11-04.md).
This remains a separate draft on #512 until current-head and fresh release gates
pass. #511 and #512 have all four CI checks green (6,741 passed / 11 skipped);
neither is deployed. All original definitions below are unchanged.

## Shared tracking follow-up — November 4

The independent Watchlist follow-up addresses the remaining CO-01/UI-03 gap:
shared company favorites, assigned tiers and custom lists now filter its table,
profiles, comparisons, captured news and PDF; profile edits reuse Companies'
existing controls and protected writes. Imported berry tiers and monitoring
groups remain separate. Empty explicit selections cannot fall back to unrelated
news. The layout is denser, with active scope visible while controls are folded.
52 affected checks and native desktop/390px/PDF review pass; CI and fresh release
acceptance remain required. See
[the scoped implementation and evidence](WATCHLIST-SHARED-COMPANY-TRACKING-2026-11-04.md).
No release approval is inferred from implementation or browser review. The
pending exact #506 release remains unchanged. All original definitions below
are retained verbatim, along with their dated evidence.

## Global Watchlist reconciliation — November 4

Global Watchlist #505 is now merged at `ae22ea07` and its healthy runtime uses image `20c8a5a0`. At the last observation the release owner was still reconciling its version receipt; this integration does not modify that record. The draft preserves the dashboard, shared table controls, scoped Reader links and source corrections. Both response imports are retained where the catalog redirect safeguards meet the new preference endpoints.

The preceding #506 head `53bfc5f5` passed all four checks (6,717 tests), 610 affected checks and native desktop/phone review. The newly reconciled head requires its own checks and current-live preservation. Earlier workflow timings and data counts below remain dated prior-head evidence. The user approved removal of only the earlier redundant #506 test copy; its 25,271 files were rechecked against retained base/delta recovery archives before cleanup. Archives, receipts, images and live data remain.

**Earlier preparation snapshot (retained with its original scope):**

Updated November 4, 2026. All 31 original requirements and their order remain
verbatim below. The mission remains active; this reconciliation retires no
requirement or human gate.

## Verified releases and current candidate

| State | Work | Evidence and next gate |
| --- | --- | --- |
| Live | Source-intelligence #501, `d785c182` | Read-only observation confirms matching recorded/running image `ed6d0f4c` and healthy status. It retains catalog #492. |
| Completed prior-head evidence | Combined #506, `e0d898c7` | All four checks/6,686 tests, 455 affected checks and native desktop/phone review passed. Fresh private review preserved five accounts, 1,259 profiles, 11,830 existing JSON records, four databases and 1,115 research files; 47 route/PDF checks passed. Six source/README files added, zero existing data changes. |
| Current draft | Combined #506 reconciled with live #501 | Retains exact platform #500, source #498, harvest/Learn #504 and checklist #503 components plus newer canonical source-intelligence work. Fresh current-head CI, browser and live-copy checks remain required. No approval, merge or deployment. |

Twenty-four complete-response comparisons on the preceding head matched across
eight fresh processes; all 25,271 isolated runtime files remained unchanged.
Measured workflows improved about 47–49%; first catalog visits still took
5.8–6.4 seconds. These are bounded server-copy measurements, not universal live
timings or acceptance of this revision. Keep TD-122 open.

## Work remaining here

| Work | Next action | Completion evidence |
| --- | --- | --- |
| Combined release | Validate the revision on actual live #501; then present the tested exact head. | All four checks, native desktop/phone review, consistent private-data/workflow preservation, explicit exact-head approval, fresh release-time backup, retained rollback and verified live behavior. |
| Cold-load speed / TD-122 | Measure the final catalog's first visit and subsequent workflow; improve only with equal complete responses and fresh edits. | Current-copy timings; rejected disk/reader/source caches remain excluded. |
| Catalog depth / CAT-01, CAT-02 | Continue the 77-subject plan, 11 unreadable originals and cited profile/role/rights/region/photo depth. | Literal names and exclusions accounted for, original sources and operator edits preserved; no unsupported worldwide-completeness claim. |
| Independent review | Retain the 32-source expected-name packet, 32 unclear photographed cells, organization holds and name/code/role/rights/photo queues. | Independent human answers and explicit decisions; parser output cannot supply its own answer key. |
| Map figures / MAP-02 | Review 24 references/51 original-unit figures across eight countries, including two UK discrepancy holds. | Human selections retaining crop, geography, period, units and citations; company presence is not a growing footprint. |
| Learn depth | Retain 27 lessons and the completed editable provider acceptance draft; improve citations/media/scientific quality. | Attribution, preserved edits/history and human quality review. No additional paid call or retry is authorized. |

Help at `/guide` already explains sections, analyst workflow and reporting.
Workspaces, company favorites/tiers/lists and saved Explorer views are shared;
only Personal Digest and layout settings are private. All accounts including
Chris.H, data mounts, settings, research and existing edits remain protected.
Publication review, statement review, source authenticity, catalog identity,
commercial roles and photo permissions stay separate human decisions.

The prior canonical #492 public audit found 539 source sections/2,073 literal
occurrences/899 derived candidate keys. These are dated public-seed counts,
not approved varieties or current private-catalog completeness. The 77-subject
plan has 67 named, seven partial, one unavailable and two identity holds;
[partial-portfolio dispositions](PARTIAL-PORTFOLIO-SOURCE-DISPOSITIONS-2026-11-04.md)
retain the exact gaps without automatically correcting identities or websites.

Old #500 approvals are not approval for #506. Existing backup archives and both
original test copies remain retained. No extra cleanup, bulk import or paid
provider request is authorized. Keep component PRs open until canonical
incorporation is verified after an approved release. Earlier active texts are
preserved in [history](REDESIGN-REQUIREMENTS-CHECKLIST-HISTORY.md#november-4-2026---checklist-before-live501-reconciliation).

## Original accepted requirements

All 31 IDs, definitions and ordering are unchanged. Updated evidence/status
cells do not change the accepted requirements or mark their open reviews done.

| ID | Accepted requirement | Delivery evidence / state | Remaining verification or implementation |
| --- | --- | --- | --- |
| CAT-01 | Reconcile sources against the variety catalog so visible named varieties cannot disappear silently | Source-specific company/article/name handoffs are retained in live #411. The current canonical public-data audit accounts for 2,073 source occurrences across 539 sections; 881 are catalog text matches and 1,192 require review. Candidate keys are counted separately: 899 in this public-only calculation. | Source matching is not an identity approval or proof that every article name is detected. The independent 32-source expected-name audit and actual source/name/role decisions remain open. Editable catalog #492 is merged but was not observed deployed; #500 retains its editor and consolidates removal confirmation. |
| CAT-02 | Build toward the most comprehensive berry variety resource, with measurable gaps and refreshed provenance | Current canonical public-only audit: 539 sections, 2,073 literal occurrences, 899 derived review keys. The 77-subject plan has 67 named, seven partial, one unavailable and two identity holds; 11 sections are unreadable and 143 have follow-ups. Counts follow this exact catalog and exclude the private inbox. | Complete current/historical portfolios, readable originals, independently reviewed identities, traits, rights, growing regions and photo permission remain open. Pending source #498 adds two literal historical labels and complete Nebula context; it does not approve a variety, role or region. |
| UI-01 | Bright, colorful agricultural Glasshouse identity; first berry icon; subtle glass, stronger contrast and hierarchy | Approved Glasshouse identity and first icon across core, intelligence, authoring, public-library and retained shells (M1–21/34/35); source prose stays literal. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| UI-02 | Immersive full-width workspace, compact top navigation, grouped More menu contained within the viewport | Full-width shared top header, contained grouped More, folded specialist destinations; live/private versus generated-public navigation tested (M20/21/35). | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| UI-03 | Dense information with useful headlines, summaries, metadata and collapsed secondary context; plain language | Dense headings, card/table hierarchy, folded secondary context and the deployed Company/Reader readability work remain retained in live #411. The #500 combined desktop/390px review passes its crop handoffs, catalog removal confirmation and interactive Learn/photo presentation. | Deep cold catalog loading remains open under TD-122. A browser review or passing page render does not prove full article availability, every advanced form or scientific/source completeness. |
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
| LEARN-01 | Top-level expanded Learn, detailed visual lessons/research first, pictures/diagrams/video links, interactive exploration | The 27 visual interactive lessons and existing credited media remain delivered. Pending #500 adds presentation improvements and three credited photographs; its current head passes 6,679 tests and desktop/phone review. | Broader source/citation/media depth and scientific quality review remain in this mission. Pending #500 still needs current-live preservation and release approval; education never promotes a scientific or competitive claim. |
| LEARN-02 | Select/highlight content -> research/add to Learn -> explicit Perplexity deep research -> new learning content | Selected-text/Reader Learn actions, explicit context, durable high-effort research jobs and editable cited drafts are delivered. #473 repairs high-depth requests while retaining legacy medium jobs. #486 also delivers the actual-result presentation repair and deterministic visual-context fallback, retaining saved texts, request settings, run IDs, user edits and history. | The single authorized real high-effort request completed at provider-reported USD0.13679 and remains an editable AI draft. #480 is superseded by fulfilled live #486; no release approval is still needed for that repair. Broader citation,media and lesson-quality review remains. No further paid request is authorized; education never approves a scientific/competitive claim. |
| INT-01 | Plain-language investigation workspaces without changing review decisions | Intelligence home preserves Statements, Signals/candidates, Assessments, Recommendations, Questions, Research and native authoring. M11–17/20/35 verify named references, literal source text and separate gates. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| MON-01 | Consolidate Monitor watches/changes/alerts while retaining distinct intent and action | Monitor consolidates Watches, Alerts and Monitoring plans, retaining marks/list/multi-berry predicates, read/dismiss/pause/resume history and Reader; #283 green and M35 retained shell. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| OPS-01 | Consolidate collection, review and quality surfaces without losing specialist tools | Operations consolidates Collect, Review, Data quality and Coverage & health, retaining specialists. Source authenticity (M34) stays separate from publication/statement approval. | Release acceptance recorded in RELEASE-REVIEW.md; source availability and independent human decisions remain explicit. |
| GUIDE-01 | Visual explainer of site sections, analyst workflow and reporting capabilities with clear purpose/how/working state | The visual explainer is live through approved #474, merge7fa7dd53. It retains twelve site-section cards, four analyst steps, prior reporting choices and shared Workspaces guidance, and now explains company comparisons, retained coverage and accurate saved-comparison JSON/CSV behavior. All four checks pass/6,091 tests; desktop/phone, fresh isolated preservation and live verification pass. | The requested visual explainer and follow-up are delivered. Wider educational/media depth and human source/catalog decisions remain open; no new approval is needed for completed #474. |
| REL-01 | Integrate approved stack, reconcile canonical, run all gates and prepare release/rollback plan for intel.johnnyaceii.com | At the November 4 09:23 UTC read-only observation, live #411 at 34eb23c3 has matching recorded/running image d8601b96 and healthy status. Catalog #492 is merged in Git. Platform #500 at 15295070 passes all four checks/6,679 tests; source #498 at d8d94411 passes all four/6,627 tests. Both pass desktop/phone review. | Neither draft is deployed. Their fresh current-live preservation checks and separate exact-head release approvals remain. The old #500 b2452a89 approval stopped at its stale-base guard; the unanswered 7ace95b7 question is superseded. No new approval, data import, provider call or additional cleanup is inferred. Keep backups, rollback, settings and data mounts. |
