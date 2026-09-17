# Side-Effect Snapshot

Validator tests use isolated `tmp_path` roots containing only `data/evidence`, `inbox`, and `review_state`. Before/after SHA-256 tree digests were compared for rejected actors and stale review.

Approval created exactly one evidence publication and the associated review state/event journal. The publication asserted `fact_ids: []` and `relationship_ids: []`; no entity, Fact, Relationship, Signal, Assessment, Recommendation, or trusted Atomic Evidence files were created.

Observed mutation result: canonical `data/` and live `inbox/` were not used by validator runs; production data mutation count is 0.
