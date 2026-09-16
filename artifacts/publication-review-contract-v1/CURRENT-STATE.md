# Publication review current state

Base inspected: `integration/competitor-intelligence-wave3` at `c95c05e51b8247a0b22f417a877088c8d7f20e6b`.

## What exists

| Concern | Current implementation | Consequence |
|---|---|---|
| Publication draft storage | Evidence-shaped JSON in gitignored `inbox/evidence/<id>.json`; `record_type=evidence`, `status=draft`, `review_state=in_review`, `evidence_role=publication_artifact`. There is no draft repository abstraction. | Drafts are private, but lifecycle and concurrency are filesystem conventions rather than a formal contract. |
| Trusted publication storage | No separate Publication schema or repository. Approved publications are stored through `EvidenceRepository` in `data/evidence/` with `status=published`, `review_state=published`, `evidence_role=publication_artifact`. | “Publication” is a semantic profile of the Evidence schema, not a distinct persisted object family. |
| Atomic Evidence | Transcript extraction creates private Evidence-shaped proposals with `evidence_role=atomic_evidence`, `status=draft`, `review_state=in_review`, and a parent publication ID. | The separate proposal/review path exists for transcript-derived claims. |
| Publication service | `ReviewPublishService.publish()` receives form-normalized values, validates, creates/updates entities, may create Facts and Relationships, creates the published `publication_artifact`, appends a review event, moves attachments, and deletes the draft. | The current publish command can cross the requested boundary by directly creating Facts and other canonical graph records. |
| Follow-on claim review | A publication approved without Facts receives `pending_claim`; `/review/{id}/claim` may later create a Fact. `evidence_trust_tier()` labels it APPROVED SOURCE until a Fact exists. | Presentation semantics distinguish source approval from a trusted claim, but the object/store name remains Evidence. |
| Human gate | `/review/{id}/publish` requires authoring mode and a nonblank reviewer form value. Missing reviewer blocks the action. | Human action exists, but actor identity is free text rather than an authenticated immutable actor ID. |
| Other decisions | `/save` edits a draft without audit; `/reject` requires reviewer, category, and reason, appends a `publication_review` event, and leaves the rejected draft in inbox. Pending “dismiss” is a separate analyst-queue overlay and is not rejection. | Save/dismiss/defer semantics are not a single publication state machine. |
| Queue vocabulary | Workbench states: `pending`, `rejected`, `approved`; schema values: `draft`, `in_review`, `published`, `rejected`; triage overlay: open/dismissed. | Multiple projections are useful but currently easy to conflate. |
| Audit | `inbox/review_events/<workflow>/<object-hash>/<event-id>.json`; events include actor, before/after state, source/provenance IDs and optional idempotency/version fields. Bodies are intentionally excluded. | The ledger is suitable, but publication routes do not supply idempotency keys or versions. Failed writes may remove a just-created event as compensation, so the ledger is not strictly append-only for attempts. |
| Transaction | JSON Unit of Work compensates creates and updates; attachment moves are manually restored. It is not a database transaction. | Partial failure is handled well for current paths but there is no durable recovery journal or isolation between concurrent reviewers. |
| Duplicate handling | Deterministic publication ID; normalized canonical URL; exact normalized title + source + date; direct-publisher preference. Identical existing publication is idempotent success; conflicting identity is 409 and no overwrite. | Strong foundation, but no command idempotency or stale-screen check. |
| Acquisition | Structured outcome categories, retryability, manual-action flag, content-quality state, source completeness, hashes, extractor/acquisition versions. | Enough information exists to gate publication eligibility honestly. |
| Content classes | `FULL_ARTICLE`, `FULL_TRANSCRIPT`, `STRUCTURED_REGISTRY`, `THIN_DESCRIPTION`, `NO_CONTENT`; current publish permits thin/no-content after operator acceptance. | Metadata-only policy is implicit, not governed by a typed approval basis. |
| Static build | Reads published records from `data/`; never includes inbox drafts, review events, analyst state, or Atomic proposals. Leak tests scan draft IDs/titles. | Approval immediately makes a publication eligible for public/static projection under existing rules. |
| Source Health | Separates discovery, acquisition and readable outcomes. Collection Status separately counts publication-review backlog, trusted publications, Atomic proposals and Atomic review. | Review throughput may be linked from Source Health, but must not redefine collection health. |

## Independent checkpoint findings incorporated

Claude's candidate-pack checkpoint, `research/publication-review-candidate-pack-v1` at `8952566625a543f1850b33fcb033ef0aac5a0839`, confirmed that a fresh isolated worktree has no review backlog because `inbox/` is gitignored and absent. The canonical corpus contained 1,272 Evidence-shaped records: 1,269 published, 3 in review, and zero with readable article bodies. Its 10-item rehearsal pack contains six real and four synthetic cases. The bounded run also reported one item as review-ready without a corresponding persisted draft. That reporting/persistence discrepancy was documented and not repaired.

These findings make local inbox files unsuitable as authoritative production queue state. V1 requires a shared durable production review-state repository. The filesystem inbox remains acceptable only as a local/development adapter or cache whose loss cannot erase accepted work.

Luna's safety checkpoint, `audit/publication-review-safety-v1` at `decb97049a79b3d9e7c4f007f4f5977284d27eec`, confirmed the existing human publication gate, untrusted AI enrichment, separate claim/Atomic review, duplicate protection, rollback compensation, and append-only event convention. It found no automatic publication route or direct publication-to-trusted-Evidence path. It also confirmed missing enforcement for actor authorization, provenance binding, optimistic concurrency, crash consistency, and partial static-read protection.

## Existing route and CLI surface

- `GET /review`, `GET /review/{draft_id}`: queue and detail.
- `POST /review/{draft_id}/publish|save|reject`: publication actions.
- `GET/POST /review/{evidence_id}/claim/*`: later Fact claim decision.
- `POST /review/{draft_id}/approve-atomic`: individual Atomic approval.
- `GET /review-ops` and session routes: bounded navigation only; sessions do not approve.
- `/pending` and `/queues/pending/*`: triage overlays; bulk dismiss never publishes or rejects.
- `scripts/export_for_review.py` and `scripts/apply_review_decisions.py`: spreadsheet-oriented review utilities; they are not a concurrency-safe promotion API.

## Gaps relative to the requested contract

1. Publication approval can currently create Facts, Relationships and Entities in the same transaction.
2. No explicit publication-review version, content digest, command idempotency key, per-draft lock, or durable recovery journal is required.
3. No explicit defer/correction-required publication states exist.
4. Save edits are unaudited and can invalidate what a reviewer previously inspected.
5. Rejection is terminal in practice; no formal correction or supersession mechanism exists after approval.
6. A separate trusted Publication schema does not exist. Compatibility therefore requires a strict `publication_artifact` storage profile inside the current Evidence schema unless a later migration is authorized.
7. Static-public body exposure is not independently governed by the review decision; publication approval and static eligibility currently coincide.
8. Gitignored, worktree-local inbox state is not durable or shared across production workers and cannot be the authoritative review backlog.
9. Exception-time rollback compensation is not crash consistency: process termination can occur between publication, decision, event, draft, and attachment writes before compensation runs.
10. Static readers have no explicit commit-marker protocol proving they see only a complete publication transition.

## Confirmed safety behavior

Focused current-state validation passed: 128 tests across publication, review, duplicate handling, source fidelity, transcript readiness, Atomic Evidence, acquisition outcomes, transcription and static leakage. Record validation also passed. No production or inbox data was changed.
