"""Morning brief ranks attention without creating a data silo or changing trust."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.analyst_queue import load_state, reading_state, save_state
from app.services.morning_brief import build_morning_brief, primary_subject


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
            "aliases": ["Planasa"],
            "status": "active",
        }
    )
    repos.entities.create(
        {
            "id": "company-advanced-berry-breeding",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Advanced Berry Breeding B.V.",
            "aliases": ["Advanced Berry Breeding", "ABB"],
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
    companies = {item.get("cluster") or item.get("id") for item in top_items}
    assert len(companies) >= 3
    for item in top_items:
        assert item.get("why_ranked")
        href = item.get("href") or ""
        assert href.startswith("/intelligence/") or href.startswith("/threads/")
        age = int(item.get("age_days") or (item.get("primary") or {}).get("age_days") or 0)
        assert age <= 21 or "watch" in (item.get("why_ranked") or "").casefold() or item.get("is_thread")
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
                "since_last": brief.get("since_last", {}).get("counts"),
                "new_developments": [
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "date": item["date"],
                        "source": item.get("source_name"),
                        "why": item.get("why_ranked"),
                        "trust": item.get("trust"),
                        "label": item.get("change_label"),
                    }
                    for item in (brief.get("new_developments") or [])[:10]
                ],
                "important": [item["id"] for item in (brief.get("important") or [])],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _set_last_seen(when: str, source_states: dict | None = None) -> None:
    state = load_state(main.INBOX_DIR)
    payload = {"last_seen_at": when, "updated_at": when, "action": "viewed"}
    if source_states is not None:
        payload["source_states"] = source_states
    state.setdefault("meta", {})["brief"] = payload
    save_state(main.INBOX_DIR, state)


def test_new_current_article_is_separated_from_important_old_records(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    old_priority = deepcopy(PRIORITY)
    old_priority["reading"] = {"level": "high", "rationale": "Still unread genetics."}
    _seed(
        repos,
        [
            _published(
                "ev-old-important",
                title="Planasa Blue Manila data sheet",
                published_date="2026-08-04",
                captured_date="2026-08-04",
                priority=old_priority,
            )
        ],
    )
    _set_last_seen("2026-08-19T08:00:00")
    draft = {
        "id": "ev-media-mexico-blueberry",
        "record_type": "evidence",
        "status": "draft",
        "evidence_role": "publication_artifact",
        "source_type": "article_rss",
        "source_name": "HortiDaily",
        "source_id": "source-hortidaily",
        "title": "Mexico will host a new international conference on blueberry cultivation",
        "published_date": "2026-08-19",
        "captured_date": "2026-08-19",
        "first_seen_at": None,
        "discovered_item_id": "discovered-mexico-blueberry",
        "media_format": "web_article",
        "relevance_tier": "direct",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "summary": "Conference coverage.",
        "why_it_matters": "Mexico blueberry production conference.",
        "priority": deepcopy(PRIORITY),
    }
    tomato = {
        "id": "discovered-tomato-noise",
        "record_type": "discovered_media_item",
        "media_format": "web_article",
        "source_id": "source-hortidaily",
        "title": "Ghana tomato trials record yields of up to 78.5 tons per hectare",
        "published_date": "2026-08-19",
        "first_seen_at": "2026-08-19T12:05:00",
        "relevance_screening": {"decision": "skip", "reason": "no berry signal"},
    }
    berry_discovered = {
        "id": "discovered-mexico-blueberry",
        "record_type": "discovered_media_item",
        "media_format": "web_article",
        "source_id": "source-hortidaily",
        "title": draft["title"],
        "published_date": "2026-08-19",
        "first_seen_at": "2026-08-19T12:04:55",
        "relevance_screening": {"decision": "process", "likely_berry_ids": ["berry-blueberry"]},
    }
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=repos.evidence.list(),
        drafts=[draft],
        discovered=[tomato, berry_discovered],
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
        sources=[{"id": "source-hortidaily", "label": "HortiDaily", "monitoring_priority": "high"}],
        mark_seen=False,
    )
    new_ids = [item["id"] for item in brief["new_developments"]]
    important_ids = [item["id"] for item in brief["important"]]
    assert "ev-media-mexico-blueberry" in new_ids
    assert "ev-old-important" not in new_ids
    assert "ev-old-important" in important_ids
    assert "discovered-tomato-noise" not in new_ids
    assert any(item["id"] == "ev-media-mexico-blueberry" for item in brief["since_last"]["groups"][1]["entries"])
    assert brief["new_developments"][0]["change_label"]
    assert "current article" in brief["new_developments"][0]["why_ranked"] or "new since last check" in brief["new_developments"][0]["why_ranked"]


def test_watch_because_uses_primary_subject_not_comention(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    reading = deepcopy(PRIORITY)
    reading["reading"] = {"level": "high", "rationale": "Index."}
    watch = deepcopy(PRIORITY)
    watch["reading"] = {"level": "medium", "rationale": "Watch ABB."}
    watch["monitoring"] = {"level": "high", "rationale": "Watch ABB."}
    _seed(
        repos,
        [
            _published(
                "ev-abb-watch",
                title="Advanced Berry Breeding - Varieties",
                entity_ids=["company-advanced-berry-breeding"],
                priority=watch,
            ),
            _published(
                "ev-cfia-index",
                title="Plant Breeders' Rights - blueberry variety index",
                entity_ids=["company-advanced-berry-breeding", "company-planasa"],
                priority=reading,
            ),
        ],
    )
    entities = {entity["id"]: entity for entity in repos.entities.list()}
    subject = primary_subject(
        {"title": "Plant Breeders' Rights - blueberry variety index", "entity_ids": ["company-advanced-berry-breeding", "company-planasa"]},
        entities,
    )
    assert subject is None
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=repos.evidence.list(),
        entities=entities,
        berry_labels={"berry-blueberry": "Blueberry"},
        mark_seen=False,
    )
    cfia = next(
        item
        for group in brief["reading_buckets"]
        for item in group["entries"]
        if item["id"] == "ev-cfia-index"
    )
    why = cfia["why_ranked"]
    assert "Advanced Berry Breeding B.V. watch" not in why
    assert "mentions watched" in why
    planasa_deltas = [row for row in brief["company_deltas"] if row["id"] == "company-planasa"]
    assert all(bullet["id"] != "ev-cfia-index" for row in planasa_deltas for bullet in row["bullets"])


def test_source_recovery_and_failure_use_last_brief_snapshot(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    tagged = deepcopy(PRIORITY)
    tagged["reading"] = {"level": "high", "rationale": "Need to read."}
    _seed(repos, [_published("ev-brief-src", priority=tagged)])
    _set_last_seen(
        "2026-08-19T08:00:00",
        source_states={
            "source-fresh-plaza": "FAILING",
            "source-growing-produce-berries": "CURRENT",
        },
    )
    freshness = {
        "source-fresh-plaza": {"state": "CURRENT", "last_success_at": "2026-08-19T12:00:00"},
        "source-growing-produce-berries": {"state": "FAILING", "last_success_at": None},
    }
    discovered = [
        {
            "id": "discovered-sanlucar-1",
            "record_type": "discovered_media_item",
            "media_format": "web_article",
            "source_id": "source-sanlucar-newsroom",
            "title": "SanLucar acquires stake in Twin River Berries",
            "first_seen_at": "2026-08-19T12:05:00",
            "published_date": "2026-07-10",
        },
        {
            "id": "discovered-sanlucar-2",
            "record_type": "discovered_media_item",
            "media_format": "web_article",
            "source_id": "source-sanlucar-newsroom",
            "title": "Thinking better with blueberries?",
            "first_seen_at": "2026-08-19T12:05:01",
            "published_date": "2024-03-14",
        },
    ]
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=repos.evidence.list(),
        discovered=discovered,
        freshness_by_source=freshness,
        sources=[
            {"id": "source-fresh-plaza", "label": "Fresh Plaza"},
            {"id": "source-growing-produce-berries", "label": "Growing Produce"},
            {"id": "source-sanlucar-newsroom", "label": "SanLucar newsroom"},
        ],
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
        mark_seen=False,
    )
    labels = [row["label"] for row in brief["source_changes"]]
    assert any("Fresh Plaza recovered" in label for label in labels)
    assert any("Growing Produce" in label and "failing" in label.casefold() for label in labels)
    assert any("SanLucar newsroom produced 2 new items" in label for label in labels)


def test_trust_transition_requires_timestamp_after_last_seen(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    tagged = deepcopy(PRIORITY)
    tagged["reading"] = {"level": "high", "rationale": "Need to read."}
    _seed(
        repos,
        [
            _published(
                "ev-became-trusted",
                title="Planasa trade note",
                reviewed_at="2026-08-19",
                captured_date="2026-08-19",
                published_date="2026-08-19",
                priority=tagged,
            )
        ],
    )
    _set_last_seen("2026-08-18T08:00:00")
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=repos.evidence.list(),
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
        mark_seen=False,
    )
    assert any(row["id"] == "ev-became-trusted" and "trusted" in row["label"].casefold() for row in brief["trust_transitions"])


def test_brief_view_still_does_not_mark_read_after_delta_layer(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    tagged = deepcopy(PRIORITY)
    tagged["reading"] = {"level": "high", "rationale": "Need to read."}
    _seed(repos, [_published("ev-brief-1", priority=tagged)])
    client = TestClient(app)
    page = client.get("/brief")
    assert page.status_code == 200
    assert "Since your last brief" in page.text
    assert "New developments" in page.text
    assert "Important" in page.text
    assert reading_state("ev-brief-1", load_state(main.INBOX_DIR)) == "unread"
