# Mission 14 — Intelligence reading hierarchy

Build on draft #286's verified head `4dd928cca2f859f25542064b30ea492a005f5ba4`. All four checks passed on run 37051961517: 3,549 passed, 11 skipped, two warnings in 326.38 seconds. This follow-up continues the approved hierarchy and plain-language requirement into the existing analyst reading surfaces. It is not a new intelligence model or a release approval.

## Reading experience

The four catalogs and their detail pages — Signals, Assessments, Recommendations and Strategic Questions — share Intelligence navigation and the accepted bright Glasshouse shell. Recommendations is reachable within that workspace. Catalog titles, summaries, metadata and status have distinct visual roles; the recommendation table retains its compact columns and scrolls inside its container on phones.

Signal, Assessment and Recommendation detail emphasizes the first authored reading unit and keeps every remaining observation, rationale and qualification visible below it. The first unit is an emphasis choice, not an AI-generated summary or a rewritten conclusion. Why it matters, decision conditions, supporting facts/sources and counterevidence remain visible. Source support precedes optional related-company/question links. Review metadata and related inventories are native, initially closed disclosures, with keyboard focus retained. Human alert/proposal actions remain explicit and do not change canonical record status through this presentation work.

Questions leads with the linked analyst views, then facts, watched patterns, contradictions, gaps, decision conditions and recommendations. Full company/variety/geography scope, coverage counts and the source index remain available below the reading sections in closed disclosures. All existing section anchors and handoffs remain. Captured-only source dates are explicitly labeled `(captured)`; publication date retains precedence and undated sources stay undated. No confidence/readiness score is inferred from coverage counts.

## Bounded correctness and privacy fixes

Read-only Signal and Recommendation detail no longer loads private analyst alert/proposal decisions. Private investigation tabs and decision state stay out of public rendering. Static pages retain the established public base and source links, with the same reading body; the global static navigation redesign remains outstanding.

Assessment `counterevidence_ids` already supports both Fact and Evidence identities. The old detail resolved only Facts. Live and static rendering now include the published-source half too, with original IDs and classifications retained. This corrects an omission without adding a fact, resolving a contradiction, changing canonical data, or bypassing publication/atomic/identity review.

## Verification

Local test evidence before the final combined run: 157 existing specialist/static tests passed; 111 reading/synthesis/question tests passed after hierarchy changes; 49 Question tests passed after scope reordering; 28 passed after capture-date provenance; 11 final reading-preservation/privacy tests passed with the separately verified static test excluded. Final combined local run: 170 focused reading, synthesis, Question, scope, Signal-review/candidate and static tests passed, one existing reportlab warning, in 170.42 seconds. It includes the full static counterevidence build after the final source-date and caption changes. Tests check every authored unit across the existing three judgment families, both Fact/source counterevidence, unchanged records after reads, public views failing before any private-state read, retained question anchors/Reader links, capture/publication/undated semantics and full static generation.

One initial new assertion did not account for HTML-escaped apostrophes; it was corrected to compare decoded content. An accidentally escalated local test process could not access its external temporary/cache directories, producing setup errors rather than app failures. Default-sandbox reruns use a unique workspace-contained test directory and disabled cache. No application permission or review gate was weakened.

Canonical validation passed. A local static build wrote 1,755 pages and reported no unpublished IDs or titles. Final static/public and full-suite acceptance also require the pushed head's four GitHub checks.

Browser review used the isolated authoring preview and real canonical records: all four desktop catalogs/details; 390px Signal, Assessment and Recommendation catalogs/details and Question detail; source tables contained their horizontal overflow. Observed page width was 375px at a 390px viewport. Native Review details and Supporting source index opened/closed with Enter; the source index retained 54 linked sources in the reviewed question. Recent-source drill-through opened the shared Reader; unavailable article text was honestly disclosed and the publisher link stayed available. Closing returned to the same question and source link. The subsequent navigation raced the Reader's asynchronous close once; a fresh state check and direct catalog navigation recovered it, without repeating any write.

No human trust/proposal/alert decision, canonical edit or provider research was performed in this browser review. Opening the Reader recorded reading progress only in the isolated sample personal store. Temporary viewport overrides were reset. Desktop/mobile screenshots are under `artifacts/design-sprint/`, named by catalog/reading view.

## Remaining work and release boundary

Research/Ask Berry, candidate-review and authoring forms still need their controlled presentation pass. The shared static navigation, deeper specialist layouts, broader sourced Learn visuals, source/body/media acquisition, editable enrichment/region suggestions, public-statistics freshness, packet compatibility, account/multi-worker persistence and canonical/active-PR reconciliation remain on the durable checklist. This slice does not close those requirements. Continue the ongoing goal; prepare the combined tested release and rollback plan for final human review. No merge or deployment.
