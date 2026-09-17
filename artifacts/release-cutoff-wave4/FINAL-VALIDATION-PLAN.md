# Final exact-head validation plan

The release-manifest commit containing this plan establishes the exact combined candidate. No product or documentation changes may follow validation without restarting the exact-head gate.

Required checks:

1. Focused Publication Review backend, adversarial, read-only UI and static-safety suites.
2. PR #255 Learner, calendar, source-lifecycle and build checks.
3. TD-THREAD-002 story-thread, matcher non-regression, search, landscape and synthesis checks.
4. PVS Slice 2 Landscape/profile/completeness/identity, Today, shell and static checks.
5. Record validation.
6. Full repository suite compared by exact nonpassing node ID with the Wave 4 baseline and explained completed-input changes.
7. Static build and Pagefind, including private/pending review leakage scans.
8. Desktop, tablet and mobile browser smoke coverage for Today, reader, Learn, story threads, Landscape, representative competitor profiles, Source Health and private review surfaces.
9. Before/after protected-data hashes for canonical records, publication state and runtime review state.
10. Independent Luna validation of this exact combined HEAD.
11. Clean worktree and exact local/remote SHA equality.

Any new unexplained failing/error node, private-data leak, protected-data mutation, browser mutation request, or Luna verdict other than PASS blocks merge and deployment.
