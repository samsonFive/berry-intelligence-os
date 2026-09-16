# Test results

## New focused tests added

`tests/test_article_acquisition.py` — 8 → 11 tests (+3):
- `test_cookie_consent_gate_is_an_interstitial_failure_not_a_readable_body`
- `test_headline_only_press_template_with_no_body_element_is_empty_body`
  (regression fixture for the live Oishii Press Feed pattern)
- `test_cms_bound_empty_rich_text_article_is_empty_body` (regression
  fixture for the live Fruitist Newsroom pattern)

`tests/test_article_refresh.py` — 14 → 15 tests (+1):
- `test_readable_article_never_reaches_trusted_evidence_or_publication_review_approval`

**Total new tests: 4.**

## Command 1 — new/changed test files only

```
../berry-intelligence-os/.venv/Scripts/python.exe -m pytest \
  tests/test_article_acquisition.py \
  tests/test_article_acquisition_outcomes.py \
  tests/test_article_refresh.py \
  -q
```

Result: **30 passed**, 0 failed.

## Command 2 — full collection / acquisition / publication / transcript / reader-contract sweep

```
../berry-intelligence-os/.venv/Scripts/python.exe -m pytest \
  tests/test_acquisition_state.py \
  tests/test_article_acquisition.py \
  tests/test_article_acquisition_outcomes.py \
  tests/test_article_refresh.py \
  tests/test_collection_ops.py \
  tests/test_collection_runner.py \
  tests/test_collection_status.py \
  tests/test_run_collection_cli.py \
  tests/test_media_discovery.py \
  tests/test_media_discovery_source_expansion.py \
  tests/test_media_orchestration.py \
  tests/test_media_transcription.py \
  tests/test_media_transcription_orchestration.py \
  tests/test_publication_enrichment.py \
  tests/test_publication_review_source_fidelity.py \
  tests/test_publication_transcript_readiness.py \
  tests/test_rich_source_acquisition.py \
  tests/test_source_reacquisition.py \
  tests/test_transcript_evidence_extraction.py \
  tests/test_youtube_media_acquisition.py \
  tests/test_competitor_source_activation_wave1.py \
  tests/test_competitor_source_strategy_v1.py \
  tests/test_astra_news_reader.py \
  -q
```

Result: **336 passed, 1 failed** (see full output: `focused-tests.txt`).

### The 1 failure is pre-existing and unrelated to this mission

`tests/test_collection_status.py::test_live_source_repository_includes_all_onboarded_sources_generically`
asserts a hardcoded `sources_configured == 201`. The real count in the
committed `data/configuration/sources.json` at this branch's exact base
commit (`85a157233674ee5cd3d2e358ea02924d3ac04790`, before this mission
made any change) is already 205 (the 4 new Wave 1 Sources added by the
earlier "Activate competitor sources wave 1" commit, `cdb059e`, pushed
this count from 201 to 205 without that one test's hardcoded assertion
being updated). Verified by stashing every change this mission made and
re-running the same test in isolation against the pristine base commit —
it fails identically, with the identical `205 == 201` message. This
mission did not modify `sources.json`, `test_collection_status.py`, or any
source-count accounting, so this failure is left as-is and reported
honestly rather than silently fixed outside this mission's acquisition/
readability scope.

## Command 3 — record validation

```
../berry-intelligence-os/.venv/Scripts/python.exe scripts/validate_records.py
```

Result: `All validated records passed.`

## Full suite

Not run, per this mission's explicit scope (focused tests only).

## Test count summary

| Category | Command | Passed | Failed |
|---|---|---:|---:|
| New/changed files | Command 1 | 30 | 0 |
| Full acquisition/collection/publication/transcript/reader sweep | Command 2 | 336 | 1 (pre-existing, unrelated) |
| Record validation | Command 3 | all validated records passed | — |
