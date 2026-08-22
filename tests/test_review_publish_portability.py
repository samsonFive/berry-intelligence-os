"""Portability regression: a restored publication draft must be reviewable and
publishable through the ordinary human review path.

Reproduces the real Lucentlands scenario (a publication draft restored from an
older pilot runtime into `inbox/evidence/`, alongside its discovered-media item
and normalized transcript) and proves the review READ path and the review
PUBLISH path resolve the *same* draft from the *same* location: when the draft
file is present at `inbox/evidence/<id>.json`, it both renders in /review and
publishes; when it is absent, both fail with 404 (no split-brain). The human
publish action remains the only way to promote it -- nothing is auto-approved
and no draft JSON is hand-promoted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.media_orchestration import publication_draft_id
from app.services.review_workbench import load_publication_transcript_readiness


ITEM_ID = "discovered-source-lucentlands-podcast-22e7bd9b03f2ce93"
SOURCE_ID = "source-lucentlands-podcast"


def _item() -> dict:
    return {
        "id": ITEM_ID,
        "record_type": "discovered_media_item",
        "staging_schema_version": 1,
        "source_id": SOURCE_ID,
        "external_id": "lucentlands-ep",
        "dedupe_strategy": "external_id",
        "dedupe_key": "lucentlands-ep",
        "title": "Scaling the Blueberry Industry",
        "description": "Lucentlands episode on scaling the blueberry industry.",
        "canonical_url": "https://anchor.fm/lucentlands/ep",
        "published_date": "2026-07-01",
        "media_format": "podcast",
        "transcript_availability": {"status": "unknown"},
        "possible_evidence_matches": [],
        "first_seen_at": "2026-08-01T10:00:00+00:00",
        "last_seen_at": "2026-08-01T10:00:00+00:00",
        "raw_metadata": {},
    }


def _transcript() -> dict:
    return {
        "transcript_id": f"transcript-{ITEM_ID}",
        "item_id": ITEM_ID,
        "source_id": SOURCE_ID,
        "language": "af",
        "acquisition": {"tier": "tier_3_local_speech_to_text"},
        "provenance": {"method": "auto_generated", "created_by": "faster-whisper", "created_at": "2026-08-01"},
        "segments": [
            {"text": "Welkom by die podcast.", "start_seconds": 0, "end_seconds": 3},
            {"text": "Die proef mag volgende jaar uitbrei.", "start_seconds": 20, "end_seconds": 24},
        ],
    }


def _draft(item: dict) -> dict:
    return {
        "id": publication_draft_id(item),
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "intake_type": "discovered_media_publication",
        "source_type": "discovered_media",
        "title": item["title"],
        "source_name": "Lucentlands Podcast",
        "source_url": item["canonical_url"],
        "published_date": item["published_date"],
        "captured_date": "2026-08-01",
        "summary": item["description"],
        "why_it_matters": "",
        "submitted_by": "media-orchestration",
        "berry_ids": [],
        "geography_ids": [],
        "entity_ids": [],
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": [],
        "attachments": [],
        "auto_captured": False,
        "priority": {d: {"level": "none", "rationale": ""} for d in ("reading", "testing", "commercial_position", "monitoring")},
        "source_id": SOURCE_ID,
        "media_format": "podcast",
        "evidence_role": "publication_artifact",
        "discovered_item_id": item["id"],
        "discovery_provenance": {
            "dedupe_key": item["dedupe_key"],
            "external_id": item["external_id"],
            "first_seen_at": item["first_seen_at"],
            "last_seen_at": item["last_seen_at"],
        },
    }


def _restore(inbox: Path, *, include_draft: bool = True) -> str:
    item = _item()
    (inbox / "discovered_media").mkdir(parents=True, exist_ok=True)
    (inbox / "discovered_media" / f"{ITEM_ID}.json").write_text(json.dumps(item), encoding="utf-8")
    (inbox / "discovered_media" / "_normalized_transcripts").mkdir(parents=True, exist_ok=True)
    (inbox / "discovered_media" / "_normalized_transcripts" / f"{ITEM_ID}.json").write_text(
        json.dumps(_transcript()), encoding="utf-8"
    )
    draft = _draft(item)
    if include_draft:
        (inbox / "evidence").mkdir(parents=True, exist_ok=True)
        (inbox / "evidence" / f"{draft['id']}.json").write_text(json.dumps(draft), encoding="utf-8")
    return draft["id"]


@pytest.fixture
def restored_runtime(monkeypatch, tmp_path: Path):
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    main._JSON_FOLDER_CACHE.clear()
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    repos.sources.create({"id": SOURCE_ID, "name": "Lucentlands Podcast"})
    draft_id = _restore(inbox)
    return {"inbox": inbox, "data": data, "draft_id": draft_id}


def _publish(client: TestClient, draft_id: str, **overrides):
    data = {
        "title": "Scaling the Blueberry Industry",
        "summary": "Lucentlands episode on scaling the blueberry industry.",
        "reviewer": "johnny",
        "source_type": "discovered_media",
        "source_name": "Lucentlands Podcast",
        "source_url": "https://anchor.fm/lucentlands/ep",
        "published_date": "2026-07-01",
        "captured_date": "2026-08-01",
    }
    data.update(overrides)
    return client.post(f"/review/{draft_id}/publish", data=data, follow_redirects=False)


def test_restored_publication_draft_is_visible_in_review(restored_runtime) -> None:
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]
    workbench = client.get("/review")
    assert workbench.status_code == 200
    assert "Scaling the Blueberry Industry" in workbench.text
    detail = client.get(f"/review/{draft_id}")
    assert detail.status_code == 200
    assert "Scaling the Blueberry Industry" in detail.text


def test_restored_publication_draft_publishes_through_ordinary_path(restored_runtime) -> None:
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]
    inbox = restored_runtime["inbox"]

    response = _publish(client, draft_id)
    assert response.status_code == 303  # published, not "Draft not found"

    repos = main.get_repositories(restored_runtime["data"], main.SCHEMAS_DIR)
    published = repos.evidence.get(draft_id)
    assert published is not None
    assert published["status"] == "published" and published["review_state"] == "published"
    assert published["evidence_role"] == "publication_artifact"
    assert published["discovered_item_id"] == ITEM_ID
    # The draft is consumed from inbox by the ordinary publish transaction.
    assert not (inbox / "evidence" / f"{draft_id}.json").exists()


def test_publish_preserves_human_approval_and_trust_semantics(restored_runtime) -> None:
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]
    inbox = restored_runtime["inbox"]
    data = restored_runtime["data"]

    # Before any human action, the draft is untrusted and nothing is in data/.
    assert (inbox / "evidence" / f"{draft_id}.json").exists()
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    assert repos.evidence.get(draft_id) is None

    # Publishing requires a reviewer; a missing reviewer is rejected (no promotion).
    missing_reviewer = _publish(client, draft_id, reviewer="")
    assert missing_reviewer.status_code == 400
    assert main.get_repositories(data, main.SCHEMAS_DIR).evidence.get(draft_id) is None

    # The explicit human publish is the only path that promotes it.
    ok = _publish(client, draft_id, reviewer="johnny")
    assert ok.status_code == 303
    published = main.get_repositories(data, main.SCHEMAS_DIR).evidence.get(draft_id)
    assert published["reviewed_by"] == "johnny" and published["review_state"] == "published"


def test_missing_draft_publish_fails_safely(restored_runtime) -> None:
    client = TestClient(app)
    absent = client.post("/review/ev-media-does-not-exist/publish", data={"title": "t", "summary": "s", "reviewer": "j"}, follow_redirects=False)
    assert absent.status_code == 404
    assert absent.json()["detail"] == "Draft not found"


def test_publish_needs_no_unrelated_runtime_state(monkeypatch, tmp_path: Path) -> None:
    # Only the three restored artifacts + the source registry; no operations/,
    # qualifications/, or other runtime state exists.
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    main._JSON_FOLDER_CACHE.clear()
    main.get_repositories(data, main.SCHEMAS_DIR).sources.create({"id": SOURCE_ID, "name": "Lucentlands Podcast"})
    draft_id = _restore(inbox)
    assert not (inbox / "operations").exists() and not (inbox / "qualifications").exists()

    response = _publish(TestClient(app), draft_id)
    assert response.status_code == 303


def test_transcript_readiness_is_independent_of_publication_approval(restored_runtime) -> None:
    inbox = restored_runtime["inbox"]
    draft_id = restored_runtime["draft_id"]
    # Readiness is computed from the transcript alone, before any publish.
    readiness = load_publication_transcript_readiness(inbox)
    assert readiness[draft_id]["state"] == "ready"

    # Publishing succeeds and does not depend on readiness state.
    response = _publish(TestClient(app), draft_id)
    assert response.status_code == 303


def test_read_and_publish_agree_when_draft_absent(monkeypatch, tmp_path: Path) -> None:
    # Proves there is no read/write split-brain: with the evidence draft absent
    # (discovered-media + transcript still present), the review READ path and the
    # PUBLISH path BOTH 404 -- neither invents a draft from discovered_media.
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    main._JSON_FOLDER_CACHE.clear()
    main.get_repositories(data, main.SCHEMAS_DIR).sources.create({"id": SOURCE_ID, "name": "Lucentlands Podcast"})
    draft_id = _restore(inbox, include_draft=False)

    client = TestClient(app)
    assert client.get(f"/review/{draft_id}").status_code == 404
    assert _publish(client, draft_id).status_code == 404
    assert "Scaling the Blueberry Industry" not in client.get("/review").text
