# Provenance gaps

Gaps observed across this mission's real bounded run and the resulting
rehearsal pack, distinct from the per-item `provenance_completeness` field
in `ITEM-DECISION-MATRIX.md` — this file focuses on *systemic* patterns
worth an operator's attention, not a single item's own record.

## 1. Reporting/persistence discrepancy: "Navigating Super El Niño With Luis Vegas (Part 2)"

`scripts/run_recent_batch.py`'s own JSON report
(`artifacts/publication-review-candidate-pack-v1/inventory-run-report.json`)
recorded this item (`discovered-source-business-of-blueberries-podcast-78eaf24b2941fdcb`,
published 2026-09-09) as `state: "awaiting_publication_review"`,
`review_ready: true` — implying a draft was created and given a
`publication_draft_id`. No corresponding file exists under this
worktree's `inbox/evidence/` after the run completed; only 7 of the 8
`review_ready: true` items in the report have a matching draft file.

This is reported honestly as a real, observed discrepancy and was **not**
investigated further or fixed — this mission's scope is inventory, not
extraction/orchestration repair, and the same source produced a normal,
verifiable draft (`rehearsal-03-metadata-only`) for its other selected
item in the same run, so this does not appear to be a systemic source- or
adapter-level failure. A future mission auditing
`app/services/media_orchestration.py`'s `OrchestrationResult`/draft-write
sequencing under back-to-back same-source processing (two items from one
source in one batch) would be the right place to look.

## 2. No transcript reached this pack's real items

None of the three real podcast items selected by this mission's bounded
run (`--max-tier 2`, publisher transcript or captions only, no Whisper)
had a publisher-declared transcript or captions detected. This is
consistent with the codebase's own documented expectation ("review-ready
without transcript is a valid state" — `AGENTS.md`) rather than a defect,
but it means this mission could not source rehearsal item 2
(transcript-backed item) from a live example — it is the synthetic
fixture in the pack, explicitly cited to the real, already-trusted
`ev-lucentlands-scaling-blueberry-industry-2025` record and the real
`TRANSCRIPT_PUBLISHER` mechanism it is modeled on.

## 3. AI enrichment is the dominant provenance layer for metadata-only items

Every real metadata-only/weak-entity/defer item in this pack (slots 3, 6,
9, 10) carries its most substantive content — `summary`, `why_it_matters`,
`suggested_entity_ids`/`suggested_berry_ids` — from untrusted AI
enrichment (`ai_enrichment.model_provenance`), not from any independently
verified source. This is the existing, correct, provenance-tagged
behavior (`trust_state: "untrusted_suggestion"`/`"untrusted_triage"`
throughout), but it means a reviewer's real provenance chain for these
items is: publisher feed metadata → AI-generated interpretation → human
review. There is no independently-verified middle layer for
short-form/metadata-only intake. This is a known, honest gap in the
architecture, not something this mission introduces or should paper over.

## 4. Discovery-level failures are invisible in the acquisition-outcome ledger

The two YouTube-feed 404s (`source-redagricola-on-the-road`,
`source-blueberries-tv-youtube`) never reached
`article_acquisition_outcomes.py`'s ledger at all — that ledger only
records *acquisition* (body/transcript fetch) attempts, not *discovery*
(feed-fetch) failures. An operator relying solely on Source Health's
"ARTICLE-BODY ACQUISITION" summary line would see nothing for these two
sources today, even though both are silently failing at the very first
step. This is a real, structural provenance gap between discovery-level
and acquisition-level failure visibility — worth a future mission's
attention, but out of this mission's own scope (inventory, not repair).

## 5. UF's "malformed/incomplete" item correctly left an outcome trace despite creating no draft (verified, corrected from an earlier draft of this file)

The `article_acquisition_failed` item (UF "2025 End Of Season Data
Summary Fbga Fall Meeting") produced no draft (correctly — borderline
relevance plus a genuinely empty body, dropped before ever reaching a
human reviewer), but **does** have a real, persisted outcome record at
`inbox/operations/article_acquisition_outcomes/source-20260901-blueberrybreeding-newsroom/discovered-source-20260901-blueberrybreeding-newsroom-2382fa05a8ba83c4/`
(`outcome_category: "navigation_only_shell"`, `publication_or_draft_id: null`).
This confirms `_record_attempt()` fires and persists a durable, auditable
outcome even when no draft is ever created — a good, already-correct
property (an operator can reconstruct "what was tried and why it failed"
purely from the outcome ledger, without needing a surviving draft), worth
noting explicitly since it is easy to assume a no-draft outcome leaves no
trace at all. It does not.
