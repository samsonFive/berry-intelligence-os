# Deleted social sources and new outputs

The user approved: “yes if deleted exclude it from new outputs.” Temporary unavailability and restricted access are distinct; neither creates a deletion exclusion.

Explicit deletion records are stored transactionally with private source removal. Receipts retain identifiers, mode and deletion time, not source content. They survive restart, replay and a later unavailable state. Existing explicit deletion audit events and deleted attachment tombstones are read without rewriting old databases. Fixture deletion cannot exclude real evidence.

New-output eligibility resolves the published `social_observation` provenance to the deleted source, including another real provenance mode for the same platform/native ID. Explicit dependencies propagate the hold through Facts, Signals, Assessments, Recommendations and nested briefing citations. Mixed-support records are held rather than silently retaining an unreassessed claim. No canonical trust state, historical file or review decision is changed; no automatic reinstatement.

The shared live RequestCorpus and CLI/static helpers filter published evidence and dependent analytical objects. Existing Landscape contracts/services are reused with a read-only repository projection; direct get retains historical records for review. Relevant cache signatures include deletion receipts. No alternate graph, registry or trusted corpus is created.

Local validation: 228 social/request-corpus tests passed (45.39s, one existing dependency warning), followed by 27 final deletion/briefing checks after the PDF guard (17.33s, one existing dependency warning). Exact committed-head CI remains required. Saved historical reports remain intact for audit. New PDF export refuses reports with deleted-source or transitively excluded citations (HTTP409) and asks the analyst to regenerate; it never silently republishes stale prose or rewrites the historical report. Report citation IDs use the same dependency closure. Provider deletion refresh, rights qualification and independent accuracy remain separate unmet criteria. Collection stays disabled.

Migration: additive `source_deletions` table in the private SQLite acquisition index; no canonical schema migration. Read-only eligibility inspection never creates the database. Preserve before-state backups and deletion receipts when rolling back. Disabling exclusion while generating new outputs would violate the approved policy; stop generation instead. No merge or deployment.


## Explicit imported attachment deletion

A schema-validated imported attachment explicitly marked `deleted` now creates the same durable output hold. A later available replay cannot restore output eligibility. Missing attachments, unavailable/restricted states and failed requests do not create deletion receipts. Fixture deletions remain isolated.

This intake path is non-destructive: stored bytes, prior analyst correction history and existing drafts are retained. Private record projections mark exclusion; all social visual/briefing/export bundles, context hooks, reader/media responses and new handoffs honor it. Previously saved drafts remain historical rather than silently erased. The receipt participates in canonical-dependent output exclusion too. Failed batch validation writes no receipt.

Automatic approval review rejected an earlier proposal to physically clean up stored bytes and redact audit events because that exceeded the user's output-exclusion authorization. That rejected command did not execute. The implemented alternative only adds operational deletion receipts and output holds; no additional destructive side effect was introduced.

Validation of this follow-up:77 store/extraction/cross-provider/deletion tests passed (18.88s);34 route/deletion/presentation checks passed (56.00s, one existing dependency warning). The route check covers failed-batch rollback, available replay, excluded reader/handoff, social briefing/export and fixture isolation. Implementation checkpoint `fb7508cb32081ff55cd6cbc4bcd2a048dace8973` passed all four required checks in [run37897921082](https://github.com/samsonFive/berry-intelligence-os/actions/runs/37897921082):4,187 passed,11 skipped,2 warnings (398.64s). Later documentation-only revisions need their own exact-head checks.
