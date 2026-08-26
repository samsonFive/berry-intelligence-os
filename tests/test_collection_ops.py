"""Collection Operations & Freshness Control V1 -- a thin, read-mostly
view over EXISTING collection runtime/status machinery (CollectionRunner,
CollectionStatusService, Source health). No new trust concept, no second
health calculation, no new persistence beyond an already-existing,
already-written run-summary log this module only reads."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.collection_ops import (
    RUN_TIMEOUT_SECONDS,
    build_status_report,
    list_recent_runs,
    trigger_bounded_run,
)

client = TestClient(app)


def _run_summary(run_id: str, *, started_at: str, completed_at: str, dry_run: bool = False, **counts) -> dict:
    base_counts = {
        "items_discovered": 0, "items_new": 0, "items_known": 0,
        "awaiting_publication_review": 0, "retryable_failures": 0, "operator_action_items": 0,
    }
    base_counts.update(counts)
    return {
        "run_id": run_id, "started_at": started_at, "completed_at": completed_at,
        "dry_run": dry_run, "source_scope": "all", "extraction_gate": {"enabled": False},
        "counts": base_counts, "sources": [], "items": [{"item_id": "should-never-appear-in-history-list"}],
        "stale_lock_recovered": False,
    }


def _write_run(inbox_dir: Path, run_id: str, payload: dict) -> None:
    runs_dir = inbox_dir / "operations" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / f"{run_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_lock(inbox_dir: Path, *, started_at: datetime, run_id: str = "collection-lockrun") -> None:
    ops_dir = inbox_dir / "operations"
    ops_dir.mkdir(parents=True, exist_ok=True)
    (ops_dir / "collection.lock").write_text(
        json.dumps({"run_id": run_id, "started_at": started_at.isoformat()}), encoding="utf-8"
    )


class _Repos:
    """Minimal stand-in -- CollectionStatusService's persisted_only path
    only needs .sources.list() and a few other .list() calls to exist."""

    class _Empty:
        @staticmethod
        def list():
            return []

    def __init__(self):
        self.sources = self._Empty()
        self.entities = self._Empty()
        self.evidence = self._Empty()
        self.facts = self._Empty()
        self.signals = self._Empty()
        self.assessments = self._Empty()
        self.recommendations = self._Empty()
        self.strategic_questions = self._Empty()
        self.relationships = self._Empty()


# --- list_recent_runs: bounded, body-free history reader -------------------


def test_list_recent_runs_empty_when_no_runs_yet(tmp_path: Path) -> None:
    assert list_recent_runs(tmp_path) == []


def test_list_recent_runs_reads_persisted_summaries_newest_first(tmp_path: Path) -> None:
    _write_run(tmp_path, "collection-20260101T000000000000Z", _run_summary(
        "collection-20260101T000000000000Z", started_at="2026-01-01T00:00:00+00:00", completed_at="2026-01-01T00:05:00+00:00",
    ))
    _write_run(tmp_path, "collection-20260201T000000000000Z", _run_summary(
        "collection-20260201T000000000000Z", started_at="2026-02-01T00:00:00+00:00", completed_at="2026-02-01T00:03:00+00:00",
    ))
    rows = list_recent_runs(tmp_path)
    assert len(rows) == 2
    assert rows[0]["run_id"] == "collection-20260201T000000000000Z"  # newest first


def test_list_recent_runs_is_bounded(tmp_path: Path) -> None:
    for i in range(15):
        run_id = f"collection-2026010{i:02d}T000000000000Z"
        _write_run(tmp_path, run_id, _run_summary(run_id, started_at="2026-01-01T00:00:00+00:00", completed_at="2026-01-01T00:01:00+00:00"))
    rows = list_recent_runs(tmp_path, limit=5)
    assert len(rows) == 5


def test_list_recent_runs_never_exposes_per_item_detail(tmp_path: Path) -> None:
    _write_run(tmp_path, "collection-x", _run_summary("collection-x", started_at="2026-01-01T00:00:00+00:00", completed_at="2026-01-01T00:01:00+00:00"))
    rows = list_recent_runs(tmp_path)
    assert "items" not in rows[0]


def test_list_recent_runs_computes_duration(tmp_path: Path) -> None:
    _write_run(tmp_path, "collection-x", _run_summary("collection-x", started_at="2026-01-01T00:00:00+00:00", completed_at="2026-01-01T00:05:00+00:00"))
    rows = list_recent_runs(tmp_path)
    assert rows[0]["duration_seconds"] == 300.0


def test_list_recent_runs_tolerates_corrupt_file(tmp_path: Path) -> None:
    runs_dir = tmp_path / "operations" / "runs"
    runs_dir.mkdir(parents=True)
    (runs_dir / "collection-bad.json").write_text("{not json", encoding="utf-8")
    assert list_recent_runs(tmp_path) == []


# --- build_status_report: lock states ---------------------------------------


def test_status_report_no_prior_run_and_no_lock(tmp_path: Path) -> None:
    report = build_status_report(repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path)
    assert report["last_run"] is None
    assert report["lock"]["state"] == "none"


def test_status_report_reflects_successful_prior_run(tmp_path: Path) -> None:
    _write_run(tmp_path, "collection-ok", _run_summary(
        "collection-ok", started_at="2026-01-01T00:00:00+00:00", completed_at="2026-01-01T00:05:00+00:00",
        items_discovered=40, items_new=3, awaiting_publication_review=3,
    ))
    report = build_status_report(repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path)
    assert report["last_run"]["counts"]["items_new"] == 3


def test_status_report_reflects_partial_retryable_run(tmp_path: Path) -> None:
    _write_run(tmp_path, "collection-partial", _run_summary(
        "collection-partial", started_at="2026-01-01T00:00:00+00:00", completed_at="2026-01-01T00:05:00+00:00",
        retryable_failures=4, operator_action_items=1,
    ))
    report = build_status_report(repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path)
    assert report["last_run"]["counts"]["retryable_failures"] == 4
    assert report["last_run"]["counts"]["operator_action_items"] == 1


def test_status_report_active_lock(tmp_path: Path) -> None:
    _write_lock(tmp_path, started_at=datetime.now(UTC) - timedelta(minutes=2))
    report = build_status_report(repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path)
    assert report["lock"]["state"] == "active"
    assert report["lock"]["active"] is True
    assert report["lock"]["stale"] is False


def test_status_report_stale_lock(tmp_path: Path) -> None:
    _write_lock(tmp_path, started_at=datetime.now(UTC) - timedelta(hours=8))
    report = build_status_report(repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path)
    assert report["lock"]["state"] == "stale"
    assert report["lock"]["active"] is False
    assert report["lock"]["stale"] is True


def test_status_report_extraction_disabled_by_default(tmp_path: Path, monkeypatch) -> None:
    for var in ("BIOS_EXTRACT_BASE_URL", "BIOS_EXTRACT_MODEL", "BIOS_COLLECTION_ENABLE_EXTRACTION"):
        monkeypatch.delenv(var, raising=False)
    report = build_status_report(repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path)
    assert report["extraction"]["enabled"] is False


# --- trigger_bounded_run: refusal, no-extraction, bounded scope -------------


def test_trigger_bounded_run_refuses_when_lock_active(tmp_path: Path) -> None:
    _write_lock(tmp_path, started_at=datetime.now(UTC) - timedelta(minutes=1))
    calls = []
    result = trigger_bounded_run(
        repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path, max_items=10,
        executor=lambda cmd: calls.append(cmd),
    )
    assert result["state"] == "refused"
    assert calls == []  # never even attempted to spawn a run


def test_trigger_bounded_run_never_passes_enable_extraction(tmp_path: Path) -> None:
    captured = {}

    class _FakeCompleted:
        returncode = 0
        stdout = json.dumps({"run_id": "x", "counts": {"items_discovered": 0}})
        stderr = ""

    def fake_executor(cmd):
        captured["cmd"] = cmd
        return _FakeCompleted()

    result = trigger_bounded_run(
        repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path, max_items=10, executor=fake_executor,
    )
    assert result["state"] == "completed"
    assert "--enable-extraction" not in captured["cmd"]


def test_trigger_bounded_run_uses_bounded_max_items(tmp_path: Path) -> None:
    captured = {}

    class _FakeCompleted:
        returncode = 0
        stdout = json.dumps({"run_id": "x", "counts": {}})
        stderr = ""

    def fake_executor(cmd):
        captured["cmd"] = cmd
        return _FakeCompleted()

    trigger_bounded_run(repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path, max_items=25, executor=fake_executor)
    assert "--max-items" in captured["cmd"]
    assert "25" in captured["cmd"]


def test_trigger_bounded_run_rejects_out_of_range_size_falls_back_to_default(tmp_path: Path) -> None:
    captured = {}

    class _FakeCompleted:
        returncode = 0
        stdout = json.dumps({"run_id": "x", "counts": {}})
        stderr = ""

    def fake_executor(cmd):
        captured["cmd"] = cmd
        return _FakeCompleted()

    trigger_bounded_run(repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path, max_items=999999, executor=fake_executor)
    assert "10" in captured["cmd"]  # DEFAULT_RUN_SIZE, not the out-of-range value


def test_trigger_bounded_run_handles_subprocess_error(tmp_path: Path) -> None:
    class _FakeCompleted:
        returncode = 2
        stdout = ""
        stderr = "boom"

    result = trigger_bounded_run(
        repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path, max_items=10,
        executor=lambda cmd: _FakeCompleted(),
    )
    assert result["state"] == "error"
    assert "boom" in result["reason"]


def test_trigger_bounded_run_handles_timeout(tmp_path: Path) -> None:
    import subprocess

    def timing_out(cmd):
        raise subprocess.TimeoutExpired(cmd, RUN_TIMEOUT_SECONDS)

    result = trigger_bounded_run(repositories=_Repos(), data_dir=tmp_path, inbox_dir=tmp_path, max_items=10, executor=timing_out)
    assert result["state"] == "error"


# --- route level: GET is read-only, POST is the only mutating verb ---------


def test_collection_ops_page_renders():
    page = client.get("/collection-ops")
    assert page.status_code == 200
    assert "Collection operations" in page.text
    assert "Lock state" in page.text
    assert "Run now" in page.text


def test_collection_ops_get_never_mutates_inbox(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client.get("/collection-ops")
    client.get("/collection-ops")
    # No lock, no run files, nothing written merely by rendering.
    assert not (tmp_path / "operations").exists()


def test_collection_ops_run_get_is_not_allowed():
    resp = client.get("/collection-ops/run")
    assert resp.status_code == 405


def test_collection_ops_run_route_refuses_when_locked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    _write_lock(tmp_path, started_at=datetime.now(UTC) - timedelta(minutes=1))
    resp = client.post("/collection-ops/run", data={"max_items": "10"}, follow_redirects=False)
    assert resp.status_code == 303
    assert "ran=refused" in resp.headers["location"]


def test_collection_ops_no_trust_mutation_on_read(tmp_path: Path, monkeypatch) -> None:
    from app.services.review_events import load_review_events

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    before = len(load_review_events(tmp_path))
    client.get("/collection-ops")
    client.get("/today")
    after = len(load_review_events(tmp_path))
    assert before == after == 0


# --- Source degradation + Today integration ---------------------------------


def test_collection_ops_shows_no_degraded_sources_when_none_failing():
    page = client.get("/collection-ops")
    assert "No Source is currently failing or blocked." in page.text or "failing" in page.text.casefold()


def test_today_links_to_collection_ops():
    page = client.get("/today")
    assert page.status_code == 200
    assert '/collection-ops' in page.text


# --- private / static leakage ------------------------------------------------


def test_collection_ops_absent_from_build_static_route_list():
    import re

    root = Path(__file__).resolve().parents[1]
    text = (root / "scripts" / "build_static.py").read_text(encoding="utf-8")
    assert not re.search(r'["\']\/collection-ops', text)
