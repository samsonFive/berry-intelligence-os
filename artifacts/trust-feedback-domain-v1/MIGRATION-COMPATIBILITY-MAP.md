# Migration and compatibility map

No live records are migrated in V1. The `trust_feedback` bucket is additive within the existing private analyst queue state file. Existing buckets and event workflows remain unchanged.

| Existing state | Feedback interpretation | Migration |
|---|---|---|
| No feedback entry | Derive base state from the record | None |
| Draft / in-review publication | `unreviewed` | None |
| Published `publication_artifact` without approved Facts | `approved_source` | None; preserves the existing evidence trust-tier rule |
| Published `publication_artifact` with approved Facts | `trusted_intelligence` | None |
| Grandfathered/atomic published Evidence | `trusted_intelligence` | None; existing trust-tier compatibility remains authoritative |
| Reading `saved`, `read`, `dismissed`, or `promoted` | Separate reading-queue state | No inferred feedback event |
| Pending triage `dismissed` | Separate publication-triage state | No inferred exclusion |
| Derived-object review | Separate interpretation review | No inferred Evidence feedback |
| Publication review events | Existing governed approval history | Retained; promotion handler continues to own these writes |

Legacy records receive no synthetic event, actor, timestamp, reason, or inferred preference. The first real action creates version 1. Static generation continues to ignore all analyst state and review-event folders.

The roadmap commit `f2021d4b1709629cb20bc81c609a9ea644142950` was read as product guidance and was not cherry-picked because it contains a broader documentation-only roadmap unrelated to this bounded backend branch. Its feedback semantics are captured here and in the executable contract.
