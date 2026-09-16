# Publication Review and Promotion Contract V1

Status: implementation-ready design. Normative words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are intentional.

## Purpose and trust pipeline

The authoritative pipeline is:

`discovery → acquisition/transcription → publication draft → mandatory human publication review → trusted publication → AI Atomic-Evidence proposals → mandatory human Atomic-Evidence review`

Publication approval establishes that a source publication is authentic enough, relevant enough, and sufficiently understood to retain as a trusted publication. It does not approve any atomic factual proposition.

## Compatibility storage profile

V1 MUST use the existing Evidence schema and repository as a compatibility store; it MUST NOT introduce a competing canonical publication store without a separate migration decision. A trusted publication is the following strict profile:

- `record_type: evidence`
- `evidence_role: publication_artifact`
- `status: published`
- `review_state: published`
- `fact_ids: []` at publication approval
- `relationship_ids: []` for anything created by the approval command
- existing canonical entity IDs may be linked; approval MUST NOT create an Entity
- source/acquisition/transcript/article provenance copied from the reviewed draft
- `publication_review` snapshot containing actor ID, decision timestamp, reason code, reviewed content digest, command ID, and resulting state version

The compatibility location does not make the publication Atomic Evidence. Downstream code MUST use `evidence_role` and the trust projection, never `record_type` alone.

## Implementation-blocking prerequisites

No production mutation path may implement this contract until all of the following are enforced and proven together:

1. review drafts, states, versions, decisions, receipts, and recovery metadata use authoritative shared durable storage; a gitignored worktree-local `inbox/` is not sufficient production state;
2. the actor is an authenticated, authorized human identity rather than form text or an AI/service identity;
3. every mutation uses expected-version or equivalent optimistic concurrency;
4. an immutable content/provenance digest binds the reviewed draft, acquisition/transcript provenance, decision, and resulting publication;
5. retries are idempotent across response loss, duplicate clicks, and process restart;
6. publication, decision, and audit writes are atomic in one durable transaction or recoverably staged behind one commit marker;
7. dynamic and static readers see the prior complete state or the new complete state, never staged or partial records.

Failure to satisfy any item blocks production promotion. These are acceptance gates, not future hardening.

## Identity

- `publication_id` defaults to the draft’s deterministic ID.
- `source_draft_id` is immutable.
- `publication_identity_key` is derived from normalized canonical URL where available; otherwise exact normalized title + source ID + publication date. No fuzzy identity.
- `review_content_digest` is SHA-256 over a canonical serialization of every review-relevant field: title, source identity and URL, publication/capture dates, summary, body/transcript hashes, content class, acquisition outcome, entity links, warnings, and source provenance.
- Any edit to a review-relevant field increments `review_version` and changes the digest.

## Eligibility result

Eligibility is a pure operation returning one of `eligible`, `eligible_with_warnings`, or `blocked`, with typed blockers and warnings. It never mutates state.

Required for every approvable draft:

- safe ID; `evidence_role=publication_artifact`; draft is in `pending_review`;
- resolvable Source ID, source name/type, source URL or a typed structured-source locator;
- title, captured date, submitted-by/provenance, discovery/acquisition version where applicable;
- content class and quality classification;
- no unresolved deterministic duplicate or identity ambiguity;
- valid schema and resolvable existing entity links;
- current `review_version` and `review_content_digest`;
- no retryable acquisition attempt still pending.

### Content matrix

| Draft content | Result | Approval conditions |
|---|---|---|
| Full readable article | Eligible | Reviewer confirms body inspected; stored body/content hash must equal reviewed digest. |
| Partial readable article | Eligible with warnings | Partial warning acknowledged; no summary may imply unseen text. |
| Full transcript | Eligible | Transcript provenance, language, acquisition method and content hash present; reviewer confirms transcript inspected. |
| Structured registry | Eligible | Typed structured fields and authoritative locator present; absence of prose body is not a defect. |
| Generic metadata-only/thin description | Recommended default: eligible with warnings only as a limited-content publication | Explicit `limited_content` approval basis and warning acknowledgment; excluded from current-readable coverage and Atomic extraction until upgraded. This remains a product policy choice recorded in `DECISION-LOG.md`. |
| Navigation-only shell, cookie/consent page, bot wall, access denied, empty page | Blocked | May be rejected, deferred for manual acquisition, or marked correction-required. Never approvable as readable content. |
| Retryable HTTP/network/parser failure | Blocked | Defer and retry; do not turn a transient failure into permanent metadata-only trust. |
| Unsupported source | Blocked | Manual acquisition or explicit future adapter support required. |
| Malformed or missing provenance | Blocked | Correction required. |
| Deterministic duplicate | Blocked | Resolve as `superseded_duplicate` with survivor ID; no second publication. |
| Ambiguous possible duplicate | Blocked | Human identity resolution required. |

Mandatory warnings include partial content, historical or unknown publication date, low authority, unverified identity suggestions, AI-generated enrichment, thin content, unresolved optional attribution, and body/transcript upgrade availability. Warnings never silently become approval.

## Approval invariants

An approval command MUST:

1. be initiated by one authenticated human actor with publication-review permission;
2. target exactly one draft;
3. include a bounded idempotency key, expected review version and reviewed content digest;
4. re-read the draft, Source, acquisition outcome, duplicate candidates and trusted-publication identity inside the service boundary;
5. fail on stale version/digest, ambiguity, hard blocker, or reused idempotency key with different parameters;
6. create at most one trusted publication and one publication decision;
7. create no Fact, Relationship, Atomic Evidence, Signal or Assessment;
8. create no canonical Entity; only preserve resolvable existing IDs;
9. append auditable intent/completion events and preserve the source draft in a private archive;
10. return the same result on an identical retry.
11. publish one durable commit marker only after the publication, decision, audit event, and immutable bindings are complete and mutually verified;
12. keep all pre-commit staged records invisible to trusted queries, extraction jobs, reports, Today, and static builders.

Acquisition success, AI enrichment, queue rank, spreadsheet selection, session navigation, or batch membership MUST NOT imply approval.

## Downstream Atomic Evidence

A trusted publication MAY become input to qualified extraction. Extraction creates private, untrusted `atomic_evidence` proposals only. Each proposal requires its own human Atomic-Evidence decision. Publication approval MUST NOT call the Atomic approval service and MUST NOT populate `fact_ids`.

## Static and reporting behavior

- Drafts, decision events, transaction journals, reviewer comments, full private bodies and Atomic proposals remain private.
- A completed trusted publication may enter the published/static projection only after the promotion transaction is complete.
- Recommended default is public metadata plus an approved excerpt/link; full body redistribution requires a separate legal/product decision.
- Limited-content publications must be labeled and excluded from readable/current-coverage counts.
- Report evidence and Today must use the trust/content projection, not `status=published` alone.

## Authorization and scope

V1 permits sequential single-item decisions by one reviewer. It has no bulk approval endpoint or command. Bulk dismiss remains a non-trust triage action. A review session may contain many items, but each approval is an independently authorized, versioned command.
