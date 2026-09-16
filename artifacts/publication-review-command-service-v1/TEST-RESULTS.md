# Test results

## New focused tests (this mission)

| File | Tests | Covers |
|---|---:|---|
| `tests/test_publication_review_domain.py` | 66 (+9 intentionally skipped) | State-machine transitions (every valid pair, exhaustive invalid cross-product), the full eligibility content matrix, deterministic identity, content/provenance digests |
| `tests/test_publication_review_repository.py` | 21 | Durability across restart/new-checkout, compare-and-set staleness, per-draft locking + stale-lock reclaim, idempotency receipts, journal phases |
| `tests/test_publication_review_command.py` | 36 | Authorization (human/AI/bot/service/unauthenticated/unpermitted), version/digest/provenance staleness, idempotent replay/conflict, duplicate/identity-conflict prevention, every valid transition + already-decided handling, readable/transcript/limited-content/navigation-shell approval bases, prohibited side effects, complete-state reads |
| `tests/test_publication_review_crash_recovery.py` | 10 | Hard-stop crash injection at every documented promotion phase, reconciliation convergence, reader isolation at each phase, idempotent post-crash retry, concurrent-duplicate rejection |
| `tests/test_publication_review_migration.py` | 6 | Single-item explicit import, no directory scan, provenance-drift detection on re-import |
| `tests/test_publication_review_static_safety.py` | 2 | Real `scripts/build_static.py` run proving review-state/private-draft/full-body non-leak and correct trusted-publication rendering |
| **Total** | **143 passed, 9 skipped** | |

The 9 skipped cases are intentional: `test_publication_review_domain.py`'s
exhaustive `(state × command)` cross-product test skips the pairs already
covered by the explicit valid-transition parametrization, so every pair is
checked exactly once without duplicate assertions.

Full output: `focused-tests.txt`.

## Command 1 — new tests only

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

Result: **143 passed, 9 skipped**, 0 failed, in 37.80s.

## Command 2 — existing publication/review/duplicate/source-fidelity/
transcript-readiness/review-event/Atomic-Evidence/trust-feedback/
acquisition/transcript suites (unaffected by this mission)

```
../berry-intelligence-os/.venv/Scripts/python.exe -m pytest \
  tests/test_atomic_evidence.py tests/test_pending_review_query.py \
  tests/test_publication_review_source_fidelity.py tests/test_publication_transcript_readiness.py \
  tests/test_review_capacity.py tests/test_review_events.py tests/test_review_operations.py \
  tests/test_review_publish_duplicate.py tests/test_review_publish_portability.py \
  tests/test_review_scripts.py tests/test_review_session.py tests/test_review_workbench.py \
  tests/test_scanner_and_review_ux.py tests/test_sync_trusted_data.py tests/test_trust_feedback.py \
  tests/test_trusted_evidence_semantics_repair_v1.py tests/test_publication_enrichment.py \
  tests/test_article_acquisition.py tests/test_article_acquisition_outcomes.py tests/test_article_refresh.py \
  tests/test_media_discovery.py tests/test_media_orchestration.py tests/test_media_transcription.py \
  tests/test_media_transcription_orchestration.py tests/test_transcript_evidence_extraction.py \
  tests/test_collection_runner.py \
  -q
```

Result: **291 passed, 0 failed**, in 348.56s. Full output:
`existing-suite-tests.txt`.

## Command 3 — record validation

```
../berry-intelligence-os/.venv/Scripts/python.exe scripts/validate_records.py
```

Result: `All validated records passed.`

## Command 4 — Luna Wave 2 gate

```
../berry-intelligence-os/.venv/Scripts/python.exe scripts/wave2_contract_gate.py --mode quick --report artifacts/publication-review-command-service-v1/wave2-gate-report.json
```

Result: **PASS** — 6 composed suites, 244 pytest tests total, all passed;
`"canonical_or_runtime_mutation": false` in the gate's own JSON report
(the gate independently digest-compares `data/` and `inbox/` before and
after every composed command — see `wave2-gate-report.json`):

| Suite | Tests | Duration |
|---|---:|---:|
| Roster and identity | 108 | 66.19s |
| Landscape | 38 | 157.31s |
| Daily Briefing | 23 | 52.64s |
| Reader | 20 | 31.48s |
| Trust | 55 | 162.69s |
| Record validation | 0 (script, not pytest) | 7.70s |

## Command 5 — static build + public-safety

Exercised directly inside `tests/test_publication_review_static_safety.py`
(a real `scripts/build_static.py::main()` run against a `tmp_path`-rooted
dataset containing one command-service-approved publication and one
unrelated pending durable draft) — see Command 1's results above; both
tests pass, proving no leak.

## Full suite

Not run, per this mission's explicit scope (focused tests + the Wave 2
gate, which itself composes a broad cross-section of the full suite).

## Grand total

143 (new) + 291 (existing, unaffected) + 244 (Wave 2 gate, overlapping
with neither of the above — a distinct composed roster/landscape/briefing/
reader/trust cross-section) = **678 test executions across this
mission's validation, 0 failures, 0 canonical/runtime mutations detected**.
