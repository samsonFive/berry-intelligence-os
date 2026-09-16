# NEXT-AGENT-PROMPT — after Publication Review read-only UI v1

## Context

Slice 1 shipped a private read-only queue/workspace at `/review-ops/publications` with `decisions_enabled: false`. Contract, prototype, candidate pack, and safety audit refs are recorded in `CHECKPOINT.md`.

## Do next (mutation slice — separate agent/branch)

Only after domain command services and safety gates exist (contract Slices for approve/reject/defer/correction + audit invariants):

1. Introduce a boundary-safe publication decision command service (not `ReviewPublishService.publish()` side effects).
2. Flip UI capability carefully: `decisions_enabled` derived from service `permitted_commands`, never a client flag alone.
3. Wire confirm dialogs with typed warning acknowledgments; reasons for reject/correction; optimistic concurrency on `review_version` + `review_content_digest`.
4. Keep bulk approval forbidden.
5. Retain private/static boundary tests; add mutation integration tests and adversarial cases from `audit/publication-review-safety-v1`.
6. Do not create trusted Atomic Evidence from publication approval.

## Do not

- Cherry-pick prototype JS decision memory into production
- Ship rehearsal fixtures as durable backlog
- Index review queue into Pagefind/static
- Enable decisions before actor auth, concurrency, and provenance binding are enforced server-side
