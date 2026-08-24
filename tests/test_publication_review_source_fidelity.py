"""Planasa runtime drafts: source fidelity, extraction input, review prefill."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.publication_review_workspace import (
    build_publication_review_dossier,
    detect_variety_observations,
)
from app.services.source_body import atomic_extraction_source_text, classify_source_body

FIXTURES = Path(__file__).parent / "fixtures" / "planasa"
RETAILER_ID = "ev-media-069f07925d20b2d93743"
PINK_ID = "ev-media-c8cdb7133db1cae0bf66"


def _load(draft_id: str) -> dict:
    return json.loads((FIXTURES / f"{draft_id}.json").read_text(encoding="utf-8"))


def test_retailer_article_persists_variety_level_passages() -> None:
    draft = _load(RETAILER_ID)
    body = classify_source_body(draft)
    text = body["body"]
    assert body["state"] == "body_available"
    assert "RedSayra" in text and "precocity" in text and "firmness" in text
    assert "Red Samantha" in text and "calibre" in text
    assert "Blue Maldiva" in text and "bloom" in text
    assert "Pink Hudson" in text and "shelf life" in text and "double cropping" in text
    assert "Black Sultana" in text
    assert "Tesco" in text
    extraction = atomic_extraction_source_text(draft)
    assert extraction == text
    assert "Full article text:" not in extraction
    assert "Planasa&#8217;s" not in text
    rows = {row["name"]: row for row in detect_variety_observations(text)}
    assert set(rows) >= {
        "RedSayra",
        "Red Samantha",
        "Blue Maldiva",
        "Blue Madeira",
        "Blue Manila",
        "Pink Hudson",
        "Black Sultana",
    }
    assert "Precocity" in rows["RedSayra"]["traits"]
    assert "Firmness" in rows["RedSayra"]["traits"]
    assert "Flavor" in rows["RedSayra"]["traits"]
    assert "Bloom" in rows["Blue Maldiva"]["traits"]
    assert "Winter production" in rows["Pink Hudson"]["traits"]
    assert "Double cropping" in rows["Pink Hudson"]["traits"]


def test_review_summary_is_enrichment_not_body() -> None:
    draft = _load(RETAILER_ID)
    assert "precocity" not in (draft.get("summary") or "").casefold()
    assert "Full article text:" in (draft.get("publisher_description") or "")
    assert "Planasa&#8217;s" in (draft.get("publisher_description") or "")


def test_pink_hudson_body_is_english_not_spanish_original() -> None:
    draft = _load(PINK_ID)
    body = classify_source_body(draft)
    assert "Superior Taste Award" in body["body"]
    assert "Pink Hudson" in body["body"]
    assert "La entrada" in body["publisher_description"]
    assert "frambuesa" not in body["body"].casefold()
    dossier = build_publication_review_dossier(
        draft,
        entities={"company-planasa": {"id": "company-planasa", "name": "Planasa", "entity_type": "company"}},
        berry_labels=main.BERRIES,
    )
    assert dossier["language_label"] == "ORIGINAL — English"
    assert dossier["translation_available"] is False
    names = {row["name"] for row in dossier["detected_intelligence"]}
    assert "Pink Hudson" in names
    assert "berry-raspberry" in dossier["prefill"]["berries"]
    assert "Planasa" in dossier["prefill"]["companies"]
    assert dossier["body"]["paragraphs"]
    assert dossier["body"]["paragraphs"][0]["index"] == 1
    assert dossier["if_published"]["atomic_evidence"] == "NOT CREATED BY THIS ACTION"
    assert dossier["source_attribution_class"] == "COMPANY-REPORTED"


def test_review_page_shows_detected_intelligence_and_decoded_html(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    main._JSON_FOLDER_CACHE.clear()
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    repos.sources.create({"id": "source-20260819-planasa-newsroom", "name": "Planasa Newsroom"})
    repos.entities.create(
        {
            "id": "company-planasa",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Plantas de Navarra, S.A.",
            "aliases": ["Planasa"],
            "status": "active",
        }
    )
    (inbox / "evidence").mkdir(parents=True)
    shutil.copy(FIXTURES / f"{RETAILER_ID}.json", inbox / "evidence" / f"{RETAILER_ID}.json")
    page = TestClient(app).get(f"/review/{RETAILER_ID}")
    assert page.status_code == 200
    assert "Detected intelligence — UNTRUSTED / REVIEW AID" in page.text
    assert "Paragraph 1" in page.text
    assert "If published" in page.text
    assert "NOT CREATED BY THIS ACTION" in page.text
    assert "COMPANY-REPORTED" in page.text
    assert "RedSayra" in page.text
    assert "Precocity" in page.text
    assert "Pink Hudson" in page.text
    assert "FULL ARTICLE" in page.text
    assert "Planasa&#8217;s" not in page.text
    assert "R&#38;D" not in page.text
    assert "Publish + Next" in page.text
    assert "Save draft does not publish" in page.text
    assert "Planasa" in page.text


def test_publish_preserves_article_paragraphs_for_atomic_input(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    main._JSON_FOLDER_CACHE.clear()
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    repos.sources.create({"id": "source-20260819-planasa-newsroom", "name": "Planasa Newsroom"})
    repos.entities.create(
        {
            "id": "company-planasa",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Plantas de Navarra, S.A.",
            "aliases": ["Planasa"],
            "status": "active",
        }
    )
    (inbox / "evidence").mkdir(parents=True)
    shutil.copy(FIXTURES / f"{RETAILER_ID}.json", inbox / "evidence" / f"{RETAILER_ID}.json")
    draft = _load(RETAILER_ID)
    client = TestClient(app)
    response = client.post(
        f"/review/{RETAILER_ID}/publish",
        data={
            "title": draft["title"],
            "summary": draft["summary"],
            "reviewer": "johnny",
            "source_type": draft["source_type"],
            "source_name": draft["source_name"],
            "source_url": draft["source_url"],
            "published_date": draft["published_date"],
            "captured_date": draft["captured_date"],
            "companies": "Planasa",
            "berries": draft["berry_ids"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    trusted = main.get_repositories(data, main.SCHEMAS_DIR).evidence.get(RETAILER_ID)
    assert trusted is not None
    paragraphs = (trusted.get("article") or {}).get("paragraphs") or []
    joined = " ".join(row.get("text") or "" for row in paragraphs)
    assert "RedSayra" in joined and "precocity" in joined
    assert atomic_extraction_source_text(trusted) == classify_source_body(draft)["body"]
    assert trusted["source_completeness"]["class"] == "FULL_ARTICLE"
    assert trusted["source_completeness"]["content_sha256"] == trusted["article"]["content_sha256"]


def test_thin_publication_dossier_warns_before_publish() -> None:
    draft = {
        "title": "Thin item", "summary": "A short feed description.",
        "publisher_description": "A short feed description.",
        "source_url": "https://example.test/thin", "source_type": "trade_press",
    }
    dossier = build_publication_review_dossier(draft, entities=[], berry_labels=main.BERRIES)
    assert dossier["source_completeness"]["class"] == "THIN_DESCRIPTION"
    assert dossier["body"]["label"] == "THIN DESCRIPTION"
    assert dossier["if_published"]["trusted_publication"] == "YES"
    assert "thin description" in dossier["if_published"]["rich_source_retained"].casefold()
    assert dossier["if_published"]["atomic_evidence"] == "NOT CREATED BY THIS ACTION"
    assert dossier["source_attribution_class"] == "TRADE PRESS"
    assert dossier["body"]["warning"] == "Full source content was not captured. Review the original source before publishing."


def test_atomic_extraction_uses_inline_transcript_without_segments() -> None:
    trusted = {
        "summary": "Thin publication description.",
        "media_format": "podcast",
        "transcript": {
            "status": "available",
            "language": "en",
            "text": "The complete inline transcript is the extraction source.",
        },
    }

    assert atomic_extraction_source_text(trusted) == trusted["transcript"]["text"]


def test_pending_first_screen_caps_rendered_cards(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox" / "evidence"
    inbox.mkdir(parents=True)
    data = tmp_path / "data"
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", data)
    main._JSON_FOLDER_CACHE.clear()
    main.get_repositories(data, main.SCHEMAS_DIR)
    for index in range(45):
        record = {
            "id": f"draft-pending-{index:03d}",
            "record_type": "evidence",
            "status": "draft",
            "review_state": "in_review",
            "title": f"Pending item {index:03d} unique-title-token-{index:03d}",
            "source_name": "Fixture Source",
            "summary": "short",
            "captured_date": "2026-08-20",
            "published_date": "2026-08-20",
            "evidence_role": "publication_artifact",
            "relevance_tier": "direct",
            "berry_ids": ["berry-strawberry"],
            "priority": {
                dim: {"level": "none", "rationale": ""}
                for dim in ("reading", "testing", "commercial_position", "monitoring")
            },
        }
        (inbox / f"{record['id']}.json").write_text(json.dumps(record), encoding="utf-8")
    page = TestClient(app).get("/pending")
    assert page.status_code == 200
    rendered = page.text.count("unique-title-token-")
    assert rendered <= 100
    assert "more in this bucket" in page.text
