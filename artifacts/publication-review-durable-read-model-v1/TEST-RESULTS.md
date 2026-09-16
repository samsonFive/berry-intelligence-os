# Test results

## New focused tests

`tests/test_publication_review_query.py` — **33 passed**, covering every
required scenario from the mission brief:

| Scenario | Test(s) |
|---|---|
| Empty store | `test_empty_store_queue_is_empty`, `test_empty_store_status_summary_is_all_zero`, `test_empty_store_detail_for_unknown_id_is_none` |
| Pending review | `test_pending_review_appears_in_queue_and_detail` |
| Approved / rejected / deferred / correction-requested | `test_approved_state_reflected_with_publication_binding`, `test_rejected_state_reflected`, `test_deferred_state_reflected`, `test_correction_requested_state_reflected` |
| Corrected draft returned to review | `test_corrected_draft_returns_to_pending_review_with_updated_content`, `test_returned_to_review_from_deferred` |
| Superseded duplicate | `test_superseded_duplicate_exposes_supersession_metadata`, `test_non_superseded_draft_has_no_supersession_metadata` |
| Multiple revisions and decision-history ordering | `test_multiple_revisions_preserve_chronological_decision_history_order` |
| Missing or stale referenced state | `test_publication_binding_referencing_a_deleted_evidence_file_is_reported_unverified`, `test_detail_without_an_evidence_reader_reports_verification_as_unknown_not_false` |
| Interrupted transaction visibility | `test_interrupted_transaction_is_visible_but_never_reported_as_approved`, `test_promotion_status_is_empty_for_a_draft_with_no_transaction`, `test_committed_approval_shows_no_pending_transaction` |
| Actor redaction / serialization boundaries | `test_decision_event_serialization_only_exposes_the_whitelisted_fields`, `test_raw_repository_event_has_more_fields_than_the_serialized_view` |
| Stable results across repeated reads | `test_repeated_queue_reads_are_identical`, `test_repeated_detail_reads_are_identical`, `test_pagination_cursor_resumes_deterministically` |
| Byte-identical repository/canonical state before/after all reads | `test_reads_never_mutate_the_durable_repository_or_data_dir` |
| No leakage of full acquired article bodies | `test_queue_item_never_contains_article_paragraphs_or_transcript_segments`, `test_detail_view_never_contains_the_full_article_text`, `test_hydrated_excerpt_is_bounded_and_never_the_full_body`, `test_short_body_excerpt_is_not_marked_truncated`, `test_readonly_ui_compatible_projection_also_never_leaks_full_body` |
| Compatibility with imported legacy review records | `test_imported_legacy_draft_is_readable_and_flagged`, `test_legacy_draft_stops_being_flagged_once_it_has_a_real_decision`, `test_natively_seeded_draft_is_not_flagged_as_legacy_import` |
| Also verified, also approved | `test_approved_publication_binding_can_be_verified_against_evidence_reader` |

Full output: `new-tests.txt`.

## Command 1 — new tests only

```
../berry-intelligence-os/.venv/Scripts/python.exe -m pytest tests/test_publication_review_query.py -q
```

Result: **33 passed**, 0 failed, 7.52s.

## Command 2 — existing publication-review domain/repository/command/crash-recovery/migration/static-safety tests

```
../berry-intelligence-os/.venv/Scripts/python.exe -m pytest \
  tests/test_publication_review_domain.py \
  tests/test_publication_review_repository.py \
  tests/test_publication_review_command.py \
  tests/test_publication_review_crash_recovery.py \
  tests/test_publication_review_migration.py \
  tests/test_publication_review_static_safety.py \
  -q
```

Result: **143 passed, 9 skipped** (the same intentional exhaustive-transition
skips as the prior mission), 0 failed, 29.26s. Unaffected by this
mission's additions. Full output: `existing-publication-review-tests.txt`.

## Command 3 — existing read-only publication-review UI tests

**Could not be run.** `feature/publication-review-readonly-ui-v1` at
`d19ee0a3` is a separate, frozen, unmerged branch; neither
`app/services/publication_review_readonly.py` nor
`tests/test_publication_review_readonly_ui.py` exists in this branch's
working tree (confirmed directly: both paths fail to resolve here), and
this mission's own instructions forbid merging that branch. The file was
inspected via `git show d19ee0a:<path>` only — see `CONTRACT-MAPPING.md`.

## Command 4 — record validation

```
../berry-intelligence-os/.venv/Scripts/python.exe scripts/validate_records.py
```

Result: `All validated records passed.`

## Command 5 — static build / private-leakage checks

```
../berry-intelligence-os/.venv/Scripts/python.exe -m pytest tests/test_build_static.py -q
```

Result: **6 passed**, 0 failed, 25.03s — the existing static-leak suite,
unaffected (this mission adds no route/template/static-build change).
This mission's own leakage proof lives in
`tests/test_publication_review_query.py` directly (see
`PRIVACY-AND-LEAKAGE-PROOF.md`), since no new route was added for the
existing static-build test to exercise.

## Full suite

Not run, per this mission's explicit scope (focused tests only).

## Grand total

33 (new) + 143 (existing publication-review suites, unaffected) + 6
(static-leak suite, unaffected) = **182 test executions, 9 intentional
skips, 0 failures, 0 inherited failures**.
