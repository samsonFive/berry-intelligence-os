"""Pending triage buckets, watch-match ranking, one-click dismiss, company deltas."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.analyst_queue import load_state, pending_workflow_state
from app.services.morning_brief import build_morning_brief


PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    (tmp_path / "inbox" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "configuration").mkdir(parents=True, exist_ok=True)
    _write(tmp_path / "data" / "configuration" / "sources.json", [])


def _today() -> str:
    return date.today().isoformat()


def _published(record_id: str, **overrides) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "news_search",
        "source_name": "FreshPlaza",
        "source_url": "https://example.invalid/" + record_id,
        "title": f"Trusted {record_id}",
        "published_date": "2026-08-10",
        "captured_date": "2026-08-10",
        "summary": "Trusted published article fixture.",
        "why_it_matters": "Analyst-facing rationale.",
        "submitted_by": "reviewer",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-08-10",
        "priority": deepcopy(PRIORITY),
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "tags": ["tier-1"],
    }
    record.update(overrides)
    return record


def _draft(record_id: str, **overrides) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "evidence_role": "publication_artifact",
        "status": "pending",
        "review_state": "pending_review",
        "source_type": "rss",
        "source_name": "Trade desk",
        "source_url": "https://example.invalid/" + record_id,
        "title": f"Pending {record_id}",
        "published_date": _today(),
        "captured_date": _today(),
        "summary": "Untrusted pending article.",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "relevance_tier": "direct",
        "media_format": "web_article",
        "priority": deepcopy(PRIORITY),
    }
    record.update(overrides)
    return record


def _seed_entities(repos) -> None:
    for entity in (
        {
            "id": "company-planasa",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Plantas de Navarra, S.A.",
            "aliases": ["Planasa"],
            "status": "active",
        },
        {
            "id": "company-hortifrut",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Hortifrut S.A.",
            "aliases": ["Hortifrut"],
            "status": "active",
        },
        {
            "id": "geography-mexico",
            "record_type": "entity",
            "entity_type": "geography",
            "name": "Mexico",
            "status": "active",
        },
    ):
        repos.entities.create(entity)


def test_pending_triage_buckets_and_review_now_reasons(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    watch = deepcopy(PRIORITY)
    watch["reading"] = {"level": "medium", "rationale": "Watch Planasa."}
    watch["monitoring"] = {"level": "high", "rationale": "Watch Planasa."}
    repos.evidence.create(
        _published(
            "ev-planasa-watch",
            title="Planasa breeding program",
            entity_ids=["company-planasa"],
            priority=watch,
        )
    )
    drafts = [
        _draft(
            "draft-planasa-now",
            title="Planasa launches Blue Maldiva blueberry",
            source_id="source-20260819-planasa-newsroom",
            source_name="Planasa Newsroom",
        ),
        _draft(
            "draft-adjacent",
            title="Warehouse robots mention berries once",
            relevance_tier="adjacent",
            berry_ids=[],
        ),
        _draft(
            "draft-old",
            title="Old generic packing note",
            published_date="2025-01-01",
            captured_date="2025-01-01",
            berry_ids=[],
            relevance_tier=None,
        ),
        _draft(
            "draft-skip",
            title="Tomato greenhouse construction",
            berry_ids=[],
            relevance_tier=None,
            relevance_screening={"decision": "skip"},
        ),
    ]
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=repos.evidence.list(),
        drafts=drafts,
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
        sources=[
            {
                "id": "source-20260819-planasa-newsroom",
                "label": "Planasa Newsroom",
                "monitoring_priority": "high",
                "linked_competitor_ids": ["company-planasa"],
            }
        ],
        mark_seen=False,
    )
    counts = brief["pending_triage"]["counts"]
    assert counts["review_now"] >= 1
    assert counts["adjacent"] >= 1
    assert counts["likely_ignore"] >= 1
    assert counts["older_backlog"] >= 1
    review_now_ids = [item["id"] for item in brief["needs_decision"]]
    assert "draft-planasa-now" in review_now_ids
    assert "draft-adjacent" not in review_now_ids
    planasa = next(item for item in brief["needs_decision"] if item["id"] == "draft-planasa-now")
    assert planasa["primary_subject"]["id"] == "company-planasa"
    assert planasa["watch_match"] == "primary"
    assert "Why this needs your decision" in planasa["why_decision"]
    assert "active watch" in planasa["why_decision"]
    deltas = [row for row in brief["company_deltas"] if row["id"] == "company-planasa"]
    assert deltas
    assert any(bullet["id"] == "draft-planasa-now" for bullet in deltas[0]["bullets"])


def test_company_primary_watch_outranks_geography_headline(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    planasa_watch = deepcopy(PRIORITY)
    planasa_watch["reading"] = {"level": "medium", "rationale": "Watch Planasa."}
    planasa_watch["monitoring"] = {"level": "high", "rationale": "Watch Planasa."}
    mexico_watch = deepcopy(PRIORITY)
    mexico_watch["reading"] = {"level": "medium", "rationale": "Watch Mexico."}
    mexico_watch["monitoring"] = {"level": "high", "rationale": "Watch Mexico."}
    repos.evidence.create(
        _published("ev-planasa-watch", title="Planasa breeding program", entity_ids=["company-planasa"], priority=planasa_watch)
    )
    repos.evidence.create(
        _published("ev-mexico-watch", title="Mexico supply watch", entity_ids=["geography-mexico"], priority=mexico_watch)
    )
    drafts = [
        _draft("draft-mexico", title="Mexico blueberry harvest outlook"),
        _draft("draft-planasa", title="Planasa files a new blueberry variety"),
    ]
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=repos.evidence.list(),
        drafts=drafts,
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
        mark_seen=False,
    )
    ranked = {item["id"]: item for group in brief["pending_triage"]["buckets"] for item in group["entries"]}
    assert ranked["draft-planasa"]["watch_match"] == "primary"
    assert ranked["draft-mexico"]["watch_match"] == "primary"
    assert ranked["draft-planasa"]["primary_subject"]["entity_type"] == "company"
    assert ranked["draft-mexico"]["primary_subject"]["entity_type"] == "geography"
    assert ranked["draft-planasa"]["score"] > ranked["draft-mexico"]["score"]
    assert ranked["draft-planasa"]["triage_bucket"] == "review_now"
    assert ranked["draft-mexico"]["triage_bucket"] == "review_soon"


def test_bulk_dismiss_hides_draft_without_rejecting(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    draft = _draft("draft-ignore", title="Tomato greenhouse construction", berry_ids=[], relevance_tier=None)
    _write(tmp_path / "inbox" / "evidence" / "draft-ignore.json", draft)
    client = TestClient(app)
    page = client.get("/brief")
    assert page.status_code == 200
    assert "Pending draft triage" in page.text
    assert "draft-ignore" in page.text or "Tomato greenhouse" in page.text
    response = client.post(
        "/queues/pending/bulk-dismiss",
        data={"item_id": "draft-ignore", "reviewer": "analyst", "return_to": "/brief#pending-triage"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    stored = json.loads((tmp_path / "inbox" / "evidence" / "draft-ignore.json").read_text(encoding="utf-8"))
    assert stored["status"] == "pending"
    assert pending_workflow_state("draft-ignore", load_state(main.INBOX_DIR)) == "dismissed"
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=[],
        drafts=[stored],
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
        mark_seen=False,
    )
    assert brief["pending_triage"]["counts"]["total"] == 0
    assert brief["pending_triage"]["counts"]["dismissed"] == 1


def test_hortifrut_newsroom_draft_appears_in_company_delta(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    draft = _draft(
        "draft-hf-newsroom",
        title="First-half berry sales and genetics platform",
        source_id="source-20260819-hortifrut-newsroom",
        source_name="Hortifrut Newsroom",
        entity_ids=[],
    )
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=[],
        drafts=[draft],
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
        sources=[
            {
                "id": "source-20260819-hortifrut-newsroom",
                "label": "Hortifrut Newsroom",
                "monitoring_priority": "high",
                "linked_competitor_ids": ["company-hortifrut"],
            }
        ],
        mark_seen=False,
    )
    item = brief["needs_decision"][0]
    assert item["primary_subject"]["id"] == "company-hortifrut"
    assert item["attribution_method"] == "newsroom_identity"
    hortifrut = next(row for row in brief["company_deltas"] if row["id"] == "company-hortifrut")
    assert hortifrut["bullets"][0]["id"] == "draft-hf-newsroom"
