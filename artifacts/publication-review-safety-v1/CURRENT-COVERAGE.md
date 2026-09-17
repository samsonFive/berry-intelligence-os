# Current coverage

The base already contains accurate coverage for the following current
contracts:

- Human publication review, required reviewer, draft retention on rejection,
  restored-draft read/publish parity, and no promotion before explicit action:
  `test_review_publish_portability.py`.
- Duplicate publication idempotency, conflicting identity protection, and
  repeated publish behavior: `test_review_publish_duplicate.py`.
- Append-only/idempotent review events, compact provenance, retry behavior,
  backup/restore, and no static private-event dependency:
  `test_review_events.py`.
- AI enrichment remains an untrusted suggestion and publisher text is
  preserved: `test_publication_enrichment.py`.
- Atomic Evidence requires parent, locator, and extraction provenance, with
  independent parent/child review lineage: `test_atomic_evidence.py`.
- Trust feedback is a projection/event workflow, does not mutate the input
  record, rejects stale versions, handles idempotency conflicts, and blocks
  missing provenance: `test_trust_feedback.py`.
- Acquisition signatures track superseded material and acquisition outcomes are
  deterministic: `test_acquisition_state.py`,
  `test_article_acquisition*.py`, `test_media_evidence.py`.
- Source-fidelity, review operations, and static draft-leakage contracts are
  covered by their corresponding focused suites.

Validation run: 70 focused tests passed in 27.14s. No new tests were added;
existing assertions accurately represented current hard constraints. The
existing Wave 2 gate is available on this base and was run separately where
compatible.
