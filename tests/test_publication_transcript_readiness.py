"""Publication transcript readiness uses synthetic, ignored-style runtime records only."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services import media_transcription, review_workbench
from app.services.media_orchestration import publication_draft_id
from app.services.review_workbench import load_publication_transcript_readiness


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _item(suffix: str) -> dict:
    return {
        "id": f"discovered-source-fixture-{suffix}",
        "source_id": "source-fixture",
        "title": f"Synthetic publication {suffix}",
        "canonical_url": f"https://example.invalid/{suffix}",
        "published_date": "2026-08-15",
        "media_format": "podcast",
    }


def _draft(item: dict) -> dict:
    return {
        "id": publication_draft_id(item),
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "intake_type": "article_or_url",
        "source_type": "industry_podcast",
        "source_name": "Synthetic Publisher",
        "source_url": item["canonical_url"],
        "source_id": item["source_id"],
        "published_date": item["published_date"],
        "captured_date": "2026-08-16",
        "title": item["title"],
        "summary": "Synthetic publication artifact for review.",
        "why_it_matters": "",
        "submitted_by": "collection fixture",
        "evidence_role": "publication_artifact",
        "media_format": item["media_format"],
        "discovered_item_id": item["id"],
        "suggested_competitors": [],
        "suggested_varieties": [],
        "attachments": [],
    }


def _transcript(item: dict, *, tier: str, language: str = "en") -> dict:
    method = "publisher_provided" if tier == "tier_1_publisher_transcript" else "auto_generated"
    if tier == "tier_2_youtube_human_captions":
        method = "human_provided"
    return {
        "id": f"transcript-{item['id']}",
        "record_type": "staged_transcript",
        "transcript_id": f"transcript-{item['id']}",
        "item_id": item["id"],
        "source_id": item["source_id"],
        "parent_evidence_id": None,
        "language": language,
        "provenance": {"method": method, "created_by": "fixture", "created_at": "2026-08-16"},
        "segments": [{"text": "Synthetic transcript segment.", "start_seconds": 0, "end_seconds": 2}],
        "acquisition": {"tier": tier},
    }


def _stage_items(inbox: Path, items: list[dict]) -> None:
    for item in items:
        _write(inbox / "discovered_media" / f"{item['id']}.json", item)


def _run(inbox: Path, items: list[dict]) -> None:
    _write(
        inbox / "operations" / "runs" / "collection-20260816T120000Z.json",
        {
            "run_id": "collection-20260816T120000Z",
            "started_at": "2026-08-16T12:00:00+00:00",
            "completed_at": "2026-08-16T12:05:00+00:00",
            "items": items,
        },
    )


def test_bulk_state_mapping_methods_language_and_fail_closed_runtime(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    tiers = {
        "publisher": "tier_1_publisher_transcript",
        "human": "tier_2_youtube_human_captions",
        "auto": "tier_2_youtube_auto_captions",
        "whisper": "tier_3_local_speech_to_text",
        "method-unknown": "future_tier",
    }
    items = {name: _item(name) for name in [*tiers, "not-attempted", "missing", "retry", "operator", "corrupt"]}
    _stage_items(inbox, list(items.values()))
    for name, tier in tiers.items():
        language = "af" if name == "whisper" else "en"
        _write(
            inbox / "discovered_media" / "_normalized_transcripts" / f"{items[name]['id']}.json",
            _transcript(items[name], tier=tier, language=language),
        )
    corrupt_path = inbox / "discovered_media" / "_normalized_transcripts" / f"{items['corrupt']['id']}.json"
    corrupt_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_path.write_text("{not-json", encoding="utf-8")
    _write(
        inbox / "operations" / "items" / f"{items['retry']['id']}.json",
        {
            "item_id": items["retry"]["id"], "failure_class": "retryable", "retry_count": 2,
            "next_eligible_retry_at": "2026-08-16T13:00:00+00:00",
            "last_attempted_at": "2026-08-16T12:30:00+00:00",
            "last_error": "SECRET cookie path C:/private/cookies plus a raw downloader trace",
        },
    )
    _write(
        inbox / "operations" / "items" / f"{items['operator']['id']}.json",
        {
            "item_id": items["operator"]["id"], "failure_class": "operator", "retry_count": 0,
            "last_attempted_at": "2026-08-16T12:31:00+00:00", "last_error": "private/internal/detail",
        },
    )
    _run(
        inbox,
        [
            {"item_id": items["not-attempted"]["id"], "transcript_status": "missing", "transcription_attempted": False},
            {"item_id": items["retry"]["id"], "transcript_status": "acquisition_failed", "transcription_attempted": True, "failure_class": "retryable"},
            {"item_id": items["operator"]["id"], "transcript_status": "malformed", "transcription_attempted": True, "failure_class": "operator"},
        ],
    )

    calls: list[Path] = []
    real_loader = review_workbench._safe_runtime_objects

    def counted(folder: Path):
        calls.append(folder)
        return real_loader(folder)

    monkeypatch.setattr(review_workbench, "_safe_runtime_objects", counted)
    view = load_publication_transcript_readiness(inbox)
    assert len(calls) == 4

    def state(name: str) -> dict:
        return view[publication_draft_id(items[name])]

    assert state("publisher")["method"] == "Publisher transcript"
    assert state("human")["method"] == "YouTube human captions"
    assert state("auto")["method"] == "YouTube auto captions"
    assert state("whisper")["method"] == "Local Whisper"
    assert state("whisper")["language"] == "af"
    assert state("method-unknown")["method"] == "Unknown method"
    assert state("not-attempted")["state"] == "not_attempted"
    assert state("missing")["state"] == "unknown"
    assert state("retry")["state"] == "retryable_failure"
    assert state("retry")["retry_count"] == 2
    assert state("operator")["state"] == "intervention_required"
    assert state("corrupt")["state"] == "unknown"
    assert "SECRET" not in json.dumps(view)
    assert "C:/private" not in json.dumps(view)


def test_queue_and_detail_render_separate_readiness_without_runtime_side_effects(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    ready, not_attempted, retry = (_item(name) for name in ("ready", "not-attempted", "retry"))
    _stage_items(inbox, [ready, not_attempted, retry])
    for item in (ready, not_attempted, retry):
        main.save_draft(_draft(item))
    _write(
        inbox / "discovered_media" / "_normalized_transcripts" / f"{ready['id']}.json",
        _transcript(ready, tier="tier_3_local_speech_to_text", language="af"),
    )
    _write(
        inbox / "operations" / "items" / f"{retry['id']}.json",
        {
            "item_id": retry["id"], "failure_class": "retryable", "retry_count": 1,
            "last_error": "raw yt-dlp --cookies-from-browser C:/private/path",
        },
    )
    _run(
        inbox,
        [
            {"item_id": not_attempted["id"], "transcript_status": "missing", "transcription_attempted": False},
            {"item_id": retry["id"], "transcript_status": "acquisition_failed", "transcription_attempted": True},
        ],
    )
    generic = {
        "id": "ev-generic-article", "record_type": "evidence", "status": "draft",
        "intake_type": "article_or_url", "source_type": "article", "source_name": "Synthetic Journal",
        "title": "Generic article remains generic", "captured_date": "2026-08-16",
        "summary": "Synthetic article.", "submitted_by": "fixture", "suggested_competitors": [],
        "suggested_varieties": [], "attachments": [],
    }
    main.save_draft(generic)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("review rendering must not acquire or transcribe")

    monkeypatch.setattr(media_transcription, "transcribe_discovered_item", forbidden)
    before = {path.relative_to(inbox): path.read_bytes() for path in inbox.rglob("*") if path.is_file()}
    client = TestClient(app)
    queue = client.get("/review")
    ready_detail = client.get(f"/review/{publication_draft_id(ready)}")
    generic_detail = client.get("/review/ev-generic-article")
    after = {path.relative_to(inbox): path.read_bytes() for path in inbox.rglob("*") if path.is_file()}

    assert queue.status_code == ready_detail.status_code == generic_detail.status_code == 200
    assert "Ready" in queue.text and "Not attempted" in queue.text and "Retryable failure" in queue.text
    assert "Detected language: <strong>af</strong>" in queue.text
    assert "--cookies-from-browser" not in queue.text and "C:/private/path" not in queue.text
    assert "Publication review" in ready_detail.text
    assert "Technical transcript readiness" in ready_detail.text
    assert "Detected language:</strong> af" in ready_detail.text
    assert "verify if unexpected" in ready_detail.text
    assert "Transcript readiness is independent of the publication decision." in ready_detail.text
    assert "Technical transcript readiness" not in generic_detail.text
    assert before == after


def test_publication_approve_and_reject_remain_independent_of_transcript_state(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    not_attempted, ready = (_item(name) for name in ("not-attempted", "ready"))
    _stage_items(inbox, [not_attempted, ready])
    for item in (not_attempted, ready):
        main.save_draft(_draft(item))
    _run(inbox, [{"item_id": not_attempted["id"], "transcript_status": "missing", "transcription_attempted": False}])
    _write(
        inbox / "discovered_media" / "_normalized_transcripts" / f"{ready['id']}.json",
        _transcript(ready, tier="tier_1_publisher_transcript"),
    )
    client = TestClient(app)
    approved = client.post(
        f"/review/{publication_draft_id(not_attempted)}/publish",
        data={
            "title": not_attempted["title"], "source_type": "industry_podcast",
            "source_name": "Synthetic Publisher", "source_url": not_attempted["canonical_url"],
            "published_date": not_attempted["published_date"], "captured_date": "2026-08-16",
            "summary": "Human-approved publication with transcription still pending.", "reviewer": "human reviewer",
        },
        follow_redirects=False,
    )
    rejected = client.post(
        f"/review/{publication_draft_id(ready)}/reject",
        data={"reviewer": "human reviewer", "rejection_reason": "Publication is not relevant."},
        follow_redirects=False,
    )
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    assert approved.status_code == rejected.status_code == 303
    assert repos.evidence.get(publication_draft_id(not_attempted))["status"] == "published"
    assert main.get_draft(publication_draft_id(ready))["status"] == "rejected"
    assert (inbox / "discovered_media" / "_normalized_transcripts" / f"{ready['id']}.json").exists()


def test_atomic_evidence_detail_does_not_receive_publication_readiness(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    atomic = {
        "id": "ev-atomic-fixture", "record_type": "evidence", "status": "draft", "review_state": "in_review",
        "intake_type": "article_or_url", "source_type": "industry_podcast", "source_name": "Synthetic Publisher",
        "title": "Atomic fixture", "summary": "Atomic fixture.", "captured_date": "2026-08-16",
        "submitted_by": "fixture", "evidence_role": "atomic_evidence", "parent_evidence_id": "ev-parent-fixture",
        "artifact_locator": {"start_seconds": 1, "end_seconds": 2}, "transcript_excerpt": "Exact support.",
        "entity_ids": [], "berry_ids": [], "suggested_competitors": [], "suggested_varieties": [], "attachments": [],
        "extraction_provenance": {}, "transcript_provenance": {},
    }
    main.save_draft(atomic)
    response = TestClient(app).get("/review/ev-atomic-fixture")
    assert response.status_code == 200
    assert "Source-grounding record" in response.text
    assert "Technical transcript readiness" not in response.text


def test_static_build_does_not_render_runtime_transcript_metadata(monkeypatch, tmp_path: Path) -> None:
    from scripts import build_static

    data = tmp_path / "data"
    inbox = tmp_path / "inbox"
    output = tmp_path / "generated"
    marker = "runtime-transcript-marker-must-not-leak"
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(build_static, "OUTPUT_DIR", output)
    item = _item("static-runtime")
    _stage_items(inbox, [item])
    transcript = _transcript(item, tier="tier_3_local_speech_to_text", language="af")
    transcript["segments"][0]["text"] = marker
    _write(inbox / "discovered_media" / "_normalized_transcripts" / f"{item['id']}.json", transcript)
    main.save_draft(_draft(item))

    build_static.build()
    assert all(marker not in path.read_text(encoding="utf-8") for path in output.rglob("*.html"))
