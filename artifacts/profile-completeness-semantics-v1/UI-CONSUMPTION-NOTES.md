# UI-consumption notes — Refine Profile Completeness Semantics V1

No UI was built or modified by this mission. These notes exist so a future
UI-adoption mission does not have to re-derive the completeness contract
from source. Read `docs/v2/PROFILE-COMPLETENESS-SEMANTICS-V1.md` first for
the full field-by-field contract; this file is the short, action-oriented
version.

## The one rule that matters most

**Only `completeness.record_integrity.status != "structurally_valid"`
(equivalently: any `actionable_gaps` entry with
`blocks_stakeholder_display: true`) means "do not render this profile
normally."** Everything else — an Unknown/Unassigned berry, an unassigned
priority, a provisional identity, no configured source, zero current
coverage — is a real, honestly-reported state that must still render, just
distinctly labeled.

## Suggested section-by-section rendering

| Section | Field | Suggested treatment |
|---|---|---|
| Header/badge | `completeness.ui_flags.profile_structurally_valid` | Red "data issue" badge only when `false` — should almost never fire on real data (33/33 valid as of this audit). |
| Classification | `completeness.classification_coverage.berry_positions[berry].display` | Render each berry's own label independently (`Tier 1`/`Unknown/Unassigned`/`Not Applicable`/etc.) — never a single rolled-up "classification: X%" badge. |
| Classification | `completeness.classification_coverage.has_unassigned` / `ui_flags.classification_incomplete_or_unassigned` | A neutral "some classification pending" chip, not a warning/error color. |
| Identity | `completeness.identity_verification.state` / `ui_flags.identity_provisional` | `active_verified` → no badge. `provisional`/`pending_duplicate_review` → an informational "identity pending verification" chip (not an error state). `invalid_canonical_reference` should not reach the UI at all in practice, since it also fails `record_integrity`. |
| Relationships | `completeness.relationship_knowledge.*_known` | Simple "not yet recorded" empty-state text per relationship type, not a warning. |
| Monitoring | `completeness.monitoring_maturity.state` / `ui_flags.monitoring_not_configured` | "Not yet monitored" / "configured, first run pending" / "active" — three calm states, not pass/fail. |
| Coverage | `completeness.current_intelligence_coverage.state` / `ui_flags.coverage_unavailable` | "No current coverage" is informational, not an error — especially common (33/33 in this audit) and expected for less-active competitors. |
| Action list | `completeness.actionable_gaps` | A per-profile "what's open" list, grouped by `category`/`severity`, each with `why_it_matters`/`recommended_next_action`/`owning_workflow` ready to display verbatim. Sort blocking first, then attention, then informational. |
| Roster dashboard | `profile_roster_summary(profiles)` | Render every field as its own labeled tile — never compute or display a single "X% complete" number from this data. |

## Things to avoid

- Do not re-derive any `ui_flags` boolean from raw fields independently —
  compute it once here, consume it everywhere.
- Do not color an Unknown/Unassigned, provisional, or monitoring-gap state
  the same red/error color as a `record_integrity` failure — that
  recreates exactly the conflation this mission fixed.
- Do not sort or rank competitors by any completeness field — there is no
  score, on purpose.
- Do not build the UI/route itself as part of continuing from this
  checkpoint without first re-reading
  `docs/v2/PROFILE-COMPLETENESS-SEMANTICS-V1.md` §6.
