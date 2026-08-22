from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from app.services.pipeline_scheduler import classify_outcome, run_due_pipelines


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def _config(path: Path) -> Path:
    path.write_text(json.dumps({"pipelines": [
        {
            "id": "article_news",
            "enabled": True,
            "scheduled": True,
            "cadence_seconds": 21600,
            "runner": "scripts/run_collection.py --pipeline-scope article-news --json-summary",
            "state": "operations/runs",
        },
        {
            "id": "trade",
            "enabled": False,
            "scheduled": False,
            "cadence_seconds": None,
            "runner": "scripts/monitor_trade_intelligence.py --json",
            "state": "operations/trade/state.json",
        },
    ]}), encoding="utf-8")
    return path


def test_partial_source_failure_is_useful_cycle_not_total_failure(tmp_path: Path) -> None:
    config = _config(tmp_path / "pipelines.json")
    stdout = json.dumps({
        "counts": {
            "sources_succeeded": 4,
            "sources_failed": 1,
            "publication_drafts_created": 2,
        }
    })
    result = run_due_pipelines(
        data_dir=tmp_path / "data",
        inbox_dir=tmp_path / "inbox",
        config_path=config,
        now=NOW,
        executor=lambda command: subprocess.CompletedProcess(command, 1, stdout=stdout, stderr=""),
    )
    assert result["state"] == "PARTIAL"
    assert result["results"][0]["outcome"] == "PARTIAL"
    assert result["results"][0]["drafts_created"] == 2
    saved = list((tmp_path / "inbox/operations/pipelines/article_news/runs").glob("*.json"))
    assert len(saved) == 1 and json.loads(saved[0].read_text())["failure_count"] == 1


def test_disabled_manual_pipeline_is_never_dispatched(tmp_path: Path) -> None:
    config = _config(tmp_path / "pipelines.json")
    plan = run_due_pipelines(
        data_dir=tmp_path / "data",
        inbox_dir=tmp_path / "inbox",
        config_path=config,
        now=NOW,
        plan_only=True,
    )
    assert plan["due"] == ["article_news"]


def test_failed_when_no_useful_unit_succeeds() -> None:
    outcome, failures = classify_outcome("article_news", {"counts": {"sources_succeeded": 0, "sources_failed": 2}}, 1)
    assert outcome == "FAILED" and failures == 2
