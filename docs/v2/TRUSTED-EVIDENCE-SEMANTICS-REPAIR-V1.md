# Trusted Evidence Semantics Repair V1

**Status:** Shipped 2026-09-02.

## The defect

The Trust Semantics Audit (`docs/v2/TRUSTED-FRESHNESS-REAL-ACCEPTANCE.md`)
found `/review/{id}/publish` conflates two materially different trust
decisions for ordinary Publications: "this source item is worth
retaining" and "this specific factual claim is approved as trusted."
Validation required only `title`/`summary`/`reviewer`; `facts_input` was
never required and the fast-triage UI never exposed it, so Evidence with
`fact_ids: []` received the same trusted presentation as Evidence that
underwent real factual review.

## Current-state model (precise, as traced)

**A. Publication draft -> Save -> still a draft.** `/review/{id}/save`
edits in place (`title`/`summary`/`why_it_matters`/`tags`/`berry_ids`),
writes the same draft file, no trust change, no review_event. Unchanged
by this mission.

**B. Publication draft -> Promote -> Evidence (repaired).**
`/review/{id}/publish` still creates the Evidence record in the same
transaction (unchanged mechanically) -- but if it publishes with no
analyst-supplied Facts, the created record now carries a `pending_claim`
(candidate statement + origin, computed from the draft before it's
deleted) and the route redirects to the new `/review/{id}/claim` screen
instead of back to the queue. The Evidence record exists and is
`status: "published"`, but `evidence_claim_review.evidence_trust_tier()`
reports it as `APPROVED SOURCE`, not `TRUSTED EVIDENCE`, until a Fact is
approved against it.

**C. Atomic transcript proposal -> Atomic Evidence Review -> Evidence
(unchanged).** Same route, `evidence_role == "atomic_evidence"` branch:
title becomes the proposed statement, `review_outcome.edited_before_
approval` is recorded. This mission does not touch this path at all --
it is the existing model for the distinction being restored elsewhere.

**D. Structured registry filing -> review -> Evidence (repaired).**
Registry filings (`intake_type in {pvr_filing, patent_filing}`) share
Publication's `evidence_role: "publication_artifact"` and previously went
through identical article-summary semantics, with their structured
fields (`cpvo_filing`/`patent_filing`) silently dropped on publish (they
are not in `review_publish.py`'s preserved-optional-fields list). They
now get the same claim-review step as prose Publications, but the
candidate proposition is built deterministically from the structured
fields alone (never free prose) -- see `_structured_registry_proposition()`.

## Target state (implemented)

- **Source decision**: "is this worth retaining as an approved
  Publication?" -- unchanged mechanism, `/review/{id}/publish`.
- **Evidence claim decision**: "which explicit factual claim should enter
  trusted Evidence?" -- new, `/review/{id}/claim` (GET, never mutates) +
  `/review/{id}/claim/approve` + `/review/{id}/claim/reject`.
- Both decisions are independently auditable: two distinct
  `review_events` workflows (`publication_review` vs.
  `evidence_claim_review`), two distinct actions per record.

## Reuse, not a second Evidence model

- **Fact** (`schemas/fact.schema.json`, unmodified schema, no
  `additionalProperties: false`): the approved claim itself. Gains three
  optional, additive fields on write -- `origin`, `proposed_statement`,
  `edited_before_approval` -- the same kind of disclosure
  `atomic_evidence`'s `review_outcome` already makes, now available to
  Publication-derived claims.
- **review_events**: new `workflow="evidence_claim_review"` value,
  `action` in `{"approve_claim", "reject_claim"}`. Same audit trail, same
  `append_review_event()` call, no new persistence mechanism.
- **Evidence**: unchanged schema. `pending_claim` (candidate statement +
  origin) is a transient, additive field cleared the moment a claim is
  approved -- not a second model, a working note on the existing record.
- **No new top-level status value.** `evidence_trust_tier()` is a pure,
  presentation-layer classification (`approved_source` /
  `trusted_evidence` / `reviewed_evidence`) computed from
  `evidence_role` + `fact_ids` -- it never writes anything.

## Legacy Evidence audit (production, read-only, before this mission)

| Population | Count | With `fact_ids` | Without |
|---|---|---|---|
| `evidence_role: None` (legacy, mixed provenance) | 1,268 | 119 (9.4%) | 1,149 (90.6%) |
| `evidence_role: "publication_artifact"` (this session's own work) | 17 | 0 | 17 (100%) |
| `evidence_role: "atomic_evidence"` (ever published) | 0 | -- | -- |

**Finding:** the fact_ids gap is systemic, not specific to Publications --
90.6% of the entire legacy trusted corpus also lacks a linked Fact. This
mission's repair deliberately does **not** reclassify that population.

## Legacy remediation recommendation

**Option A: grandfather with visible provenance class -- applied narrowly.**
`evidence_trust_tier()` only ever returns something other than
`reviewed_evidence` for `evidence_role == "publication_artifact"`
records. The 1,268 legacy `evidence_role: None` records (only 119 of
which have `fact_ids` themselves) are untouched, unconditionally
"REVIEWED EVIDENCE," exactly as before this mission -- **not** because
their provenance is verified, but because retroactively re-auditing
1,268 records with genuinely mixed history is a separate, much larger
decision than this mission's own scope, and the mission's own instruction
is explicit: do not perform bulk trust mutation without explicit operator
authorization. The 17 `publication_artifact` records this session's own
prior missions created are the one population honestly reclassified as
`APPROVED SOURCE` going forward -- a real, disclosed, narrow-scope
consequence of the fix, not a bug. No file was mutated to produce this;
it is presentation logic applied uniformly, forward and backward, to the
one population the defect concerns.

No bulk mutation was performed anywhere in this mission.

## UI

`claim_review.html`: a two-section page. "Source decision (already
recorded)" recaps the already-approved Publication (trust-tier badge,
summary excerpt, link to original source) -- this is not re-decided
here. "Evidence claim decision" shows the machine-prepared candidate
statement in an editable textarea beside classification/confidence
selectors, one Approve button (editing is captured automatically, no
separate "edit" mode), and a "No claim to approve" button that leaves the
record as an approved source only. No badge soup: three labels total
(`LIVE / UNREVIEWED` unchanged from Competitor Pulse, `APPROVED SOURCE`,
`TRUSTED EVIDENCE`), plus the pre-existing unconditional `REVIEWED
EVIDENCE` for everything this mission does not touch.

## Current-first operability preserved

`/pending`'s Dismiss/Duplicate/Defer/Reject actions are completely
unchanged -- a low-value item is still dismissible in one click without
ever entering claim review. Only an explicit Promote decision leads
toward the (also fast) claim-review screen; Promote with Facts already
supplied via the advanced form skips it entirely (already satisfied).

## What this does not do

- Does not touch `evidence_role: None` legacy records' classification.
- Does not batch-approve claims -- one record, one explicit decision.
- Does not weaken `/review/{id}/publish`'s existing validation or
  transaction.
- Does not change the disabled state of recurring Newsroom Intake.
- Does not remove the smoke-test Assessment artifact (separate,
  deliberately deferred decision).
