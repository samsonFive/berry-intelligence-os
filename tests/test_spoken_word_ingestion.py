"""End-to-end checks for the single real Lucentlands ingestion spike."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ID = "ev-lucentlands-scaling-blueberry-industry-2025"
SOURCE_ID = "source-lucentlands-podcast"


def _record() -> dict:
    return json.loads((ROOT / "data" / "evidence" / f"{EVIDENCE_ID}.json").read_text(encoding="utf-8"))


def test_real_spoken_word_evidence_integrity_and_links() -> None:
    record = _record()
    assert not list(main.get_validator("evidence.schema.json").iter_errors(record))
    assert record["source_id"] == SOURCE_ID
    assert record["published_date"] == "2025-10-28"
    assert record["captured_date"] == "2026-08-15"
    assert record["published_date"] != record["captured_date"]
    assert record["transcript"] == {"status": "not_available"}
    assert record["status"] == record["review_state"] == "published"
    assert record["auto_captured"] is False and record["validated"] is True

    repositories = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    assert repositories.sources.get(SOURCE_ID)["label"] == "Lucentlands Podcast"
    linked = {entity_id: repositories.entities.get(entity_id) for entity_id in record["entity_ids"]}
    assert linked["company-fall-creek-farm-and-nursery"]["name"] == "Fall Creek Farm & Nursery, Inc."
    assert linked["geography-south-africa"]["name"] == "South Africa"
    assert record["geography_ids"] == ["geography-south-africa"]
    assert all(entity and entity["entity_type"] != "person" for entity in linked.values())
    assert all(EVIDENCE_ID in entity["evidence_ids"] for entity in linked.values())


def test_real_spoken_word_evidence_uses_existing_filters_and_detail_page() -> None:
    record = _record()
    assert main.filter_evidence([record], media_format="podcast") == [record]
    assert main.filter_evidence([record], source="industry_podcast") == [record]
    assert main.filter_evidence([record], berry="berry-blueberry") == [record]
    assert main.filter_evidence([record], geography="geography-south-africa") == [record]
    assert main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR).evidence.list(source_id=SOURCE_ID)[0]["id"] == EVIDENCE_ID

    response = TestClient(app).get(f"/evidence/{EVIDENCE_ID}")
    assert response.status_code == 200
    assert "Podcast" in response.text
    assert "Transcript" in response.text
    assert "Not Available" in response.text
    assert "Fall Creek Farm &amp; Nursery, Inc." in response.text
    assert "South Africa" in response.text


def test_general_review_publish_preserves_optional_media_metadata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    draft_id = "ev-review-media-metadata"
    main.save_draft(
        {
            "id": draft_id,
            "record_type": "evidence",
            "status": "draft",
            "intake_type": "article_or_url",
            "source_type": "industry_podcast",
            "title": "Reviewed podcast item",
            "source_name": "Publisher",
            "source_url": "https://example.invalid/podcast",
            "published_date": "2025-10-28",
            "captured_date": "2026-08-15",
            "summary": "Publisher-supplied description.",
            "why_it_matters": "",
            "submitted_by": "tester",
            "source_id": SOURCE_ID,
            "media_format": "podcast",
            "transcript": {"status": "not_available"},
            "suggested_competitors": [],
            "suggested_varieties": [],
            "attachments": [],
        }
    )

    response = TestClient(app).post(
        f"/review/{draft_id}/publish",
        data={
            "title": "Reviewed podcast item",
            "source_type": "industry_podcast",
            "source_name": "Publisher",
            "source_url": "https://example.invalid/podcast",
            "published_date": "2025-10-28",
            "captured_date": "2026-08-15",
            "summary": "Publisher-supplied description.",
            "berries": ["berry-blueberry"],
            "reviewer": "human-reviewer",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    published = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR).evidence.get(draft_id)
    assert published["source_id"] == SOURCE_ID
    assert published["media_format"] == "podcast"
    assert published["transcript"] == {"status": "not_available"}
