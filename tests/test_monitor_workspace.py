"""V2 Monitor workspace: Watches inventory, Alerts action, Source Health."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.analyst_queue import work_counts
from app.services.monitor_workspace import (
    enrich_watch_items,
    failing_source_health_rows,
    group_source_health,
    present_monitor_alerts,
    present_source_health_rows,
)
from app.services.source_freshness import BLOCKED, FAILING, MANUAL, QUIET, classify_source_freshness


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
    (tmp_path / "data" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "signals").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "entities" / "companies").mkdir(parents=True, exist_ok=True)
    main._NAV_WORK_CACHE["key"] = None
    main._NAV_WORK_CACHE["value"] = None


def _published(record_id: str, **overrides) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "news_search",
        "source_name": "FreshPlaza",
        "title": record_id,
        "summary": "Fixture.",
        "published_date": "2026-08-18",
        "captured_date": "2026-08-18",
        "priority": deepcopy(PRIORITY),
        "entity_ids": [],
        "berry_ids": ["berry-blueberry"],
    }
    record.update(overrides)
    return record


def _seed_entity(tmp_path: Path, entity_id: str, *, entity_type: str, name: str) -> None:
    folder = {
        "company": "companies",
        "variety": "varieties",
        "geography": "geographies",
        "person": "people",
    }[entity_type]
    _write(
        tmp_path / "data" / "entities" / folder / f"{entity_id}.json",
        {
            "id": entity_id,
            "record_type": "entity",
            "entity_type": entity_type,
            "name": name,
            "status": "active",
        },
    )


def test_enrich_watch_uses_stored_entities_not_prose() -> None:
    entities = {
        "company-planasa": {"id": "company-planasa", "entity_type": "company", "name": "Planasa"},
        "geography-mexico": {"id": "geography-mexico", "entity_type": "geography", "name": "Mexico"},
    }
    watch = {
        "id": "ev-watch-planasa",
        "title": "Mexico strawberry tariffs mentioned in passing",
        "watch_what": "Mexico strawberry tariffs mentioned in passing",
        "watch_why": "Watch Planasa licensing, not the geography headline.",
        "entity_ids": ["company-planasa"],
        "berry_ids": ["berry-strawberry"],
        "workflow_state": "active",
        "last_signal": "",
    }
    activity = _published(
        "ev-later",
        title="Planasa files a new variety",
        entity_ids=["company-planasa"],
        published_date="2026-08-20",
    )
    rows = enrich_watch_items(
        [watch],
        entities=entities,
        berry_labels=main.BERRIES,
        published=[activity],
        last_seen_at="2026-08-19",
    )
    assert rows[0]["watched_entities"][0]["name"] == "Planasa"
    assert rows[0]["watched_entities"][0]["entity_type"] == "company"
    assert rows[0]["new_since_last_count"] == 1
    assert rows[0]["last_development"] == "Planasa files a new variety"


def test_alerts_are_action_not_watch_inventory() -> None:
    state = {"signals": {}, "monitoring": {}}
    watches = [
        {
            "id": "ev-watch-1",
            "watch_what": "Planasa",
            "watched_entities": [{"id": "company-planasa", "name": "Planasa", "entity_type": "company"}],
            "new_since_last_count": 2,
            "recent_activity": [{"id": "ev-later"}],
        }
    ]
    signals = [{"id": "sig-open", "title": "Proposed licensing", "status": "proposed", "evidence_ids": ["ev-watch-1"]}]
    candidates = [
        {
            "id": "cand-1",
            "title": "Repeated activity",
            "status": "proposed",
            "entity_ids": ["company-planasa"],
        }
    ]
    groups = {group["key"]: group for group in present_monitor_alerts(signals=signals, state=state, watches=watches, candidates=candidates)}
    assert groups["signals"]["count"] == 1
    assert groups["candidates"]["items"][0]["decision_href"].startswith("/signals/candidates/cand-1")
    assert groups["watch_activity"]["count"] == 1
    assert "action" in groups["signals"]["copy"].lower()
    assert "inventory" not in groups["signals"]["copy"].lower()
    assert "Watch never confirms" in groups["candidates"]["copy"]


def test_source_health_distinguishes_quiet_failing_blocked_manual() -> None:
    sources = [
        {"id": "source-quiet", "label": "Quiet trade", "entity_types": ["trade_press"], "berry_ids": ["berry-blueberry"], "region_coverage": ["global"], "update_cadence": "weekly", "discovery": {"adapter": "article_rss", "feed_url": "https://example.invalid/feed"}},
        {"id": "source-fail", "label": "Failing register", "entity_types": ["government_regulatory"], "berry_ids": ["berry-strawberry"], "region_coverage": ["north_america"], "update_cadence": "weekly", "discovery": {"adapter": "government_register_json", "feed_url": "https://example.invalid/json"}},
        {"id": "source-block", "label": "Blocked press", "entity_types": ["trade_press"], "discovery": {"adapter": "news_search_rss", "feed_url": "https://example.invalid/news"}},
        {"id": "source-manual", "label": "Reference only", "entity_types": ["trade_association"]},
    ]
    freshness = {
        "source-quiet": classify_source_freshness(sources[0], discovery_state={"status": "ok", "last_success_at": "2026-08-20", "new": 0}).as_dict(),
        "source-fail": classify_source_freshness(sources[1], discovery_state={"status": "error", "error": "timeout"}).as_dict(),
        "source-block": classify_source_freshness(sources[2], discovery_state={"status": "error", "error": "403 Forbidden"}).as_dict(),
        "source-manual": classify_source_freshness(sources[3], discovery_state=None).as_dict(),
    }
    assert freshness["source-quiet"]["state"] == QUIET
    assert freshness["source-fail"]["state"] == FAILING
    assert freshness["source-block"]["state"] == BLOCKED
    assert freshness["source-manual"]["state"] == MANUAL
    rows = present_source_health_rows(
        sources,
        freshness_by_source=freshness,
        entity_type_labels=main.SOURCE_ENTITY_TYPES,
        berry_labels=main.BERRIES,
        region_labels=main.SOURCE_REGIONS,
        cadence_labels=main.SOURCE_CADENCES,
    )
    grouped = {group["state"]: group for group in group_source_health(rows)}
    assert grouped[QUIET]["items"][0]["label"] == "Quiet trade"
    assert grouped[FAILING]["items"][0]["source_class_labels"] == ["Government / Regulatory / Statistical Agency"]
    assert grouped[BLOCKED]["count"] == 1
    assert grouped[MANUAL]["items"][0]["discoverable"] is False
    html_labels = " ".join(group["copy"] for group in group_source_health(rows))
    assert "recall" not in html_labels.lower()


def test_failing_source_rows_do_not_need_discovered_item_scan(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    (inbox / "discovered_media" / "_state").mkdir(parents=True)
    source = {
        "id": "source-fail",
        "label": "Failing",
        "discovery": {"adapter": "article_rss", "feed_url": "https://example.invalid/feed"},
    }
    _write(
        inbox / "discovered_media" / "_state" / "source-fail.json",
        {"status": "error", "error": "timeout", "last_checked_at": "2026-08-21"},
    )
    rows = failing_source_health_rows([source], inbox_dir=inbox)
    assert rows[0]["freshness"]["state"] == FAILING


def test_watches_page_is_v2_inventory_and_opens_reader(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entity(tmp_path, "company-planasa", entity_type="company", name="Planasa")
    priority = deepcopy(PRIORITY)
    priority["monitoring"] = {"level": "high", "rationale": "Licensing intent."}
    repos.evidence.create(
        _published(
            "ev-watch-1",
            title="Watch Planasa",
            entity_ids=["company-planasa"],
            priority=priority,
        )
    )
    repos.evidence.create(
        _published(
            "ev-later",
            title="Planasa later filing",
            entity_ids=["company-planasa"],
            published_date="2026-08-21",
        )
    )
    _write(
        tmp_path / "data" / "signals" / "sig-proposed-1.json",
        {
            "id": "sig-proposed-1",
            "record_type": "signal",
            "title": "Proposed licensing signal",
            "status": "proposed",
            "direction": "emerging",
            "strength": "medium",
            "evidence_ids": ["ev-watch-1"],
            "reviewer": None,
            "proposed_at": "2026-08-18",
        },
    )
    client = TestClient(app)
    page = client.get("/queues/monitoring")
    assert page.status_code == 200
    html = page.text
    assert "active watches" in html
    assert "new signal" in html
    assert "MONITOR — INVENTORY" in html
    assert "v2-watch-card" in html
    assert 'id="alerts"' in html
    assert "v2-alert-card" in html
    assert "data-open-reader" in html
    assert "data-intel-card" in html
    assert "/signals/sig-proposed-1" in html
    assert "queue-table" not in html
    assert "KPI" not in html
    dismissed = client.post(
        "/signals/sig-proposed-1/alert-decision",
        data={"action": "dismiss", "reviewer": "analyst-fixture"},
        follow_redirects=False,
    )
    assert dismissed.status_code == 303
    assert dismissed.headers["location"].endswith("/queues/monitoring#alerts")


def test_source_health_page_is_v2_and_uses_generic_classes(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    _write(
        tmp_path / "data" / "configuration" / "sources.json",
        [
            {
                "id": "source-federal-register-strawberry-antidumping",
                "type": "rss",
                "label": "Federal Register fixture",
                "value": "https://www.federalregister.gov/api/v1/documents.json",
                "entity_types": ["government_regulatory"],
                "berry_ids": ["berry-strawberry"],
                "region_coverage": ["north_america"],
                "monitoring_priority": "high",
                "update_cadence": "weekly",
                "enabled": True,
                "discovery": {
                    "adapter": "government_register_json",
                    "feed_url": "https://www.federalregister.gov/api/v1/documents.json",
                },
            },
            {
                "id": "source-google-news-driscolls",
                "type": "rss",
                "label": "Google News Driscoll fixture",
                "value": "https://news.google.com/rss/search?q=Driscoll",
                "entity_types": ["trade_press"],
                "berry_ids": ["berry-strawberry", "berry-blueberry"],
                "region_coverage": ["global"],
                "monitoring_priority": "high",
                "update_cadence": "realtime",
                "enabled": True,
                "discovery": {
                    "adapter": "news_search_rss",
                    "feed_url": "https://news.google.com/rss/search?q=Driscoll",
                },
            },
        ],
    )
    client = TestClient(app)
    page = client.get("/sources")
    assert page.status_code == 200
    html = page.text
    assert "Source Health" in html
    assert "not intelligence recall" in html.lower() or "not intelligence recall" in html
    assert "SOURCE HEALTH" in html
    assert "SOURCE COVERAGE" not in html
    assert "Government / Regulatory" in html
    assert "Trade Press / News Outlet" in html
    assert "Not configured for discovery" in html
    assert "Healthy but quiet" in html
    assert "v2-health-row" in html
    assert "source-federal-register-strawberry-antidumping" in html
    assert html.lower().count("recall") >= 1
    assert "volume means recall" not in html.lower()


def test_monitor_pages_do_not_rank_brief(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    modes: list[str] = []
    original = main.build_morning_brief
    original_semantics = main.annotate_feed_semantics
    original_discovered = main.list_discovered_items
    semantics_calls: list[str] = []
    discovered_calls: list[str] = []

    def wrapped(*args, **kwargs):
        modes.append(str(kwargs.get("mode") or "full"))
        return original(*args, **kwargs)

    def wrapped_semantics(*args, **kwargs):
        semantics_calls.append("called")
        return original_semantics(*args, **kwargs)

    def wrapped_discovered(*args, **kwargs):
        discovered_calls.append("called")
        return original_discovered(*args, **kwargs)

    monkeypatch.setattr(main, "build_morning_brief", wrapped)
    monkeypatch.setattr(main, "annotate_feed_semantics", wrapped_semantics)
    monkeypatch.setattr(main, "list_discovered_items", wrapped_discovered)
    client = TestClient(app)
    assert client.get("/queues/monitoring").status_code == 200
    assert modes == []
    assert semantics_calls == []
    assert discovered_calls == []
    assert client.get("/sources").status_code == 200
    assert modes == []
    assert discovered_calls == ["called"]
    counts = work_counts(inbox_dir=main.INBOX_DIR, published=[], signals=[])
    assert counts["monitoring_inventory"] == 0
    assert counts["signal_alerts"] == 0
