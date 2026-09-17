# Publication review UI data contract

This contract supports a later UI without authorizing UI implementation in this checkpoint.

## Queue projection

The queue response is body-free and contains:

- draft ID, title, source name and source ID;
- publication/capture dates;
- review state, version, and updated timestamp;
- content class and readable-content flag;
- normalized acquisition outcome and retry/manual-action flags;
- blocker and warning codes with counts;
- duplicate state and survivor ID when resolved;
- linked canonical entity IDs and display names;
- operator-safe priority/review-after metadata;
- permitted commands derived by the service.

It never embeds article bodies, transcripts, review comments, raw failure payloads, or credentials.

The queue is a projection of authoritative shared durable review state. It must return the same acknowledged backlog after worker restart, a new checkout, or routing the operator to another application instance. A missing local `inbox/` cannot mean that accepted review work disappeared.

## Review detail

The detail response adds complete provenance, canonical URL, content hashes, acquisition/extractor versions, quality findings, duplicate evidence, immutable event summary, and an authorized content locator or separately hydrated content. It returns `review_version` and `review_content_digest`; every state-changing form must submit both.

The UI displays the authenticated actor supplied by the session. It must not provide an editable reviewer identity field. Warning acknowledgments are explicit and keyed by warning code. A generic confirmation box cannot satisfy typed acknowledgments.

## Actions and error handling

The client uses a unique idempotency key for each intentional command and reuses it only when retrying an uncertain response. On `stale_review`, it reloads current detail and requires fresh inspection. It must not automatically resubmit approval with the new version or digest.

The interface may offer next-item navigation or a bounded review session. It must send one command per item. No “approve all,” selected-row approval, spreadsheet-import approval, or implicit approval on navigation is part of V1.

## Operational counters

Display these as separate measures:

- discovery runs and discovery successes;
- article-body/transcript acquisition outcomes;
- pending, deferred, correction-required, rejected, and approved publication reviews;
- trusted publications by content class;
- pending and approved Atomic Evidence;
- current readable company coverage.

Source Health remains the discovery/acquisition operational surface. Publication Review owns human decision backlog. Collection Status may link both, but a successful discovery or an approved limited-content publication cannot be counted as readable company coverage.

## Static/public projection

Static builders receive a derived projection only from verified visibility commit markers. A build reads one stable committed snapshot/version and must fail closed without replacing prior output if any referenced publication, decision, event, or hash is missing or changes during the build. It contains public-safe publication metadata, approved excerpt/link policy, content limitation label, and resolved public entity links. It excludes draft IDs where unnecessary, bodies designated private, reviewer identity/comments, command receipts, event ledgers, journals, acquisition diagnostics, and Atomic proposals.
