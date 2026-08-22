# Spoken-Word Atomic Evidence Architecture Finding

**Date:** 2026-08-15
**Decision:** Option A — parent/child records within the existing Evidence model.

## Repository finding

The existing model had most of the required lineage already:

- Source identifies the recurring publisher/channel.
- Evidence identifies an individual publication and already carries media/transcript metadata.
- Fact and Relationship accept one or more `evidence_ids`.
- Assessment requires Facts and may also link Evidence directly.
- Existing query services resolve Fact → Evidence and Assessment → Fact → Evidence.

It did not have an Evidence-to-Evidence derivation edge, timestamp/segment provenance, extraction provenance, or a generic rejection action for inbox proposals. Treating the whole episode as the only citation would therefore be too coarse. A separate Media Artifact record type would duplicate the Evidence repository, Source linkage, publication metadata, review state, detail route, static generation, and downstream lineage without adding a distinct lifecycle.

## Selected semantics

- Whole article, podcast episode, video, or conference recording: Evidence with `evidence_role: publication_artifact`.
- Independently reviewable statement extracted from it: Evidence with `evidence_role: atomic_evidence` and `parent_evidence_id`.
- Precise support: `artifact_locator.start_seconds`, optional `end_seconds`, section, and untyped `speaker_label`.
- Extraction audit: `extraction_provenance` records method, actor/system label, and date. It never implies approval.
- Human decision: `review_state`, `reviewed_by`, and `reviewed_at`.

All additions are optional for historical Evidence. Only a record that explicitly declares `atomic_evidence` must provide its parent, locator, and extraction provenance. The real Lucentlands record is truthfully marked as the publication artifact; no production atomic points were invented.

## Review and lineage

Each proposed atomic point is its own ordinary inbox draft. Multiple drafts may share one `parent_evidence_id`. The existing publish service independently approves each draft and now preserves the additive derivation fields. The generic reject action records a reviewer, date, and reason on the rejected inbox proposal without publishing it or changing its parent/siblings.

Once approved, an atomic Evidence ID can be cited by Fact or Relationship exactly like any existing Evidence ID. Assessment continues to cite the resulting Fact, preserving the existing lineage rather than adding a parallel spoken-word chain.

## Scaling consequence

The next dependency is transcript acquisition: extraction cannot retain defensible timestamp/span provenance until reliable transcript/caption material exists. Evidence extraction follows; recurring episode discovery can be automated after the artifact-to-transcript-to-proposal path is proven.
