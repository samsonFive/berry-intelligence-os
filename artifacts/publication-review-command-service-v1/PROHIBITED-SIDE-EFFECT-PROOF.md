# Prohibited side-effect proof

The contract's `TRUST-BOUNDARIES.md` is explicit: "Publication approval
creates no Fact, Relationship, Entity, Signal, Assessment, or approved
Atomic Evidence." This mission's `PublicationReviewCommandService` never
imports, constructs, or calls anything from `ReviewPublishService`
(the existing code path proven able to create Facts/Relationships/
Entities in the same transaction), and never writes to any repository
folder except the trusted-publication compatibility record it is
authorized to create.

## Direct proof, not an absence-of-import inference

`tests/test_publication_review_command.py::test_approval_never_calls_review_publish_service`
monkeypatches `ReviewPublishService.publish` itself to raise
`AssertionError` if called, then runs a normal, successful approval and
confirms it still succeeds — proving the command service's approval path
never reaches that method at all, rather than merely observing that the
current source code happens not to import it (which a future edit could
silently break without this test catching it).

## Zero writes under every prohibited folder

`tests/test_publication_review_command.py::test_approval_creates_no_entities_facts_relationships_signals_assessments_recommendations`
runs a full, successful approval against a `tmp_path`-rooted `data/`
directory and then globs every one of:

```
data/entities/**/*.json
data/facts/**/*.json
data/relationships/**/*.json
data/signals/**/*.json
data/assessments/**/*.json
data/recommendations/**/*.json
```

asserting each glob is empty. This is a positive, executed proof (the
approval actually ran and actually succeeded) rather than a static check
that the code merely doesn't mention those repositories.

## No trusted Atomic Evidence

`test_approval_creates_no_atomic_evidence` inspects every record actually
written under `data/evidence/` after approval and asserts none carries
`evidence_role == "atomic_evidence"` — the marker that would make it an
Atomic proposal rather than a publication artifact. Combined with
`_build_trusted_publication_record()`'s own hardcoded
`"evidence_role": "publication_artifact"` (never derived from caller
input), there is no code path by which an approval command could produce
an Atomic Evidence record.

## Exactly one trusted record per approval, ever

`test_only_one_trusted_publication_and_one_decision_event_created` and the
idempotency tests (`test_identical_retry_returns_the_same_result`,
`test_two_simultaneous_identical_commands_produce_one_commit`,
`test_process_crash_after_completion_then_exact_retry_returns_same_result`)
together prove that no sequence of retries, double-clicks, or process
restarts around a single approval ever produces more than one file under
`data/evidence/` or more than one event under `inbox/review_events/`.

## `fact_ids`/`relationship_ids` are always empty, never caller-supplied

`_build_trusted_publication_record()` hardcodes `"fact_ids": []` and
`"relationship_ids": []` on every record it builds — there is no
parameter on `approve_publication()` through which a caller could ever
populate either field. `test_readable_article_approval_creates_a_trusted_publication_with_full_article_basis`
asserts this directly on a real, approved record.

## Canonical entity ids may be linked, never created

`_build_trusted_publication_record()` copies `entity_ids` straight from
the draft's own already-resolved list — it calls no entity-creation
function, and `check_eligibility()`'s `BLOCKER_UNRESOLVED_ENTITY_LINK`
blocks approval outright if any `entity_ids` value does not already
resolve against the caller-supplied `resolvable_entity_ids` set
(`test_unresolved_entity_link_is_blocked`,
`test_resolved_entity_link_does_not_block`). There is no "match-or-create"
step anywhere in this service, unlike `ReviewPublishService.publish()`'s
own entity match-or-create block.

## Canonical/live data is never touched by any test

Every test in this mission's new files constructs its own `tmp_path`
stores. `tests/test_publication_review_crash_recovery.py` and
`tests/test_publication_review_command.py` never reference `DEFAULT_DATA_DIR`
or the real repo-root `inbox/`. `tests/test_publication_review_static_safety.py`
monkeypatches `app.main.DATA_DIR`/`app.main.INBOX_DIR` to `tmp_path`
locations before running `scripts/build_static.py`, following the exact
same pattern `tests/test_build_static.py` already establishes.
