from datetime import datetime, timezone
import json

from app.services.pipeline_health import build_pipeline_health


def test_pipeline_health_reports_contract_and_manual_pipelines(tmp_path):
    config = tmp_path / "pipelines.json"
    config.write_text(json.dumps({"pipelines": [
        {"id": "article_spoken_media", "enabled": True, "scheduled": False, "schedule_entrypoint": True, "cadence_seconds": 60, "state": "operations/runs", "runner": "runner"},
        {"id": "trade", "enabled": False, "scheduled": False, "cadence_seconds": None, "state": "operations/trade/state.json", "runner": "trade"},
    ]}))
    runs = tmp_path / "inbox/operations/runs"
    runs.mkdir(parents=True)
    (runs / "run.json").write_text(json.dumps({
        "started_at": "2026-08-21T00:00:00+00:00", "completed_at": "2026-08-21T00:00:05+00:00",
        "sources": [{"status": "ok"}], "counts": {"items_new": 2, "publication_drafts_created": 1},
    }))
    report = build_pipeline_health(data_dir=tmp_path / "data", inbox_dir=tmp_path / "inbox", config_path=config, now=datetime(2026, 8, 21, tzinfo=timezone.utc))
    media, trade = report["pipelines"]
    assert media["scheduled"] is False and media["schedule_entrypoint"] is True
    assert media["last_success"] and media["items_discovered"] == 2 and media["duration_seconds"] == 5
    assert media["next_due"] == "2026-08-21T00:01:05+00:00"
    assert trade["scheduled"] is False and trade["last_attempt"] is None


def test_partial_scheduler_outcome_advances_last_success_and_next_due(tmp_path):
    config = tmp_path / "pipelines.json"
    config.write_text(json.dumps({"pipelines": [{
        "id": "article_news", "enabled": True, "scheduled": True,
        "cadence_seconds": 60, "state": "operations/runs", "runner": "runner",
    }]}))
    runs = tmp_path / "inbox/operations/pipelines/article_news/runs"
    runs.mkdir(parents=True)
    (runs / "run.json").write_text(json.dumps({
        "started_at": "2026-08-21T00:00:00+00:00",
        "completed_at": "2026-08-21T00:00:05+00:00",
        "outcome": "PARTIAL", "failure_count": 1,
        "failure_sample": ["one source blocked"], "drafts_created": 2,
    }))
    report = build_pipeline_health(
        data_dir=tmp_path / "data", inbox_dir=tmp_path / "inbox", config_path=config,
        now=datetime(2026, 8, 21, tzinfo=timezone.utc),
    )["pipelines"][0]
    assert report["outcome"] == "PARTIAL"
    assert report["last_success"] == "2026-08-21T00:00:05+00:00"
    assert report["last_full_success"] is None
    assert report["next_due"] == "2026-08-21T00:01:05+00:00"
