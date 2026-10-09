# Landscape Explorer — blueberry review checkpoint

October 9 integrated checkpoint: [current review handoff](BLUEBERRY-INTEGRATED-REVIEW-HANDOFF.md)
supersedes the earlier preview/artifact links for the stacked candidate. It includes
the denser portfolio roles, corrected focus/evidence URL restoration, current
visual workflow/reporting guide and verified native briefing downloads. Parent
#373 is all-green; the new draft's exact-head checks remain a separate gate.
Blueberry feedback, other-berry rollout and merge/deploy gates remain open.

**Mission remains open. Milestone A is the current review candidate; Milestone B is explicitly gated on user feedback. Do not enable other berries, merge or deploy at this checkpoint.** The full approved scope is retained verbatim in [the executable brief](LANDSCAPE-EXPLORER-BRIEF.md). This document is the durable resume checklist, not a replacement or narrowing of that brief.

## Identity and existing architecture

- Branch: `feature/landscape-explorer`.
- Canonical base: `v2/intelligence-os`, `7962ac04dd05855985f51596f3f8070f19990a75` (merge of redesign release PR #312). GitHub default branch is `master`; repository governance identifies `v2/intelligence-os` as canonical.
- Final HEAD and the exact-head required-check run are recorded in the draft PR description; use `git rev-parse HEAD` in this checkout to resolve the local review identity. Draft PR [#313](https://github.com/samsonFive/berry-intelligence-os/pull/313) carries the review artifacts, implementation and final verification identity. The [review packet](LANDSCAPE-EXPLORER-REVIEW.md) records the walkthrough and measurements.
- Existing components inspected: RequestCorpus/repositories; geography `part_of` hierarchy; global explorer and GeoJSON boundaries; variety role buckets and dossiers; `genetics_geography`; timeline and change/scenario engine; source-independence clustering; source/claim review policies; region annotations; saved Landscape selectors; report/brief export infrastructure; provider-neutral untrusted completion adapter; Glasshouse shell; remote session middleware.
- Hosting: existing authenticated FastAPI service in Docker, persistent runtime mounted at `/app/runtime`, Caddy reverse proxy to `app:8000`; public GitHub Pages snapshot is a separate static build. This feature adds no hosting, dependency, API key or infrastructure. No production access/change is necessary for A.

## Milestone A implementation

The additive read-only adapter is `app/services/landscape_explorer.py`; the same complete selection bundle drives landscape, chronology, explanation and exports. No persisted records, identity merges, human reviews, domain schemas, CPVO, footprints, trade/weather stores or user annotations are changed.

| Requirement | Delivered behavior / proof |
|---|---|
| App navigation and dossiers | Live Landscape navigation; contextual company and blueberry variety links; existing overview and saved selectors retained. Analyst-only route `/landscapes/explorer`; News Reader intact. |
| Berry-neutral engine, blueberry gate | Canonical typed nodes and predicates, explicit berry tags. Route enables blueberry only; other registered berry requests return a clear review-gate error. |
| Portrait / geography | Stable name/ID ordering; country lanes; expandable company roles; separately labeled connected genetics; locator reuses existing boundaries and explicit ISO tags. No force layout or article-count geography. |
| Genetics and commercial roles | Existing breeder, owner, licensee, grower, marketer, distributor, trial, seller and partner roles. Each connection is an exact registry relationship; shared companies never materialize variety locations. |
| Focus / keyboard / state | Immediate neighborhood highlighting and labeled connection diagram; synchronized keyboard-accessible table and evidence buttons. Focus, source selection, filters, theme and view travel in the URL. Country endpoints are labels, not invalid company-focus controls. |
| Scope / progressive disclosure | Country multi-select, exact alias search without identity merging, role/review/status/date filters, reset. Default display 100 nodes / 200 edges, visible hidden counts and expansion; explanation and exports retain full selected scope. |
| Change clocks | Recorded effective date, source publication, earliest supporting-source capture are separate. Capture means newly documented; standing links survive date windows. Unknown dates remain unknown; historical labels do not assert an end date. |
| Conflicts / review / provenance | Disputed and historical links retained; reviewed source is separate from claim approval. Intent, registered office, test station, rights enforcement, inferred support and legacy substituted-role caveats are explicit. Provisional identities retain review-needed labels. Source summaries are not presented as verbatim quotations; unavailable locators are explicit. |
| Three explain presets | Selected-markets, selected-genetics, selected-window questions; bounded visual diagram plus complete cited findings, changes, interpretation and unknowns. Deterministic, no provider calls. Optional-output validator accepts only exact existing propositions/citations, otherwise falls back; no model feature is activated. |
| Exports | Standalone printable HTML, vector SVG panels, relationship/source CSV; filters, focus, clocks, generation, data version, legend, findings, boundaries and numbered links retained. Complete scope, not viewport. CSV separates one relationship/source association per row and neutralizes spreadsheet formulas. |
| Authorization / versioning | Same remote session and analyst-mode boundary on UI, API and every export. API/downloads private and no-store; no static route or private data publication. Bounded immutable cache keyed by whole-record content and filters, including edits/deletions. |
| Verification | `tests/test_landscape_explorer.py` covers typed trace, supported fixture cross-country genetics, false mention links, containment, ambiguous aliases, roles, review/history/disputes, chronology, syndication, removals, invalid output, parity/safety, truncation and authentication. Review outcomes are recorded in the review packet. |

## Actual corpus and truthful limits

Default reviewed-source Chile / China / Peru scope: **53 nodes (16 companies, 4 programs, 30 varieties, 3 geographies), 82 relationships (80 active, 2 disputed), 47 source records, 19 conservatively clustered origins, 10 company-location links, zero direct variety/program-location links.** Sixteen relationships have a recorded effective date. Four variety identities remain provisional: Arana, Eterna, FC11-164, Twilight. Counts describe captured coverage, never company scale, market share or variety adoption.

The canonical registry has durable genetics and company geography edges, but no durable direct Variety/BreedingProgram → Geography edges. Source co-mentions, operating regions and analyst annotations cannot fill this gap. A multi-country corporate picture is real; a multi-country same-variety growing footprint is not established. Generic direct genetics-location behavior is tested with explicitly synthetic fixtures only. Legacy inferred/substituted role records retain visible caveats and their original notes without promoting them to verified facts. No extraction job is necessary for durable existing relationships, and browsing never triggers extraction or acquisition.

Historical chronology is not reconstructed. First capture dates are source-capture proxies, not an append-only relationship creation log. Legacy `operates_in` records sometimes encode intent, test stations, registered offices or rights enforcement; the adapter preserves the predicate with explicit caveats. Evidence excerpts/extraction versions are sparse; missing provenance is disclosed, not invented. Repeated stories do not inflate independent corroboration.

Other known limits: inline connection diagrams use staged disclosure; large complete SVG exports are tall multi-panel vectors, with printable pagination supplied by HTML. Browser print-to-PDF is not labeled as a downloadable PDF feature. This app currently has one authenticated analyst workspace, not per-user accounts; the new read-only feature creates no new shared saved-state store. Existing user notes are not promoted into the approved graph. The public static site does not publish this analyst-only explorer.

## Required stop / resume contract

At A deliver the draft PR, exact branch/base/HEAD, working preview/start instructions, desktop/mobile/both-theme screenshots, a real exported briefing, five-minute walkthrough, checks and measurements, supported counts and limitations. Request feedback on **readability, trust, analyst usefulness and export quality**, then STOP. A review-ready blueberry implementation does not complete the full mission.

After explicit feedback approving continuation, resume this branch/draft PR and perform B in this order:

- [ ] Apply agreed blueberry revisions to shared components first.
- [ ] Enable strawberry, raspberry and blackberry using the same engine; inspect the four existing berry categories and document any inclusion decisions without inventing categories.
- [ ] Preserve each berry's actual licensing/commercialization semantics; retain species boundaries. Integrate existing trait/sensory records only where supported; show gaps instead of borrowed blueberry assumptions.
- [ ] All berries scope; two-berry side-by-side comparison with common actors highlighted and genetic identities/edges distinct. No unsupported volume/influence rankings or across-species variety merging.
- [ ] Integrate existing saved-view facilities with established authorization; distinguish refreshed selectors from frozen snapshots. Do not introduce cross-user visibility or parallel personal-state stores.
- [ ] Downloadable PDF via existing report/brief infrastructure, tested pagination and readable visual panels; label browser-print fallback honestly if applicable.
- [ ] Finish cache/update behavior and agreed UX refinements after review; preserve human review gates and operator edits.
- [ ] Report data sufficiency separately for every berry; thin coverage stays visible. Record unresolved debt and real coverage gains only.
- [ ] Full final regression, real UI walkthrough, authorization, export parity and measured performance; update PR around final implementation and mark ready for review.
- [ ] Obtain subsequent explicit authorization before merge or deploy. Earlier approval for the already-shipped redesign is not approval for this feature.

## Rollback and invariants

Feature is additive: remove the explorer router registration and its live navigation/dossier links (or revert feature commits) to disable it. No database migration, data rollback or provider cleanup is needed. Old `/landscapes`, existing saved views, News, Map Explorer and dossiers remain operational. Keep `INTELLIGENCE-EXPANSION-BUILD-GUIDE.md` verbatim. Do not disable authentication to publish the preview.

At delivery, Milestone A is the tested blueberry review checkpoint in draft PR #313; final exact-head checks are recorded there. Remaining berries and cross-berry completion await feedback; the full mission remains open.

## Blueberry feedback revision, October 6–7

The user rejected sparse repeated cards, system-oriented language and missing
varieties named in source excerpts. Replace the portrait with a compact company
by country matrix and grouped program/variety portfolios. Put cited takeaways
first; show offices, breeding tests, plans and IP enforcement in plain language.
Evidence opens when selected, releasing its unused column when closed. Keep
complete relationships, dates and technical references behind disclosure.

Repair the shared source-to-catalog discovery failure, not a Hortifrut-only list.
The eleven Hortifrut names and sixteen MBG code/name pairs now appear beside
sources and in the existing identity-review workflow. Additional candidate names
appear beside directory searches without changing canonical identities or roles.
See [the comprehensive catalog mission](VARIETY-CATALOG-COMPREHENSIVENESS-MISSION.md)
and its repeatable stored-source audit. This necessary read-model fix changes no
Variety schemas, CPVO backends or trusted records. Human decisions win on replay.

- [x] Shared discovery repair and repeatable corpus audit.
- [x] Denser comparison, grouped portfolios and cited overview questions.
- [x] Source-linked candidate visibility in evidence, directory and review queue.
- [x] Final revised desktop/mobile/theme review and local regression. Exact-head GitHub check results are recorded in draft PR #313 at delivery.
- [ ] User review of the revised blueberry checkpoint before other-berry rollout.

October 8 source-catalog continuation: NIAB/Bayer/Masiá name histories and five
held photos now reach private review/company context. Code display is repaired
without role or alias approval. See NIAB-BAYER-MASIA-VARIETY-REVIEW.md for exact
source scopes, tests and remaining gaps. The blueberry user checkpoint above
remains required; no other-berry Landscape rollout or merge/deploy.
