"""Duplicate publication publish must never 500.

Reproduces POST /review/<id>/publish when a trusted Evidence record already
exists at the same deterministic id: identical identity is already-published
success; conflicting identity is a controlled 409 with no overwrite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.media_orchestration import publication_draft_id
from app.services.review_events import load_review_events
from tests.test_review_publish_portability import SOURCE_ID, _draft, _item, _publish, _restore


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


def _trusted(item: dict, **changes) -> dict:
    record = {
        "id": publication_draft_id(item),
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "discovered_media",
        "title": item["title"],
        "source_name": "Lucentlands Podcast",
        "source_url": item["canonical_url"],
        "published_date": item["published_date"],
        "captured_date": "2026-08-01",
        "summary": "Already-trusted publication summary.",
        "why_it_matters": "Existing trusted why.",
        "submitted_by": "fixture",
        "berry_ids": ["berry-blueberry"],
        "source_id": SOURCE_ID,
        "media_format": "podcast",
        "evidence_role": "publication_artifact",
        "discovered_item_id": item["id"],
        "reviewed_by": "prior-reviewer",
        "reviewed_at": "2026-08-01",
        "priority": {
            dimension: {"level": "none", "rationale": ""}
            for dimension in ("reading", "testing", "commercial_position", "monitoring")
        },
    }
    record.update(changes)
    return record


def test_identical_trusted_publish_is_already_published_not_500(restored_runtime) -> None:
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]
    data = restored_runtime["data"]
    inbox = restored_runtime["inbox"]
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    repos.evidence.create(_trusted(_item()))

    response = _publish(client, draft_id)
    assert response.status_code in {200, 303}
    assert response.status_code != 500
    assert "Internal Server Error" not in response.text
    after = main.get_repositories(data, main.SCHEMAS_DIR).evidence.get(draft_id)
    assert after["summary"] == "Already-trusted publication summary."
    assert after["reviewed_by"] == "prior-reviewer"
    assert not (inbox / "evidence" / f"{draft_id}.json").exists()


def test_conflicting_trusted_publish_is_409_and_does_not_overwrite(restored_runtime) -> None:
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]
    data = restored_runtime["data"]
    inbox = restored_runtime["inbox"]
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    repos.evidence.create(
        _trusted(_item(), title="A different trusted title", source_url="https://other.example/item")
    )

    response = _publish(client, draft_id)
    assert response.status_code == 409
    assert "json" not in (response.headers.get("content-type") or "")
    assert "trusted" in response.text.lower()
    after = main.get_repositories(data, main.SCHEMAS_DIR).evidence.get(draft_id)
    assert after["title"] == "A different trusted title"
    assert after["summary"] == "Already-trusted publication summary."
    assert (inbox / "evidence" / f"{draft_id}.json").exists()


def test_repeat_publish_after_success_is_already_published(restored_runtime) -> None:
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]
    inbox = restored_runtime["inbox"]
    first = _publish(client, draft_id)
    assert first.status_code == 303
    (inbox / "evidence").mkdir(parents=True, exist_ok=True)
    (inbox / "evidence" / f"{draft_id}.json").write_text(
        __import__("json").dumps(_draft(_item())),
        encoding="utf-8",
    )
    second = _publish(client, draft_id)
    assert second.status_code in {200, 303}
    assert second.status_code != 500
    published = main.get_repositories(restored_runtime["data"], main.SCHEMAS_DIR).evidence.get(draft_id)
    assert published["status"] == "published"
    assert published["reviewed_by"] == "johnny"
    events = load_review_events(inbox)
    assert len(events) == 1 and events[0]["action"] == "publish"


def test_review_form_has_speed_actions_and_untrusted_enrichment_panel(restored_runtime) -> None:
    draft_id = restored_runtime["draft_id"]
    path = restored_runtime["inbox"] / "evidence" / f"{draft_id}.json"
    draft = __import__("json").loads(path.read_text(encoding="utf-8"))
    draft["publisher_description"] = "Original RSS show notes with promo text."
    draft["why_it_matters"] = "Suggested CI why."
    draft["ai_enrichment"] = {
        "concise_summary": "CI summary of blueberry scaling.",
        "why_it_matters": "Suggested CI why.",
        "suggested_berry_ids": ["berry-blueberry"],
        "suggested_geography_ids": [],
        "suggested_entity_ids": [],
        "suggested_tags": ["industry"],
        "topical_relevance": "high",
        "confidence": 0.6,
        "caveats": "Show notes only.",
        "model_provenance": {
            "status": "ok",
            "provider": "perplexity-agent",
            "model": "anthropic/claude-haiku-4-5",
            "trust_state": "untrusted_suggestion",
        },
    }
    path.write_text(__import__("json").dumps(draft), encoding="utf-8")
    client = TestClient(app)
    detail = client.get(f"/review/{draft_id}")
    assert detail.status_code == 200
    assert "Original RSS show notes" in detail.text
    assert "CI summary of blueberry scaling" in detail.text
    assert "untrusted" in detail.text
    assert "Publish + Next" in detail.text
    assert "Save + Next" in detail.text
    assert "Reject + Next" in detail.text
    queue = client.get("/review?kind=publication&enrichment=enriched")
    assert queue.status_code == 200
    assert "Scaling the Blueberry Industry" in queue.text
    assert "ENRICHED" in queue.text
