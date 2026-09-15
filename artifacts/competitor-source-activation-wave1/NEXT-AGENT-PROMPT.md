Implement Competitor Source Activation Wave 2 from the completed Wave 1 checkpoint.

Start from the final HEAD of `feature/competitor-source-activation-wave1` in a new worktree and branch. Read `AGENTS.md`, the expansion guide, `artifacts/competitor-source-activation-wave1/ACTIVATION-CHECKPOINT.md`, `activation-reconciliation-matrix.json`, `duplicate-source-audit.json`, `canary-results.json`, and both monitoring audits before editing.

Wave 1 leaves 33 represented, 10 configured, 5 operational, 4 with readable acquisition, and 0 with current usable published coverage. Do not reinterpret a configured, operational, or readable Source as current coverage. Do not import Wave 1's gitignored inbox.

Prioritize a bounded second wave from the research strategy using identity confidence, adapter compatibility, robots policy, and duplicate risk. Recommended initial review set: AgroBerries, Australasian Plant Genetics, Gem-Pack Berries, Perfection Fresh, Plant Sciences, Smart Berries, and SunBelle. Do not activate The Berry Collective until identity ambiguity is resolved. Do not activate Mountain Blue while its explicit Content-Signal restriction remains unresolved. Keep California Giant and UC Davis blocked, Well-Pict inconclusive, and manual-only entities manual.

For every candidate, reconcile against canonical IDs and existing normalized Source URLs, preserve research provenance, and default uncertainty to disabled or operator action required. Add no new adapter unless an existing adapter demonstrably cannot represent a verified permitted source. Use `sources[].linked_competitor_ids` as linkage authority and retain non-company entity support.

Before any canary, run focused deterministic tests. Canary no more than 4–6 Sources, five discoveries per Source, 30 total discoveries, and 20 body attempts. Use `--max-discoveries 5`, run one Source at a time, stage privately, and never approve or publish. Persist honest acquisition outcomes and report every mutation. Update the 33-entry audit and keep configured, operational, readable, and current separate.

Commit durable configuration/tests separately from canary evidence. Do not push, merge, deploy, publish, approve, force-push, modify competitor classifications or identities, or commit live inbox records. Finish clean with a test-runner handoff and a Wave 3 continuation prompt.
