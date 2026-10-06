# Mission 27 — Source-led location review

Company Operating regions and Variety Growing regions now offer an explicit source check from an already linked article or active statement. Perplexity receives the public catalog name/type and that exact public source URL. Private notes, edited statements, article summaries and internal identifiers are excluded. Opening a page neither submits nor retrieves research.

## Delivered workflow

The existing background research client prepares bounded, private proposals with country, locality, activity, effective date, source passage and qualifications. Each proposal requires a native citation to the exact selected source URL; a URL written in generated prose is insufficient. Publication dates stay separate from effective dates. Incomplete or invalid effective dates remain unknown with the original date qualification retained.

Company headquarters, growing, research, packing and sales remain distinct. Variety trials, announced planting, historical growing and commercial growing remain distinct. Patent territories, retail markets, offices and mismatched activities are visibly unsupported; they cannot enter the map through the proposal action. Ambiguous country matches require manual resolution. Country shading represents recorded entries, never acreage or market share.

Eligible suggestions open an unsaved, editable entry. Existing entries in that country and its recorded subregions are available for comparison. The analyst can correct place, activity, date, notes and status before saving. The source identity/provenance is rechecked against current records and cannot be attached to a different source. This is a private working annotation, not publication or Atomic Evidence approval.

Saved location, original research proposal, provenance, replay identity and change history share the same atomic private write. A repeated submission cannot duplicate an entry or overwrite later human edits. Removed entries remain in history and cannot be recreated by replaying their old suggestion. The source-check history links to a currently saved entry; removed entries have a history label instead of a broken edit link. Long source qualifications are retained, with an explicit 4,000-character save limit rather than silent truncation.

## Recovery and boundaries

Durable reservations deduplicate the request token and active source/profile scope, with at most two active location checks in this local workspace. Uncertain submission blocks duplicate starts. Reserved requests can resume or stop; existing runs can be explicitly checked, cancelled or reconnected. Network retrieval runs outside the application event loop. Retrieval failure preserves the existing run, and stale responses cannot overwrite a newer state. Corrupt private history is preserved and blocks replacement. Raw responses and native citation metadata remain private and accessible behind a closed disclosure.

Authorization and same-origin checks precede provider activity. Read-only/public views neither read the private research store nor expose its output. No canonical Company, Variety, Geography, Relationship, Evidence or Fact is written; no model is qualified and no human review gate changes. Serialization is local-worker scoped, not a distributed or per-account job system. Production persistence and worker readiness remain release checks.

## Verification

Final focused location, Map, company-research and static-public-safety suite: **73 passed / one existing ReportLab deprecation warning in 17.26 seconds**. The location/Map subset had **43 passed**. Tests cover protected private input, concurrent submission deduplication, uncertain recovery, resume/cancel, wrong profile/provider/source, stale revisions, corrupt history/proposals, exact native citations, partial results, unknown/duplicate geography, invalid dates, preserved long qualifications, later edits, removal and replay. Canonical records validated successfully. Required CI uses deterministic responses only.

An isolated loopback browser fixture exercised company start/check/compare/correct/save, preserving its earlier headquarters entry, and variety trial prepare/correct/save/source history. Both saved entries appeared in the shared Map table with explicit unreviewed status and unknown effective date. A fictional patent territory remained unsupported. Desktop and requested 390px phone review passed; page and content width were both 375px. Keyboard source-history disclosure worked, and temporary viewport settings were reset. The fixture's fictional passages are prominently labeled; they are not source verification and were never applied to user or canonical data. No live provider call was made for this slice.

Artifacts: `region-source-suggestions.png`, `region-source-unsupported.png`, `region-source-mobile.png` and `region-variety-map.png` in `artifacts/design-sprint/`. Pushed-head CI is recorded in the PR and checklist when available.

## Remaining release work

Subnational boundary layers, selected region/Trade snapshot composition, broader source/body/media and market coverage, account/worker persistence, older-PR parity and combined release acceptance remain on the existing ledger. These are separate from the delivered source-to-editable-location workflow. Final user review precedes merging or deploying.
