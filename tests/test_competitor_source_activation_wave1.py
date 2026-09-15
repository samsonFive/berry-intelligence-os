from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.services import media_discovery
from app.services.company_news_coverage import company_news_coverage
from app.services.competitor_registry import monitoring_state_for_entity
from app.services.media_discovery import discover_source
from app.services.source_freshness import source_execution_status
from app.services.source_lifecycle import is_collection_eligible


ROOT = Path(__file__).resolve().parents[1]
WAVE_PATH = ROOT / "data/imports/competitor-source-strategy-2026-09-15/first-activation-wave.json"
SOURCES_PATH = ROOT / "data/configuration/sources.json"
NEW_SOURCE_IDS = {
    "source-20260915-fruitist-newsroom",
    "source-20260915-oishii-press",
    "source-20260915-ozblu-news",
    "source-20260915-wish-farms-newsroom",
}
BLOCKED_SOURCE_IDS = {
    "source-20260915-ozblu-news",
    "source-20260915-wish-farms-newsroom",
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _entities() -> list[dict]:
    return [_load(path) for path in (ROOT / "data/entities").rglob("*.json")]


def _sources() -> list[dict]:
    return _load(SOURCES_PATH)


def test_all_twelve_wave_entries_resolve_to_canonical_entities() -> None:
    wave = _load(WAVE_PATH)["entries"]
    entity_ids = {row["id"] for row in _entities()}
    assert len(wave) == 12
    assert len({row["canonical_entity_id"] for row in wave}) == 12
    assert {row["canonical_entity_id"] for row in wave} <= entity_ids


def test_existing_sources_are_reused_and_only_four_records_are_created() -> None:
    sources = _sources()
    by_id = {source["id"]: source for source in sources}
    assert len(by_id) == len(sources)
    assert NEW_SOURCE_IDS <= set(by_id)
    linked_entities = {
        entity_id
        for source in sources
        if source["id"] not in NEW_SOURCE_IDS
        for entity_id in source.get("linked_competitor_ids") or []
    }
    expected_existing = {
        "company-advanced-berry-breeding", "company-berryworld",
        "company-costa-group-holdings", "company-fall-creek-farm-and-nursery",
        "company-hortifrut", "company-planasa", "company-university-of-arkansas",
        "company-university-of-florida",
    }
    assert expected_existing <= linked_entities


def test_no_duplicate_source_ids_or_new_normalized_feed_urls() -> None:
    sources = _sources()
    assert len({source["id"] for source in sources}) == len(sources)
    new_urls = {
        (source.get("discovery") or {}).get("feed_url", "").casefold().rstrip("/")
        for source in sources if source["id"] in NEW_SOURCE_IDS
    }
    other_urls = {
        (source.get("discovery") or {}).get("feed_url", "").casefold().rstrip("/")
        for source in sources if source["id"] not in NEW_SOURCE_IDS
    }
    assert len(new_urls) == 4
    assert not (new_urls & other_urls)


def test_new_sources_use_canonical_links_and_retain_candidate_provenance() -> None:
    by_id = {source["id"]: source for source in _sources()}
    expected = {
        "source-20260915-fruitist-newsroom": "company-agrovision",
        "source-20260915-oishii-press": "company-oishii",
        "source-20260915-ozblu-news": "brand-ozblu",
        "source-20260915-wish-farms-newsroom": "company-wish-farms",
    }
    for source_id, entity_id in expected.items():
        source = by_id[source_id]
        assert source["linked_competitor_ids"] == [entity_id]
        assert source["activation"]["candidate_proposal_id"].startswith("PROPOSAL-")
        assert source["activation"]["strategy_commit"] == "da8740cf10660831ecfa5287b15fdb9f6e6c53ee"
        assert source["activation"]["verification_date"] == "2026-09-15"
    assert by_id["source-20260915-ozblu-news"]["entity_types"][0] == "brand"
    assert by_id["source-20260901-blueberrybreeding-newsroom"]["linked_competitor_ids"] == [
        "company-university-of-florida"
    ]


def test_blocked_candidates_cannot_become_runnable() -> None:
    by_id = {source["id"]: source for source in _sources()}
    for source_id in BLOCKED_SOURCE_IDS:
        source = by_id[source_id]
        assert source["lifecycle"]["state"] == "OPERATOR_ACTION_REQUIRED"
        assert not is_collection_eligible(source)
        status = source_execution_status(source, discovery_state=None)
        assert status["state"] == "BLOCKED"
        assert not status["runnable"]
    assert monitoring_state_for_entity(
        "breeding_program-uc-davis-strawberry", sources=[], inbox_dir=ROOT / "inbox"
    )["state"] == "source_blocked"


def test_configured_operational_readable_and_current_are_distinct(tmp_path: Path) -> None:
    source = {
        "id": "source-wave-test", "enabled": True,
        "linked_competitor_ids": ["company-wave-test"],
        "discovery": {"adapter": "article_rss", "feed_url": "https://example.invalid/feed"},
    }
    initial = source_execution_status(source, discovery_state=None)
    assert initial["runnable"] and initial["state"] == "NEVER_RUN"

    state_dir = tmp_path / "discovered_media/_state"
    state_dir.mkdir(parents=True)
    (state_dir / "source-wave-test.json").write_text(json.dumps({
        "source_id": "source-wave-test", "status": "ok",
        "last_checked_at": "2026-09-15T12:00:00+00:00",
        "last_success_at": "2026-09-15T12:00:00+00:00",
    }), encoding="utf-8")
    operational = source_execution_status(
        source,
        discovery_state=json.loads((state_dir / "source-wave-test.json").read_text()),
    )
    assert operational["state"] == "SUCCESSFULLY_RUN"
    assert monitoring_state_for_entity(
        "company-wave-test", sources=[source], inbox_dir=tmp_path
    )["state"] == "linked_to_runnable_source"

    contaminated = {
        "id": "ev-wall", "status": "published", "entity_ids": ["company-wave-test"],
        "published_date": "2026-09-15", "title": "Blocked article",
        "article": {"paragraphs": [{"index": 0, "text": "Verify you are a human. Checking your browser before accessing."}]},
    }
    coverage = company_news_coverage(
        {"id": "company-wave-test", "name": "Wave Test"},
        published=[contaminated], today=__import__("datetime").date(2026, 9, 15),
    )
    assert coverage["usable_count"] == 0


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.text = content.decode("utf-8")
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None


def test_canary_cap_is_applied_before_discovery_persistence(tmp_path: Path, monkeypatch) -> None:
    repos = get_repositories(tmp_path, SCHEMAS_DIR)
    repos.sources.create({
        "id": "source-canary-cap", "type": "rss", "label": "Canary cap",
        "url": "https://example.invalid/", "enabled": True,
        "discovery": {"adapter": "article_rss", "feed_url": "https://example.invalid/feed"},
    })
    items = "".join(
        f"<item><title>Berry item {i}</title><link>https://example.invalid/{i}</link>"
        f"<guid>item-{i}</guid><pubDate>Tue, 15 Sep 2026 12:00:00 GMT</pubDate>"
        f"<description>Berry company news item {i}.</description></item>"
        for i in range(8)
    )
    feed = f"<rss version='2.0'><channel><title>Canary</title>{items}</channel></rss>".encode()
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *args, **kwargs: _FakeResponse(feed))

    result = discover_source(
        "source-canary-cap", inbox_dir=tmp_path / "inbox", data_dir=tmp_path,
        schemas_dir=SCHEMAS_DIR, max_persisted_items=5,
    )

    assert result.found == 8
    assert result.new == 5
    assert len(list((tmp_path / "inbox/discovered_media").glob("discovered-*.json"))) == 5


def test_default_competitor_landscape_source_remains_33_entries() -> None:
    matrix = _load(ROOT / "data/imports/competitor-registry-2026-09-15/reconciliation-matrix.json")
    assert len(matrix["rows"]) == 33
