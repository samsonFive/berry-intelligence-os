# Project Status

*Maintained by Claude. Updated at the end of each work session that changes project state. Keep short — this is a status check, not a changelog (see `docs/reviews/CURRENT-STATE-AUDIT.md` and `docs/v2/` for detail).*

**Last updated:** 2026-08-14

---

**Current program:**
Intelligence OS V2

**Current stage:**
Phase 1A complete — core intelligence schema foundation added (BL-010 – BL-015)

**Current branch:**
`v2/intelligence-os`

**Next phase:**
Rest of Phase 1 — Domain Pack files (BL-018 – BL-023), not started

**Last completed:**
`BL-010` – `BL-015` (Phase 1A, schema-foundation only). New schemas: `assessment.schema.json`, `recommendation.schema.json`. Extended: `evidence.schema.json` (+`review_state`, `source_tier`, `event_date`, `information_confidence`, all optional), `relationship.schema.json` (+`confidence`, optional), `signal.schema.json` (`evidence_ids` minItems 1→2, richer status enum, id pattern and strength/status enums unioned — see compatibility finding below), `strategic-question.schema.json` (status enum tightened to active/answered/retired). `scripts/validate_records.py` wired to the two new schemas. 11 new tests added (`tests/test_v2_schemas.py`).

**Compatibility finding (flagged, not silently resolved):** implementing BL-014 revealed that `app/main.py`'s live `/signals` route validates against `signal.schema.json` **at runtime** (`get_validator()`) and has its own hard-coded id-generation convention (`signal-` prefix) and form vocabularies (`SIGNAL_STRENGTHS`, `SIGNAL_STATUSES`) — a compatibility surface the original data-only check (0 live signal records) missed. Resolved by making the id pattern and strength/status enums the **union** of the live app's existing values and the blueberry package's proposed values, not a replacement — no `app/main.py` or template code was touched. `evidence_ids` minItems 1→2 was kept exactly as specified (an explicit requirement, not an incidental mismatch); this does change what the live form accepts (single-evidence signals no longer validate), so one existing test's fixture data was updated to submit 2 evidence ids — the form field already supported multiple values, so this required no route/template change, only different test input.

**In progress:**
Nothing. Phase 1A is complete and fully verified.

**Next:**
Owner authorization to continue Phase 1 (BL-018 – BL-023, Domain Pack files) or to proceed directly to Phase 1.5.

**Next implementation action:**
`BL-018` — write `domain-pack.schema.json`. **Not started — pending owner authorization.**

**Blocked by:**
None.

**Known-good V1 reference:**
Tag `v1-blueberry-reference` → commit `432a96bd4efce1991df83b60aa1587154ba19528`. Unaffected by Phase 1A (all work happened on `v2/intelligence-os`, `master` untouched).

**Architecture documents:**
Accepted (`docs/v2/00-README.md` through `10-BACKLOG.md`, 2026-08-13).

**Tests at baseline:**
133 passed, 0 failed (`pytest -q`) — 122 original + 11 new schema tests. `scripts/validate_records.py` passes with zero schema errors across all 1,882 live records plus the two new (currently empty) `data/assessments/`/`data/recommendations/` validation targets. No production data was rewritten; no routes or templates were modified.

**Important decisions — status:**
(IDs match `docs/v2/08-DECISION-LOG.md`)
- D-001 — PostgreSQL as operational store — **ACCEPTED**, subject to the revised (non-dual-write) migration strategy
- D-002 through D-009 — **ACCEPTED**
- D-010 — Claim stays a `fact.classification` value, no separate schema — **ACCEPTED (Option A)**, implemented (no `claim.schema.json` created)
- D-011 — Recommendation and Evidence Priority coexist permanently, distinct triage-vs-decision semantics — **ACCEPTED**, implemented (`recommendation.schema.json`'s `priority` is a flat scalar, structurally distinct from `evidence.priority`'s four-dimension object)

No decisions remain open. No Domain Pack work, PostgreSQL work, or UI/route/template work has begun.
