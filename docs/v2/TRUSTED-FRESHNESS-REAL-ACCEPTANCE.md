# Trust Semantics Audit + Real Morning Review Acceptance

**Status:** Audit + real production acceptance run, 2026-09-02. No code changed as part of this document -- Issue 1's finding is documented, not redesigned, per explicit instruction.

## Issue 1: Trust semantics of Publication Promote

### What `/review/{draft_id}/publish` actually does (traced, not assumed)

Code: `app/main.py:7165` (`review_publish` route, HTTP concerns only) delegates to `app/services/review_publish.py:183` (`ReviewPublishService.publish`, the actual transaction).

1. The route parses form fields (`title`, `summary`, `why_it_matters`, `source_*`, dates, entity name lists) and a `facts_input` list built from `fact_statement_N`/`fact_classification_N`/`fact_confidence_N` form fields (`app/main.py:7211-7221`).
2. **Validation requires only `title`, `summary`, and `reviewer` to be non-empty** (`app/main.py:7285-7290`). There is no requirement that `facts_input` be non-empty.
3. `ReviewPublishService.publish()` builds `evidence_record` **directly from the draft's own existing fields** -- same `id` as the draft (`evidence_id = request.draft_id`), `status: "published"`, `summary`/`why_it_matters` copied verbatim from whatever form values were submitted (`app/services/review_publish.py:289-314`).
4. Facts are built **only** from `facts_input`; if that list is empty, `facts_to_save = []` and the created Evidence record has `fact_ids: []` (`app/services/review_publish.py:237-255`).
5. The quick-triage form used by `/pending` (`_pending_decision_actions.html`) **does not expose `fact_statement_N` fields at all** -- only the advanced form at `/review?kind=publication` does. A user working the fast triage queue has no UI path to attach a Fact even if they wanted to.
6. `append_review_event()` records `workflow`, `object_id`, `action="publish"`, `prior_state`, `new_state`, `actor`, and the full `subject` dict -- but **not** what was specifically verified, edited, or newly asserted.

### The system already has a stricter mechanism -- for a different content type

For `evidence_role == "atomic_evidence"` (transcript-derived proposals only, created by `app/services/transcript_evidence.py`), the **same route** does something meaningfully different (`app/main.py:7199-7210`, `app/services/review_publish.py:369-378`): the proposed statement becomes the record's title, and the created record gets an explicit `review_outcome: {"decision": "approved", "edited_before_approval": <bool>, "original_normalized_statement": <str>}` -- a real, auditable trace of whether the analyst accepted the proposition verbatim or changed it before approving. **Ordinary Publications (`evidence_role: "publication_artifact"`) never get this treatment.** The distinction the intended architecture draws between "media/publication review" and "factual proposition approval" is not hypothetical -- it is already implemented in this exact file, just never applied to the content type that makes up 100% of the current review backlog.

### Direct answers

- **Does Publication approval itself create canonical Evidence?** Yes, unconditionally, in the same transaction as the "approve this Publication" decision. There is no second gate.
- **What analyst judgment is being recorded?** A binary decision ("promote vs. not") plus a `reviewer` name stamp on whatever text was already pre-filled on the draft. Nothing distinguishes "I independently verified this claim" from "I accepted the pre-filled summary without editing it."
- **Is normalized factual Evidence generated from Publication metadata/body?** No. The trusted record's `summary`/`why_it_matters` are the article's own pre-existing free-text fields, carried through unchanged. Nothing is extracted, decomposed, or normalized into discrete, individually-citable claims unless the analyst manually uses the advanced form's Fact rows -- which the fast-triage UI never surfaces.
- **Is there a distinct Evidence proposition being approved?** No. Same record, same id, before and after.
- **Does any atomic Evidence Review occur for ordinary Publications?** No. That mechanism exists in this codebase but is reserved for transcript-derived content.
- **Does this conform to the intended trust model?** No -- see verdict below.
- **Is `review_event` sufficient provenance for the resulting Evidence?** Thinner than it looks: it proves *who* clicked *what* action *when*, but not *what specific factual claim* they endorsed, nor whether they changed anything from the pre-filled text. `atomic_evidence`'s `review_outcome.edited_before_approval` is the kind of provenance this trust model apparently intends to capture; Publications don't get it.
- **Could a news article be promoted into trusted Evidence without the analyst explicitly approving a factual statement?** Yes -- and this session has direct empirical proof: 9 of the 10 Promotes executed in the prior mission's acceptance run, and all 6 decisions in this mission's real-reading session, were submitted with `facts_input = []` (the fast-triage form doesn't offer the field). Every one of those trusted Evidence records has `fact_ids: []` today.

### Verdict: trust-design defect (conflation), not a working-as-intended distinction

Publication approval and factual-claim approval are materially different decisions -- the codebase's own `atomic_evidence` path proves the designers know this -- but the fast-triage path for Publications (100% of current review volume) collapses them into one click with no distinct factual-proposition object and no `edited_before_approval`-style provenance. The record ends up with the exact same `status: "published"` and the exact same downstream trust label as content that *did* go through a real fact-approval step. This is not a documented, deliberate simplification; it is an unexamined gap between the intended model (visible in the atomic_evidence code path) and what actually happens for the overwhelming majority of review volume.

### Safest correction (documented, NOT implemented this session)

Do not implement any of these without a separate, deliberate decision -- listed in increasing order of intrusiveness:

1. **Cheapest, least disruptive:** add `review_outcome.edited_before_approval`-style provenance to the Publication publish path too (compare submitted `summary`/`why_it_matters` against the draft's pre-fill state), so at minimum the record honestly discloses whether the analyst changed anything or accepted it verbatim. No new UI, no new required field, no behavior change -- pure provenance improvement.
2. **Moderate:** rename/re-label what "Promote" produces so its trust label is honest about what actually happened -- e.g. distinguish "Source confirmed relevant" from "Fact verified" in the UI and in any downstream trust-label rendering, without changing the underlying schema.
3. **Most correct, most disruptive:** require at least one `fact_statement` before a Publication can transition to `status: published`, mirroring what `atomic_evidence` already does -- i.e., actually split "this Publication is legitimate and worth trusting" from "here is the specific claim I am asserting is true," the way the intended architecture already models for transcripts. This is the structurally correct fix but changes the review workflow's click-count and would need its own acceptance pass; it is explicitly **not** implemented here.

None of these were applied. This section is diagnosis and options only.

## Issue 2: Product acceptance was too generous -- corrected

The prior mission's PRODUCT ACCEPTED=YES rested on two errors, both corrected here:

1. **9.88 seconds of server round-trip time was reported as if it represented review time.** It measured HTTP/trust-service latency only -- proof the mechanics aren't a bottleneck, not proof a human can review that fast. This mission's session instead spent real wall-clock time (WebFetch calls) actually reading source content before each decision -- see below.
2. **14-day staleness (2026-08-06 -> 2026-08-19) was accepted as sufficient.** Per this mission's explicit standard, it is not: trusted Evidence must contain meaningful material from the current 72-hour operating window to be product-accepted, and it did not.

### Real human-paced session methodology

Read full source content (via WebFetch, not title/summary skimming) before every decision. First checked whether genuinely current (<=72h) material exists anywhere in the system:

- **Pending drafts (1,699) with `published_date` within 72h of now: 0.**
- **Raw `discovered_media` (4,267 items) with `published_date` within 72h: 0.** Discovery capture is active (newest `first_seen_at` was ~10 hours before this check) but the newest *real-world* published_date across the entire discovery corpus was 2026-08-26 -- 7 days stale, even in raw discovery.
- **This is itself the failure signal the mission anticipated.** The passive/batch discovery-to-review pipeline is not surfacing same-week news for this domain right now.
- Checked whether Competitor Pulse's live, on-demand queries could find anything the batch pipeline missed, across the four companies used in the prior mission's acceptance (Fall Creek, Planasa, Driscoll's, Hortifrut). Fall Creek, Planasa, and Hortifrut returned 0 qualifying results at a live 7-day window. **Driscoll's returned one item within 72 hours**: a peer-reviewed *Frontiers in Sustainable Food Systems* research article, published 2026-09-01, with two named Driscoll's-affiliated co-authors and company-funding acknowledgment.

### Items actually examined (full source content read, not titles)

| Item | Source | Read via | Real assessment |
|---|---|---|---|
| Frontiers strawberry-irrigation cultivar study | frontiersin.org | WebFetch (full article) | Genuine peer-reviewed research; ten cultivars; yield -46%/Brix +25% under reduced irrigation; Driscoll's co-authored and funded. **Promote.** |
| Naturipe organic blueberry variety expansion | naturipefarms.com | WebFetch (full article) | Real named varieties (Envoy, Keepsake, Charisma, Mighty Blues); company press-release tone but factually substantive. **Promote**, with the self-reported nature noted. |
| USHBC President on Mexico's role in blueberry supply | freshfruitportal.com | WebFetch (full article) | On-record named-official quote, real trade figures ($9.1B industry, ~1/3 Mexico share), substantive trade reporting. **Promote.** |
| CPVO PVR -- RIDLEY 1602 | online.plantvarieties.eu | WebFetch attempted, **blocked (HTTP 403)** by CPVO's own bot protection | Public re-verification is not mechanically possible for these records; verification is necessarily against the already-extracted structured `cpvo_filing` fields (denomination/applicant/species), checked for internal consistency. **Promote**, with this limitation disclosed rather than hidden. |
| Costa horticulture scholarship | costagroup.com.au | Title/domain only, **not** full-text read | HR/education-adjacent, not competitive intelligence. **Defer** (not Reject -- may still be worth a later look), disclosed as a lighter-touch triage than the four items above. |
| Arkansas Horticulture Grad fellowship | aaes.uada.edu | Title/domain only, **not** full-text read | Same reasoning. **Defer.** |

### Wall-clock time (measured, not estimated from HTTP latency)

Real server timestamps bracket the session: 2026-09-02T02:46:38Z (start, when the 72h-scarcity check ran) to 2026-09-02T02:52:03Z (end, after all six decisions were submitted) = **~5.4 minutes measured**. This measured span is disclosed but explicitly **not** claimed as representative of human reading pace -- an AI reading/synthesizing four short web pages is materially faster than a human doing the same. A defensible **realistic human-analyst estimate** for the same six decisions, based on the actual complexity of what was read: ~5 min for the full peer-reviewed paper, ~1.5 min for the press release, ~2 min for the trade-quote article, ~1 min for the structured registry check, ~0.5 min each for the two title-only defers = **~10-11 minutes for 6 items**. Extrapolating that per-item pace to the full current-priority queue (~52 items remaining after this session) gives a rough **1.5-2 hour** realistic estimate to work the entire queue with this level of genuine diligence -- well outside the mission's 15-30 minute target for a *full* session, though a bounded 15-30 minute session handling the highest-priority ~10-15 items (as done in the prior mission, now corrected for rigor) remains realistic.

### Trust decisions and results (real HTTP against real production routes)

6 real decisions: 4 Promote, 2 Defer. All succeeded (HTTP 200). `published_evidence`: 1,281 -> 1,285 (+4, exact). `review_events`: 22 -> 28 (+6, exact match to 6 real decisions -- zero trust bypass).

**Newest trusted source date: 2026-08-19 -> 2026-09-01.** Exactly one trusted Evidence record (`ev-pulse-0a9b912a8a0d8c447287`, the Frontiers article) now falls within 72 hours of the current time (2026-09-02T02:52Z) -- the *only* such record in the entire trusted corpus.

### Current-priority queue state and sustainability

`review_now`: 7 -> 3 remaining (2 promoted, 2 deferred). `structured_registry`: 45 -> 44 (1 promoted). This is **one data point from one session**, not evidence of sustained throughput: no history exists yet of this workflow being repeated across multiple real mornings, so no claim of steady-state sustainability is made. The one genuinely-current item found this session required *actively querying Competitor Pulse's live search*, not the passive scheduled pipeline -- the passive pipeline alone still has zero same-week material anywhere in its corpus.

## Newsroom Intake activation verdict

**Still disabled. Correctly so.** None of the three required gates are met: (1) the current queue is not yet proven to *stay* current across repeated sessions -- one snapshot is not evidence of that; (2) realistic analyst-paced throughput for the full queue is 1.5-2 hours, not 15-30 minutes, so "realistic current arrival volume" has not been demonstrated as absorbable at true human pace; (3) trust semantics have an open, documented defect (Issue 1) that recurring automated intake would only amplify by adding more Publication-only volume through the same conflated approval path.

## Smoke-test artifact disposition

`assessment-20260821072758-6106-smoke-td-012-berry-scope-20260821-072758` was independently re-verified this session: `reviewer: "cursor-cloud-smoke"`, title literally "Smoke TD-012...", rationale self-describes as "Live smoke of optional stored market_ids." Unambiguous. The safest correction is a status transition to the schema's own defined `"withdrawn"` value (`schemas/assessment.schema.json` enum: `active`/`superseded`/`withdrawn`) -- non-destructive, auditable, reversible. This record exists only in production runtime data (not git-tracked; created directly by a prior smoke-test run, bypassing the normal data pipeline entirely), so the fix is a direct runtime field edit rather than a PR. **That edit was attempted and blocked by the session's own permission classifier** (direct production data mutation). Not worked around. Left for the user to authorize explicitly; the finding and the exact safe fix are fully specified above and ready to apply on approval.

## Production / frontend verification

- **PR #215 (stakeholder shell):** confirmed present on production via git ancestry (`f7ad3ed` is an ancestor of deployed HEAD) and via rendered HTML (real `/entities/company/company-driscolls` response contains `sh-page`/`sh-btn`/`sh-header` classes).
- **PR #220 (Global Week Intelligence V1):** merged to canonical (`11cd041`) but **not yet deployed to production** (production remains at `ffd6837`, this mission's own prior deploy). Not altered, per instruction to verify only.
- **Competitor Pulse:** confirmed healthy on production -- live authenticated request to `/pulse/company/company-driscolls?window=7d` returned HTTP 200 with 5 real qualifying results in ~4.9s.
