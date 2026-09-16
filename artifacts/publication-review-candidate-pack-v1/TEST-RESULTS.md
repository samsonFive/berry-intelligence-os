# Test results

## New test file

`tests/test_publication_review_rehearsal_pack_v1.py` — 14 new tests,
proving:

- Exactly 10 rehearsal items exist, covering all 10 required decision types.
- Every item declares synthetic-vs-real provenance with a real citation.
- Every item carries the full required-analysis field set (source,
  discovery/acquisition path, content state, provenance completeness,
  publication-date confidence, body/transcript availability, entity
  association, duplicate risk, warnings, recommended action, and why it
  is not automatic).
- No forbidden content signal (raw HTML, cookies, `Set-Cookie`,
  `Authorization:`, API keys, passwords) appears anywhere in the pack.
- Every synthetic item's `source_url` uses the reserved,
  guaranteed-non-resolving `example.invalid` domain.
- Every synthetic item's actual stored body text (not any representative
  `word_count` metadata) is under 150 words.
- No two items share a URL or content hash.
- The pack's own index file matches its item files exactly.
- **Each rehearsal file's wrapper shape fails Evidence-schema validation
  directly** — proving a tool that pointed `evidence.schema.json` at a
  rehearsal file itself (rather than its nested `record` field) could not
  mistake it for real Evidence.
- **`EvidenceRepository.list()` against this repository's real `data/`
  directory contains none of the 10 rehearsal ids** — a direct, live
  proof that the real repository loader never ingests rehearsal data.
- **`scripts/validate_records.py`'s own folder list is read directly from
  its source and does not include `data/imports`.**
- **`scripts/validate_records.py` was actually run as a subprocess with
  the rehearsal pack committed, and still reports success** — an
  end-to-end proof, not an inference.
- No canonical data directory changed.

## Command 1 — new test file only

```
../berry-intelligence-os/.venv/Scripts/python.exe -m pytest tests/test_publication_review_rehearsal_pack_v1.py -q
```

Result: **14 passed**, 0 failed.

## Command 2 — full acquisition / publication-draft / review / transcript sweep

```
../berry-intelligence-os/.venv/Scripts/python.exe -m pytest \
  tests/test_article_acquisition.py \
  tests/test_article_acquisition_outcomes.py \
  tests/test_article_refresh.py \
  tests/test_media_discovery.py \
  tests/test_media_orchestration.py \
  tests/test_media_transcription.py \
  tests/test_media_transcription_orchestration.py \
  tests/test_transcript_evidence_extraction.py \
  tests/test_collection_runner.py \
  tests/test_run_collection_cli.py \
  tests/test_youtube_media_acquisition.py \
  tests/test_source_reacquisition.py \
  tests/test_rich_source_acquisition.py \
  tests/test_publication_enrichment.py \
  tests/test_publication_review_source_fidelity.py \
  tests/test_publication_transcript_readiness.py \
  tests/test_review_capacity.py \
  tests/test_review_events.py \
  tests/test_review_operations.py \
  tests/test_review_publish_duplicate.py \
  tests/test_review_publish_portability.py \
  tests/test_review_scripts.py \
  tests/test_review_session.py \
  tests/test_review_workbench.py \
  tests/test_analyst_queue.py \
  tests/test_publication_review_rehearsal_pack_v1.py \
  -q
```

Result: **297 passed**, 0 failed (see full output: `focused-tests.txt`).

## Command 3 — record validation

```
../berry-intelligence-os/.venv/Scripts/python.exe scripts/validate_records.py
```

Result: `All validated records passed.` — run **with the rehearsal pack
already committed to the worktree**, directly confirming the noncanonical
`data/imports/publication-review-rehearsal-2026-09-16/` directory is never
scanned.

## Full suite

Not run, per this mission's explicit scope (focused tests only).

## Test count summary

| Category | Command | Passed | Failed |
|---|---|---:|---:|
| New rehearsal-pack safety tests | Command 1 | 14 | 0 |
| Full acquisition/publication-draft/review/transcript sweep | Command 2 | 297 | 0 |
| Record validation | Command 3 | all validated records passed | — |
