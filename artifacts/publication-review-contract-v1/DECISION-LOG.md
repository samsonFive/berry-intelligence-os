# Publication Review Contract V1 decision log

## Decided

| Question | Decision | Reason |
|---|---|---|
| Does publication approval create trusted Evidence claims? | No. It creates only a trusted `publication_artifact` compatibility record. | Source trust and proposition trust require separate human decisions. |
| May approval create or update Entity, Fact, Relationship, Signal, Assessment, or Atomic Evidence records? | No. | Keeps the publication gate narrow, auditable, and reversible. |
| Is a second canonical Publication schema required for V1? | No. Use a strict profile in the existing Evidence schema and repository. | Avoids competing stores and a migration before the command boundary is safe. |
| How is reviewer identity supplied? | Immutable authenticated actor ID with publication-review permission. | Free-text reviewer names are not an authorization boundary. |
| What prevents stale approval? | Expected review version plus digest of every review-relevant field. | A reviewer must approve exactly what was inspected. |
| What prevents duplicate effects? | Per-command idempotency, deterministic publication identity, and per-draft locking. | HTTP retries and concurrent reviewers must converge. |
| Are human decision events mutable? | Completed decisions are append-only. Corrections create a new event/cycle. | Preserves an honest audit trail. |
| Is bulk approval allowed? | No. | Each trust decision requires an independently versioned human action. |
| May one operator approve multiple items? | Yes, sequentially. Each item requires its own inspected digest, idempotency key, and command. | Supports practical queue work without creating a batch trust boundary. |
| Is bulk dismiss affected? | No; it remains non-trust triage. | Dismissal does not publish or reject. |
| Does approval require body inspection? | Yes for readable articles and transcripts. Structured registry approval requires inspection of the typed source fields. A product-authorized limited-content record requires explicit inspection and acknowledgment of what is missing. | Approval must identify the material actually reviewed. |
| How are duplicates handled? | Exact deterministic duplicates become `superseded_duplicate` and point to one survivor. Ambiguous similarity blocks approval for human identity resolution. | Prevents duplicate trust without allowing fuzzy automatic merges. |
| Can a later body/transcript replace reviewed content silently? | No. It creates a new content revision and requires re-review. | Coverage and summaries must reflect inspected content. |
| Does Source Health own publication semantics? | No. | Collection health, review throughput, and usable coverage are distinct. |

## Product decisions still required

1. **Generic metadata-only publications.** Recommended: allow only as explicitly labeled `limited_content`, with a typed warning acknowledgment; exclude them from readable/current coverage and Atomic extraction. A stricter product choice may block them entirely.
2. **Public body policy.** Recommended: publish metadata, a bounded approved excerpt, and source link. Full body redistribution needs source-specific legal/product authorization.
3. **Post-approval withdrawal and correction authority.** Define roles, public projection behavior, and downstream invalidation before exposing a reversal command.
4. **Retention.** Set retention periods for private drafts, bodies, journals, command receipts, and review events while preserving required provenance.
5. **Actor directory and permissions.** Name the identity provider and permission claim that replaces free-text reviewer input.
6. **AI enrichment visibility.** Decide which model-generated fields may be visible to reviewers and which can enter public metadata after publication approval.

None of these open decisions permits the current publication command to create trusted claims or canonical graph records.
