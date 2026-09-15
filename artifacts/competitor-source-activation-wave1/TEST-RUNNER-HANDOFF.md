# Independent test-runner handoff

Validate branch `feature/competitor-source-activation-wave1` from its final clean HEAD. Do not import this worktree's `inbox/`, and do not run collection.

Recommended focused checks:

```powershell
python -m pytest -q tests/test_competitor_source_activation_wave1.py tests/test_competitor_source_strategy_v1.py tests/test_collection_runner.py tests/test_run_collection_cli.py tests/test_article_acquisition_outcomes.py tests/test_article_acquisition.py tests/test_astra_news_reader.py tests/test_competitor_registry_v1.py tests/test_competitor_landscape_v1.py tests/test_competitor_intelligence_integration_v1.py tests/test_build_static.py
python scripts/validate_records.py
python scripts/build_static.py
```

Confirm:

- 12/12 Wave 1 identities resolve.
- Four and only four new Source IDs exist.
- Existing linked Sources are reused; UF's existing blog sitemap carries the added canonical link.
- OZblu and Wish Farms are not collection-eligible.
- UC Davis and California Giant render blocked without a runnable Source.
- `--max-discoveries` caps staging before persistence.
- Oishii's canary outcome remains operational discovery with no readable/current promotion.
- `/competitors` still exposes all 33 entries.
- No `inbox/` file is tracked.

Do not run the full suite; Luna owns that validation.
