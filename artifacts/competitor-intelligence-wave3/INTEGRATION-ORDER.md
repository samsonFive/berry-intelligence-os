# Integration order

1. Created an isolated worktree and branch `integration/competitor-intelligence-wave3` at exact R1 base `0b0c6fc65395261afe0c9653640bafcd5a20b394`.
2. Verified the local and remote source commits and inspected their parents, paths, and diffs.
3. Applied Luna's complete gate range in source order: `e08dae3…`, then requested head `20c7f2…`. Quick mode passed with no mutation.
4. Applied Claude's exact `02bd03f…` acquisition diagnostic checkpoint. Focused acquisition tests and the redacted audit review confirmed the pipeline boundary and no automatic publication.
5. Applied Grok's complete Slice 1 range in source order: `558574d…`, then requested head `e9801db…`. The earlier prototype branch was not integrated.
6. Ran the post-Grok quick/full gates, focused suites, record validation, full suite, static build, and browser matrix.
7. Browser verification found one focus-restoration defect caused by server navigation discarding the opener DOM node. Commit `25fa04a…` stores the exact opener position and item ID in session storage, restores it on close, and falls back safely for direct reader links.
8. Re-ran the focused Product Slice test, final quick gate, complete full suite, final static build, and full browser matrix.

No collection, publication approval, Evidence creation, trust mutation, deployment, canonical merge, or force push occurred.
