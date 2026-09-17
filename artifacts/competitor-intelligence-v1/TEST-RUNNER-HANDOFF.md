# Python 3.12 test-runner handoff

Branch: `integration/competitor-intelligence-v1`
Base: `bd96fca1231dc97ae4ec3fc316743b0a3f2e8427`
Integration commit: `ea6bc2ddb3f7eeba4940a695e00166c3e6f6b495`

The focused integration run completed on the available Python 3.13.7 runtime:
96 passed. Record validation passed. A 1,650-page static build passed using an
isolated temporary output after Windows locked the worktree's existing
`generated/entities/variety` directory during replacement.

Use Python 3.12 for the release validation pass:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements.txt
.\.venv312\Scripts\python.exe -m pytest -q tests/test_competitor_registry_v1.py tests/test_competitor_landscape_v1.py tests/test_competitor_intelligence_integration_v1.py tests/test_article_acquisition.py tests/test_article_acquisition_outcomes.py tests/test_article_refresh.py tests/test_monitor_workspace.py tests/test_company_news_coverage.py
.\.venv312\Scripts\python.exe scripts/validate_records.py
.\.venv312\Scripts\python.exe scripts/build_static.py
```

Then run the full suite without collection or live model calls:

```powershell
.\.venv312\Scripts\python.exe -m pytest -q
```

Acceptance checks:

- canonical roster and default landscape remain 33/33 with zero missing rows;
- no `pending-competitor-*` IDs appear in production route output;
- Ozblu and UC Davis retain `brand` and `breeding_program` entity types;
- California Giant exposes all simultaneous monitoring gaps;
- Source Health separates discovery success from body readability;
- the three imported relationship assertions remain pending review;
- no private/inbox content appears in static output.

Do not run collection as part of this validation.
