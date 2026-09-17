# Missing enforcement

The audit found no evidence of an alternate automatic publication path in the
review boundary. The following protections are not present or are not proven
by executable tests and must remain explicit future work:

- publication-level optimistic concurrency / expected draft version;
- actor authorization that distinguishes a human reviewer from AI, bot, or
  service identities;
- a complete publication transition table and fail-closed malformed-draft
  handling;
- source/content identity policy for duplicate URLs and equal content;
- cryptographic or version binding for upgraded bodies and replaced
  transcripts;
- atomic durability across structured repository writes and the filesystem
  review-event ledger;
- a static-build consistency protocol for partially written trusted records;
- a job admission gate preventing Evidence generation before publication and
  claim-review prerequisites.

These are blocking where they can change trust state; reason-policy and
same-content/different-URL policy are nonblocking until product policy is
decided. No speculative tests were added for these gaps.
