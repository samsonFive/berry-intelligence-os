# Test-runner handoff — article acquisition outcomes V1

Branch: `fix/article-acquisition-failures-v1`
Base: `bd96fca1231dc97ae4ec3fc316743b0a3f2e8427`

Run from `C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-article-acquisition-failures-v1` with the sibling environment at `../berry-intelligence-os/.venv/Scripts/python.exe`.

Focused validation:

```powershell
$python = '..\berry-intelligence-os\.venv\Scripts\python.exe'
& $python -m pytest tests/test_article_acquisition.py tests/test_article_acquisition_outcomes.py tests/test_article_refresh.py tests/test_collection_runner.py tests/test_monitor_workspace.py tests/test_source_freshness.py tests/test_source_reacquisition.py -q
& $python -m pytest tests/test_company_news_coverage.py tests/test_intelligence_front_page_v1.py tests/test_review_publish_duplicate.py tests/test_review_publish_portability.py -q
& $python scripts/validate_records.py
& $python scripts/audit_source_execution.py --inbox-dir inbox --output artifacts/astra-repair/acquisition-outcome-audit.json
& $python scripts/audit_competitor_source_coverage.py --inbox-dir inbox --as-of 2026-09-15 --output artifacts/astra-repair/competitor-source-coverage.json
```

Expected focused results are recorded in `artifacts/astra-repair/acquisition-outcome-tests.txt` and `downstream-honesty-tests.txt`. The five-source canary has already run; do not repeat it during routine test verification. The ignored worktree `inbox/` contains its exact private state and one unapproved BerryWorld draft. Full suite was not run.
