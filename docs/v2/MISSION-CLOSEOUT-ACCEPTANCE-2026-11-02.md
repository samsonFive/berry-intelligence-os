# Mission closeout acceptance

Current live release #470 (`d2f6eb96`) retains the approved #443 redesign,
#469's private patent research and its original-row spreadsheet follow-up. Its
platform release #468 is still in verification: the first canonical-target CI
run found a 538.9 ms warm-Reader request against the unchanged 500 ms test.
The bounded preparation repair and complete-output controls are documented in
[the Reader review](READER-CLOSEOUT-PERFORMANCE-REVIEW.md). New exact-head CI,
native review and server-copy preservation must pass on the reconciled #470
base before release approval. Existing private research profiles, source rows,
contacts and user edits must survive that check.

Source #467, catalog/Map #449 and Learn #464 have separate scopes. Their prepared
evidence does not make them live or grant approval to combine them. The full
mission remains open for release acceptance and the catalog/research items below.

The original 31 accepted definitions and their order remain in
[the requirements checklist](REDESIGN-REQUIREMENTS-CHECKLIST.md). This matrix
adds evidence and limits; it does not replace those definitions. A fixture test
proves the tested behavior, not provider availability, independent research
quality or worldwide completeness. The prior 95-route audit proves rendering
and access gates, not every form workflow.

## Requirement evidence

| ID | User outcome and inspected evidence | Closeout state |
| --- | --- | --- |
| CAT-01 | Named sources remain visible through reconciliation and candidate handoffs. Portfolio/source/photo regressions and #467's all-earlier-key preservation cover omissions and saved decisions. | Partial: human name/source/role decisions and independent expected-name review remain. |
| CAT-02 | Source plan, gap inventory, current/historical distinctions, original patents and held photos are present. Prepared #467 has 534 source sections and 2,019 occurrences. | Open: those counts are not distinct varieties, current rights or comprehensive web recall. |
| UI-01 | Approved Glasshouse design, first berry icon and retained shells; prior desktop/phone acceptance and `test_ui_v2_shell.py`. | Implemented; preserve the accepted visual language in final smoke review. |
| UI-02 | Full-width shell, contained grouped More, retained destinations and responsive navigation; shell/navigation tests and prior native review. | Implemented; keyboard-clearance follow-up is in #468. |
| UI-03 | Compact cards/tables, distinct title/body/metadata and collapsed secondary context; News, directory and export readability tests. | Layout implemented. Cold-load performance remains a limitation; the Reader closeout repair requires final gates. |
| NEWS-01 | `test_news_workspace.py` checks newest publication first, exact quick/custom dates, multiple berries/countries, bounded previews and scope. `test_news_images.py` checks real images, explicit illustrations and safe URLs. | Implemented; image/body availability remains source-dependent. |
| NEWS-02 | Trusted requires reviewed publication plus active escalation; reactions/save remain separate from truth. News and account tests retain review gates and shared reactions. | Implemented; reviewing a publication does not approve every statement. |
| NEWS-03 | Shared overlay and publisher handoff, consent-body rejection, actual text and safe image selection; UI shell, Astra Reader, publisher-chrome and source-body tests. | Implemented with pending #468 repairs; missing/blocked publisher text remains explicit. |
| DIGEST-01 | Account tests cover saves, progress, reading location, explicit list subscriptions, concurrency and legacy retention. | Implemented: Digest/layouts remain personal; collaboration stays shared. |
| CO-01 | Directory tests cover separate favorite/tier/list state, retained legacy values, concurrent membership and cross-view filters. | Implemented; user values must survive the final preservation check. |
| CO-02 | Profile precedence/history, editable links, contact-scoped restore, People highlights and logo permission tests; prior native upload proof. | Implemented; collected suggestions preserve manual edits and blanks. |
| VAR-01 | Supplied-photo seed has 144 transcribed rows and 32 explicit unresolved cells, with company association kept separate from breeder/owner role. | Partial: the 32 uncertain cells need human correction/confirmation. Temporary originals are unavailable in their former paths. |
| VAR-02 | Region research tests reject headquarters/sales/rights as growing, retain source/country/activity/date and preserve edits; Map layers remain distinct. | Implemented workflow; region depth and individual source decisions remain open. |
| MAP-01 | Global Explorer tests cover country/berry composition, empty/invalid scope, real boundaries, multiple berries, trusted snapshot and PDF escaping. Prior native country-to-News/snapshot acceptance remains. | Implemented; retain keyboard/touch and the Peru/Chile/China handoff in final smoke review. |
| MAP-02 | Cited baseline, explicit research jobs and selected figures retain units/periods and references. #449's new figures are staged separately. | Partial depth; #449 is not deployed and held discrepancies are not selected automatically. |
| PACK-01 | Packet tests check the exact versioned schema, separate competitor rows, original URLs, all 77 supplied roster subjects and provisional exceptions. | Implemented; unresolved identities stay provisional. Receiving-system integration remains a separate request. |
| PACK-02 | Packet tests distinguish reviewed publication from Atomic review, retain generation-time dates/history and prevent failed exports advancing the last-generated marker. | Implemented; source review is the user's selected meaning of Reviewed. |
| PACK-03 | Failed/stale capture blocks generation; successful capture is required within 15 minutes, with explicit dates, identity and exception behavior. Deterministic transport fixtures cover the lifecycle. | Implemented; provider completion/coverage remains observable and cannot be promised exhaustive. |
| AUDIT-01 | Section audit and 95-route review retain useful workflows and deliberate access gates. Existing statement-link defects prompted the #468 repair. | Implemented audit; sparse usage does not establish a zombie page. |
| REPORT-01 | Reports & Briefings distinguishes executive view, selected briefs, editable reports, snapshots and news packets. Briefing/report tests retain separate scopes. | Implemented; outputs keep their source/trust semantics. |
| REPORT-02 | Meeting Prep preserves old routes, selected scope, notes and explicit question-generation action; briefing tests cover history/edit retention. | Implemented; read-only browsing starts no provider job. |
| REPORT-03 | Export readability tests retain literal edits/qualifications, readable references, stable source numbering, date distinctions and long-text flow. Prior desktop/phone/PDF review covers the designed outputs. | Implemented; final smoke review must retain readable documents and original user wording. |
| LAND-01 | Explorer subject/place/section/date scope and saved views remain shared; workspace/account tests preserve separate personal layout preferences. | Implemented; workspaces are collaborative. |
| LAND-02 | User-approved blueberry continuation, four crops, All berries, comparison, saved views and PDF/HTML/SVG/CSV are delivered in #398 and retained by Explorer tests. | Implemented platform; catalog/trust depth remains CAT-01/CAT-02. The old blueberry stop is satisfied. |
| LEARN-01 | Top-level Learn, 27 visual lessons, diagrams, attributed images/video links and interactive glossary are delivered in #440; guide/learner tests retain entry points. | Implemented; broader scientific/media coverage remains ongoing. |
| LEARN-02 | Research tests cover selected approved context, durable jobs, one paid submission, cancellation/resume, native citations and edit preservation. #464 corrects current API effort for detailed lessons. | Prepared follow-up: #464 is not deployed. Live high-effort provider quality/cost is not established by fixture tests. |
| INT-01 | Investigation surfaces and literal canonical statement destinations retain source/truth labels and separate dates. Statement and investigation tests cover the repair. | Implemented; #468's navigation fixes await release. |
| MON-01 | Monitor tests cover shared watches, alerts/history, stale state, damaged stores, multi-berry filters and pure browsing. | Implemented; watch intent does not confirm a signal. |
| OPS-01 | Collection, Review and Quality retain specialist routes. Publication, source authenticity, identity and Atomic qualification have separate human gates and read-only/static boundaries. | Implemented consolidation; pending human reviews remain decisions rather than disappearing queues. |
| GUIDE-01 | Read-only Help explains 12 workspaces, four analyst steps and six report choices, including Capture → Connect → Brief. Guide/static tests and prior native review cover the visual explainer. | Delivered at `/guide`; it is the requested explainer, not an unfinished presentation. |
| REL-01 | Live #470 retains #443, private patent research and row-aligned spreadsheet copying. Earlier component receipts remain historical evidence; #468 now reconciles onto current canonical. | Open: revised exact-head gates, scoped approval, release-time backup, deploy/rollback and post-switch verification remain. |

## Human decisions and research still open

The closeout packet separates four kinds of work. Deployment approval does not
answer any of them:

1. **Photo transcription:** 32 uncertain seed cells retain literal visible text,
   company label, berry and image number. Confirm the actual name/placement;
   do not infer a breeder role. The four temporary original-photo paths no
   longer exist, and matching attachment filenames were not found in the
   attachment cache. A clearer original or a supplied correction can resolve a
   cell; existing transcriptions remain untouched.
2. **Organization identity:** Genetics Uruguay is too generic to identify a
   company. Mario Aguas-Alvarado is a person, with a separately noted potential
   affiliation; no company is created from his name. Clarification should name
   the intended organization or retain the person as a contact.
3. **Independent expected names:** the retained 32-source worksheet has no
   completed expected-name lists. It needs human reading of the saved words.
   Detector results are not prefilled as expectations. Publication authenticity,
   name identity and benchmark qualification remain separate decisions.
4. **Photos and research depth:** unknown reuse stays held, with attributed
   source links and explicit session preview. Current rights, full portfolios,
   growing regions, traits and independent recall need further evidence.
   Counts and green CI cannot establish the most comprehensive resource on the web.

These catalog decisions remain visible alongside the platform release; they do
not silently become approved facts or default-loaded photos. Public documents
contain no private article bodies, reviewer answers or authentication material.

## Final acceptance sequence

Finish #468's gates and its short desktop/phone walkthrough: latest News,
Reader article/publisher access, shared company/list/workspace state, private
Digest/layouts, Map/Landscape handoffs, and a designed report/export. Validate
the new exact head on a fresh bounded server-data copy. Then request that
release's exact scoped approval. After approval, take a fresh release-time
backup, retain rollback and verify accounts/data plus the same workflows after
the switch. Source/Map and Learn releases require their own reviewed scopes.

Full mission completion remains unproven while any original requirement or
required review remains open. This audit records those items explicitly.
