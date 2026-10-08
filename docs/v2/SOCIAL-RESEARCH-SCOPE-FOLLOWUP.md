# Social research scope follow-up — October 7, 2026

Following the user's functional approval and instruction to continue, tightened the existing opt-in private ResearchScope context provider. No new source requests, credits, paid services, deployment or trusted-data writes.

- Apply the research date window before the twenty-result limit. Use publication date in UTC, excluding undated imports, old posts and future-dated posts. Collection date alone does not demonstrate recent conversation.
- Resolve explicitly attributed purchase markets against supplied canonical geography IDs, names, aliases and ISO country attributes. Apply regional containment through existing stored active `part_of` relationships only.
- Fruit origin, author geography and search market never satisfy purchase-market scope. Query-target geography never establishes a sighting. Unknown or ambiguous mappings return no match; missing mapping configuration never falls back to unfiltered posts.
- Preserve berry/entity scope, English-readable visibility, translated presentation, newest-first ordering, provenance modes and redacted model-packet titles. Links carry the date window back into the workspace.

Caller configuration: `market_context_provider(store, entities=canonical_entities, relationships=canonical_relationships)`. Both canonical collections are read-only inputs; no new hierarchy or registry records. Optional `today` supports reproducible tests. Without geography configuration a geographic request yields an honest empty result. The seam remains opt-in and is not wired automatically into trusted dossiers or model collection.

Regression case covers US versus Mexico, country versus explicitly stored region containment, older/future/undated timestamps, UTC boundary, query-target exclusion, origin/author separation and geography filtering before the result cap. Existing entity-before-cap test remains.

Validation: 107 focused social tests passed in 27.52 seconds, one existing dependency warning. Initial sandbox run could not create its temporary test directory; the rerun used an explicit isolated workspace directory and completed successfully. Required current-head repository checks are recorded in the draft PR/review receipt.

No SQL migration or preview data reprocessing needed. Rollback is the code commit. Existing unresolved items remain: independent human accuracy and native-language review, representative consumer coverage, source-specific rights/deletion refresh, durable reviewed watch profiles, unattended collection approval, automatic downstream assembly and published dependency retraction. This scoped navigation hook does not satisfy those requirements.
