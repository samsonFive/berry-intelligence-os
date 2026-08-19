"""Morning brief ranks attention without creating a data silo or changing trust."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.analyst_queue import load_state, reading_state
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
        "entity_ids": ["company-planasa"],
        "tags": ["tier-1"],
    }
    record.update(overrides)
    return record


def _seed(repos, records: list[dict]) -> None:
    repos.entities.create(
        {
            "id": "company-planasa",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Plantas de Navarra, S.A.",
            "status": "active",
        }
    )
    repos.entities.create(
        {
            "id": "company-otherco",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Otherco Berries",
            "status": "active",
        }
    )
    for record in records:
        repos.evidence.create(record)


def test_watched_company_outRanks_unmonitored_same_date(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    reading_high = deepcopy(PRIORITY)
    reading_high["reading"] = {"level": "high", "rationale": "Planasa genetics."}
    reading_high["monitoring"] = {"level": "high", "rationale": "Watch Planasa."}
    other = deepcopy(PRIORITY)
    other["reading"] = {"level": "high", "rationale": "Unrelated."}
    _seed(
        repos,
        [
            _published(
                "ev-planasa-now",
                title="Planasa files a new blueberry variety",
                entity_ids=["company-planasa"],
                priority=reading_high,
            ),
            _published(
                "ev-other-now",
                title="Otherco opens a packing shed",
                entity_ids=["company-otherco"],
                berry_ids=["berry-blueberry"],
                priority=other,
            ),
        ],
    )
    _write(
        tmp_path / "data" / "signals" / "sig-planasa-1.json",
        {
            "id": "sig-planasa-1",
            "record_type": "signal",
            "title": "Planasa licensing signal",
            "status": "proposed",
            "direction": "emerging",
            "strength": "high",
            "evidence_ids": ["ev-planasa-now", "ev-other-now"],
            "entity_ids": ["company-planasa"],
            "reviewer": None,
            "proposed_at": "2026-08-10",
        },
    )
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=repos.evidence.list(),
        drafts=[],
        signals=repos.signals.list(),
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
        mark_seen=False,
    )
    top_ids = [item["id"] for item in brief["top_developments"]]
    assert top_ids[0] == "ev-planasa-now"
    assert "Planasa" in brief["top_developments"][0]["why_ranked"] or "watch" in brief["top_developments"][0]["why_ranked"].casefold()
    assert brief["watch_activity"]
    assert brief["watch_activity"][0]["signal_count"] >= 1
    assert all(bullet.get("href") for company in brief["company_deltas"] for bullet in company["bullets"])


def test_adjacent_is_not_top_priority(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    tagged = deepcopy(PRIORITY)
    tagged["reading"] = {"level": "high", "rationale": "Direct berry story."}
    adjacent = deepcopy(PRIORITY)
    adjacent["reading"] = {"level": "high", "rationale": "Incidental mention."}
    _seed(
        repos,
        [
            _published("ev-direct", title="Direct blueberry harvest", relevance_tier="direct", priority=tagged),
            _published(
                "ev-adjacent",
                title="Adjacent supermarket flyer mentions blueberries",
                relevance_tier="adjacent",
                priority=adjacent,
            ),
        ],
    )
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=repos.evidence.list(),
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
    )
    buckets = {group["key"]: [item["id"] for item in group["entries"]] for group in brief["reading_buckets"]}
    assert "ev-adjacent" in buckets["adjacent"]
    assert "ev-adjacent" not in buckets["top_priority"]
    assert "ev-direct" in buckets["top_priority"]


def test_brief_view_sets_last_seen_without_marking_read(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    tagged = deepcopy(PRIORITY)
    tagged["reading"] = {"level": "high", "rationale": "Need to read."}
    _seed(repos, [_published("ev-brief-1", priority=tagged)])
    client = TestClient(app)
    page = client.get("/brief")
    assert page.status_code == 200
    assert "Morning Brief" in page.text
    assert "Top developments" in page.text
    assert "Mark read" in page.text
    assert reading_state("ev-brief-1", load_state(main.INBOX_DIR)) == "unread"
    assert (load_state(main.INBOX_DIR).get("meta") or {}).get("brief", {}).get("last_seen_at")
    kept = client.post(
        "/queues/reading/ev-brief-1",
        data={"action": "keep", "reviewer": "analyst-fixture", "return_to": "/brief"},
        follow_redirects=False,
    )
    assert kept.status_code == 303
    assert kept.headers["location"] == "/brief"
    assert repos.evidence.get("ev-brief-1")["status"] == "published"


def test_older_items_go_to_backlog(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    tagged = deepcopy(PRIORITY)
    tagged["reading"] = {"level": "medium", "rationale": "Historical."}
    current = deepcopy(PRIORITY)
    current["reading"] = {"level": "high", "rationale": "Now."}
    _seed(
        repos,
        [
            _published("ev-old", title="2019 packing note", published_date="2019-03-25", captured_date="2019-03-25", priority=tagged),
            _published("ev-now", title="Current cycle note", published_date="2026-08-10", priority=current),
        ],
    )
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=repos.evidence.list(),
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
    )
    buckets = {group["key"]: [item["id"] for item in group["entries"]] for group in brief["reading_buckets"]}
    assert "ev-old" in buckets["backlog"]
    assert "ev-now" in buckets["top_priority"]


def test_real_reading_queue_morning_workload_is_smaller_than_unresolved() -> None:
    from app.main import BERRIES, DATA_DIR, INBOX_DIR, all_signals, entity_index, list_pending_drafts, published_evidence

    published = published_evidence()
    brief = build_morning_brief(
        inbox_dir=INBOX_DIR,
        published=published,
        drafts=list_pending_drafts(),
        signals=all_signals(),
        entities=entity_index(),
        berry_labels=BERRIES,
        mark_seen=False,
    )
    unresolved = brief["counts"]["unresolved"]
    top = brief["counts"]["top_priority"]
    backlog = brief["counts"]["backlog"]
    assert unresolved >= 100
    assert top < unresolved
    assert top <= 40
    assert backlog >= 1
    top_items = brief["top_developments"]
    assert 3 <= len(top_items) <= 7
    companies = {item["cluster"] for item in top_items}
    assert len(companies) >= 3
    for item in top_items:
        assert item.get("why_ranked")
        assert item.get("href", "").startswith("/intelligence/")
        assert int(item.get("age_days") or 0) <= 21 or "watch" in (item.get("why_ranked") or "").casefold()
        assert "ABN Lookup" not in (item.get("title") or "")
    top10_titles = [item["title"] for item in brief["reading_buckets"][0]["entries"][:10]]
    assert not any("ABN Lookup" in title for title in top10_titles)
    assert all(bullet.get("href") for company in brief["company_deltas"] for bullet in company["bullets"])
    Path("/opt/cursor/artifacts/morning_brief_workload.json").write_text(
        json.dumps(
            {
                "unresolved": unresolved,
                "top_priority": top,
                "needs_review": brief["counts"].get("needs_review"),
                "adjacent": brief["counts"].get("adjacent"),
                "saved": brief["counts"].get("saved"),
                "backlog": backlog,
                "frontier": brief["frontier"],
                "top10": [
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "score": item["score"],
                        "why": item["why_ranked"],
                        "date": item["date"],
                        "cluster": item["cluster"],
                    }
                    for item in (brief["reading_buckets"][0]["entries"][:10])
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
