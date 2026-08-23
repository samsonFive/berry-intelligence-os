"""Demo-facing scanner and publication-review presentation."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.media_orchestration import publication_draft_id
from app.services.review_workbench import build_public_scanner_summary, build_scanner_summary


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _item(inbox: Path, suffix: str, *, decision: str = "process") -> dict:
    item = {
        "id": f"discovered-source-fixture-{suffix}",
        "source_id": "source-fixture",
        "title": f"Synthetic blueberry {suffix}",
        "canonical_url": f"https://example.invalid/{suffix}",
        "published_date": "2026-08-15",
        "media_format": "podcast",
        "relevance_screening": {
            "score": 20 if decision == "process" else 1,
            "decision": decision,
            "reason": "fixture",
            "trust_state": "untrusted_triage",
        },
    }
    _write(inbox / "discovered_media" / f"{item['id']}.json", item)
    return item


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
        "summary": "Long publisher RSS dump that must not lead the card.",
        "publisher_description": "Long publisher RSS dump that must not lead the card.",
        "why_it_matters": "",
        "submitted_by": "collection fixture",
        "evidence_role": "publication_artifact",
        "media_format": "podcast",
        "discovered_item_id": item["id"],
        "berry_ids": ["berry-blueberry"],
        "suggested_competitors": [],
        "suggested_varieties": [],
        "attachments": [],
        "ai_enrichment": {
            "concise_summary": "Peru supply risk is the CI point.",
            "why_it_matters": "El Niño can disrupt blueberry export timing.",
            "suggested_berry_ids": ["berry-blueberry"],
            "suggested_geography_ids": ["geography-peru"],
            "suggested_entity_ids": [],
            "suggested_tags": ["climate-risk"],
            "topical_relevance": "High relevance to blueberry competitive intelligence.",
            "confidence": 0.7,
            "caveats": "Show notes only.",
            "model_provenance": {
                "status": "ok",
                "provider": "perplexity-agent",
                "model": "anthropic/claude-haiku-4-5",
                "trust_state": "untrusted_suggestion",
            },
        },
    }


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    return inbox


def test_scanner_does_not_treat_missing_transcripts_as_failures(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    relevant = _item(inbox, "relevant")
    _item(inbox, "skip", decision="skip")
    drafts = [_draft(relevant)]
    summary = build_scanner_summary(inbox_dir=inbox, drafts=drafts, published=[], transcript_readiness={})
    assert summary["found"] == 2
    assert summary["important"] == 1
    assert summary["skipped"] == 1
    assert summary["needs_review"] == 1
    assert summary["transcript_ready"] == 0
    assert summary["review_ready_without_transcript"] == 1
    assert summary["attention"] == 0
    assert summary["note"]
    assert "failure" in summary["note"].casefold()
    assert "0 failures" not in summary["note"].casefold()


def test_public_scanner_summary_uses_only_published_records() -> None:
    published = [
        {"id": "ev-trusted", "status": "published", "evidence_role": "publication_artifact"},
        {"id": "ev-other", "status": "published"},
        {"id": "ev-draftish", "status": "draft"},
    ]
    summary = build_public_scanner_summary(published)
    assert summary["public_snapshot"] is True
    assert summary["accepted"] == 2
    assert summary["found"] == 0
    assert summary["needs_review"] == 0
    assert summary["attention"] == 0
    assert "inbox" not in summary["note"].casefold()
    assert "local" in summary["note"].casefold()


def test_scanner_and_publication_queue_lead_with_analyst_fields(monkeypatch, tmp_path: Path) -> None:
    inbox = _isolate(monkeypatch, tmp_path)
    item = _item(inbox, "elnino")
    main.save_draft(_draft(item))
    weak = _item(inbox, "weak")
    weak_draft = _draft(weak)
    weak_draft["title"] = "How DNA Technology Is Transforming Agriculture | Ep. 151"
    weak_draft["published_date"] = "2026-08-12"
    weak_draft["ai_enrichment"]["topical_relevance"] = "Low to moderate. Not berry-specific."
    weak_draft["ai_enrichment"]["why_it_matters"] = "Generic breeding technology, not a berry CI brief."
    weak_draft["ai_enrichment"]["concise_summary"] = "A generic agriculture podcast."
    main.save_draft(weak_draft)
    client = TestClient(app)

    scanner = client.get("/work-queue")
    assert scanner.status_code == 200
    assert "Live Intelligence" in scanner.text
    assert "v2-feed-grid" in scanner.text or "intel-card" in scanner.text
    assert "FOUND" not in scanner.text
    assert "0 failures" not in scanner.text.casefold()
    assert "El Niño can disrupt blueberry export timing." in scanner.text
    assert scanner.text.index("Synthetic blueberry elnino") < scanner.text.index("How DNA Technology")
    assert "Peru supply risk is the CI point." in scanner.text
    assert "AI-assisted · pending analyst review" in scanner.text
    assert 'href="/intelligence/' in scanner.text
    assert "Promote publication" not in scanner.text

    queue = client.get("/review?kind=publication")
    assert queue.status_code == 200
    assert "Needs publication review" in queue.text
    assert "Why it matters" in queue.text
    assert "High relevance" in queue.text
    assert "Review" in queue.text
    assert "Long publisher RSS dump that must not lead the card." not in queue.text

    form = client.get(f"/review/{publication_draft_id(item)}")
    assert form.status_code == 200
    assert "HUMAN PUBLICATION REVIEW" in form.text
    assert "Why this matters" in form.text
    assert "Concise summary" in form.text
    assert "Publish + Next" in form.text
    assert "Save + Next" in form.text
    assert "Reject + Next" in form.text
    assert form.text.index("Why this matters") < form.text.index("Original submission")
    assert form.text.index("Concise summary") < form.text.index("AI provenance")
