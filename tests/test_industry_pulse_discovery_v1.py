"""Industry Pulse discovery + news recall V1.

Catch-net only. Reuses the canonical recall taxonomy. GET never publishes
Evidence or onboards Sources. No homepage redesign.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main
from app.services.industry_pulse import (
    audit_freshness,
    discover,
    generate_pulse_queries,
    query_count,
    run_pulse,
)
from app.services.industry_pulse.dedup import dedupe_hits, identity_key
from app.services.industry_pulse.matrix import BERRIES, GEOGRAPHIES, TOPICS
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider, hits_from_news_search_items
from app.services.industry_pulse.qualify import qualify_hit
from app.services.recall_audit.classify import (
    MISS_CLASSES,
    SOURCE_COLLECTED_ITEM_MISSED,
    SOURCE_UNKNOWN,
    UNSUPPORTED_NOT_QUALIFYING,
)

REPO = Path(__file__).resolve().parents[1]
TODAY = date(2026, 9, 1)


def _hit(**kwargs) -> DiscoveryHit:
    row = dict(
        title="Planasa launches new strawberry variety in Spain",
        url="https://www.freshplaza.com/article/planasa-strawberry",
        source_domain="freshplaza.com",
        published_date="2026-09-01",
        snippet="Planasa commercial launch of a new strawberry cultivar for Spanish growers.",
        query_id="pulse:strawberry:europe:7d",
        query_text="strawberry Europe",
        geography="europe",
        berry="strawberry",
        topic="industry_pulse",
        provider="memory",
        origin_publisher_name="FreshPlaza",
        origin_publisher_url="https://www.freshplaza.com/article/planasa-strawberry",
    )
    row.update(kwargs)
    return DiscoveryHit(**row)


def _collected_source(host: str, source_id: str = "source-freshplaza") -> dict:
    url = f"https://www.{host}/rss"
    return {
        "id": source_id,
        "label": host,
        "type": "rss",
        "url": url,
        "value": url,
        "enabled": True,
        "discovery": {"adapter": "article_rss", "feed_url": url},
    }


def test_query_matrix_generation() -> None:
    queries = generate_pulse_queries()
    assert query_count() == 32
    assert len(queries) == 32
    berry_geo = [row for row in queries if row.kind == "berry_geography"]
    topics = [row for row in queries if row.kind == "topic_global"]
    assert len(berry_geo) == 20
    assert len(topics) == 12
    assert {row.berry for row in berry_geo} == set(BERRIES)
    assert {row.geography for row in berry_geo} == set(GEOGRAPHIES)
    assert {row.topic for row in topics} == set(TOPICS)


def test_geography_specific_query() -> None:
    europe = next(row for row in generate_pulse_queries() if row.id == "pulse:blueberry:europe")
    africa = next(row for row in generate_pulse_queries() if row.id == "pulse:blueberry:africa")
    assert "Spain" in europe.text or "Europe" in europe.text
    assert europe.hl == "en-GB"
    assert "South Africa" in africa.text
    assert africa.gl == "ZA"
    assert "when:7d" in europe.with_window("7d").text


def test_berry_specific_query() -> None:
    blueberry = next(row for row in generate_pulse_queries() if row.id == "pulse:blueberry:global")
    blackberry = next(row for row in generate_pulse_queries() if row.id == "pulse:blackberry:apac")
    assert "blueberry" in blueberry.text
    assert "blackberry" in blackberry.text
    assert blueberry.berry == "blueberry"
    assert blackberry.geography == "apac"


def test_topic_query() -> None:
    pbr = next(row for row in generate_pulse_queries() if row.id == "topic:pbr_patent:global")
    assert "PBR" in pbr.text
    assert pbr.berry is None
    assert pbr.geography == "global"


def test_result_normalization() -> None:
    query = next(row for row in generate_pulse_queries() if row.id == "pulse:blueberry:americas").with_window("7d")
    item = SimpleNamespace(
        title="Hortifrut blueberry export update",
        canonical_url="https://news.google.com/rss/articles/ABC",
        published_date="2026-08-31",
        description="Peru blueberry exports",
        raw_metadata={
            "origin_publisher_name": "FreshFruitPortal",
            "origin_publisher_url": "https://www.freshfruitportal.com/news/hortifrut",
        },
    )
    hits = hits_from_news_search_items([item], query=query, provider_name="google_news_rss")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.title == "Hortifrut blueberry export update"
    assert hit.url.endswith("/news/hortifrut") or "freshfruitportal.com" in hit.url
    assert hit.source_domain == "freshfruitportal.com"
    assert hit.published_date == "2026-08-31"
    assert "Peru" in hit.snippet
    assert hit.provider == "google_news_rss"
    assert hit.query_id.endswith(":7d")
    assert hit.geography == "americas"
    assert hit.berry == "blueberry"


def test_unknown_source_classification() -> None:
    report = run_pulse(
        provider=MemoryProvider(
            hits_by_query_id={
                "pulse:blueberry:europe:7d": [
                    _hit(
                        title="Nordic Berry Lab blueberry PBR filing",
                        url="https://www.unknown-berry-times.example/pbr",
                        source_domain="unknown-berry-times.example",
                        origin_publisher_url="https://www.unknown-berry-times.example/pbr",
                        geography="europe",
                        berry="blueberry",
                    )
                ]
            }
        ),
        sources=[_collected_source("freshplaza.com")],
        published_evidence=[],
        today=TODAY,
    )
    assert report["windows"]["7d"]["qualifying"] == 1
    assert report["novel_source_count"] == 1
    assert report["hits"][0]["miss_classification"] == SOURCE_UNKNOWN


def test_known_source_new_item() -> None:
    report = run_pulse(
        provider=MemoryProvider(
            hits_by_query_id={
                "pulse:strawberry:europe:7d": [
                    _hit(
                        title="Planasa launches new strawberry variety in Spain",
                        url="https://www.freshplaza.com/article/brand-new-2026",
                        origin_publisher_url="https://www.freshplaza.com/article/brand-new-2026",
                    )
                ]
            }
        ),
        sources=[_collected_source("freshplaza.com")],
        published_evidence=[
            {
                "id": "ev-old",
                "status": "published",
                "source_url": "https://www.freshplaza.com/article/old",
                "title": "Old item",
                "published_date": "2026-01-01",
            }
        ],
        today=TODAY,
    )
    assert report["known_source_item_missed_count"] == 1
    assert report["hits"][0]["miss_classification"] == SOURCE_COLLECTED_ITEM_MISSED


def test_duplicate_url() -> None:
    first = _hit(query_id="pulse:strawberry:europe:7d")
    second = _hit(query_id="topic:commercial_launch:global:7d")
    out = dedupe_hits([first, second])
    assert out[0].duplicate_of is None
    assert out[1].duplicate_of is not None
    assert identity_key(first) == identity_key(second)


def test_syndicated_item_same_publisher() -> None:
    google = _hit(
        url="https://news.google.com/rss/articles/XYZ",
        wrapper_url="https://news.google.com/rss/articles/XYZ",
        source_domain="freshplaza.com",
        origin_publisher_url="https://www.freshplaza.com/article/planasa-strawberry",
        query_id="pulse:strawberry:global:7d",
    )
    direct = _hit(query_id="pulse:strawberry:europe:7d")
    out = dedupe_hits([google, direct])
    assert sum(1 for hit in out if hit.duplicate_of) == 1


def test_distinct_publishers_not_collapsed() -> None:
    a = _hit()
    b = _hit(
        url="https://www.fruitnet.com/article/planasa-strawberry",
        source_domain="fruitnet.com",
        origin_publisher_url="https://www.fruitnet.com/article/planasa-strawberry",
        origin_publisher_name="Fruitnet",
    )
    out = dedupe_hits([a, b])
    assert all(hit.duplicate_of is None for hit in out)


def test_dedupe_prefers_regional_geography_over_global() -> None:
    global_hit = _hit(geography="global", query_id="pulse:strawberry:global:7d")
    europe_hit = _hit(geography="europe", query_id="pulse:strawberry:europe:7d")
    out = dedupe_hits([global_hit, europe_hit])
    unique = [hit for hit in out if not hit.duplicate_of]
    assert len(unique) == 1
    assert unique[0].geography == "europe"
    assert global_hit.duplicate_of is not None


def test_publication_date_window() -> None:
    report = run_pulse(
        provider=MemoryProvider(
            hits_by_query_id={
                "pulse:strawberry:europe:7d": [
                    _hit(published_date="2026-09-01"),
                    _hit(
                        title="Older strawberry harvest report from Spain",
                        url="https://www.freshplaza.com/article/older",
                        origin_publisher_url="https://www.freshplaza.com/article/older",
                        published_date="2026-08-28",
                    ),
                ]
            }
        ),
        sources=[],
        published_evidence=[],
        today=TODAY,
    )
    assert report["windows"]["24h"]["discovered"] == 1
    assert report["windows"]["3d"]["discovered"] == 1
    assert report["windows"]["7d"]["discovered"] == 2


def test_unknown_date_excluded_from_windows() -> None:
    report = run_pulse(
        provider=MemoryProvider(
            hits_by_query_id={
                "pulse:strawberry:europe:7d": [_hit(published_date=None)]
            }
        ),
        sources=[],
        published_evidence=[],
        today=TODAY,
    )
    assert report["windows"]["24h"]["discovered"] == 0
    assert report["windows"]["7d"]["discovered"] == 0
    assert report["windows"]["7d"]["unknown_date"] == 1


def test_non_qualifying_result_rejection() -> None:
    recipe = qualify_hit(
        _hit(title="10 blueberry smoothie recipes for summer", snippet="Calories and yogurt bowls")
    )
    assert recipe.qualifying is False
    promo = qualify_hit(_hit(title="Blueberries on sale this week", snippet="Weekly ad club card specials"))
    assert promo.qualifying is False
    fluff = qualify_hit(
        _hit(
            title="Hyte releases new strawberry-colored PC case with affordable price tag",
            snippet="launch of a computer case",
            berry="strawberry",
        )
    )
    assert fluff.qualifying is False
    device = qualify_hit(
        _hit(
            title="IP Litigation Insider: All about Key Patent Innovation's BlackBerry bet",
            snippet="patent litigation smartphone",
            berry="blackberry",
        )
    )
    assert device.qualifying is False
    harvest_festival = qualify_hit(
        _hit(
            title="Barenaked Ladies lead 2026 Harvest Music Festival",
            snippet="blackberry stage lineup",
            berry="blackberry",
        )
    )
    assert harvest_festival.qualifying is False
    jewel_pet = qualify_hit(
        _hit(
            title="Meet Raspberry and Jewels, this week's CVAS pets of the week",
            snippet="animal shelter",
            berry="raspberry",
        ),
        variety_names=["Jewel"],
    )
    assert jewel_pet.qualifying is False
    good = qualify_hit(_hit(), company_names=["Planasa"])
    assert good.qualifying is True
    pairwise = qualify_hit(
        _hit(
            title="Pairwise's seedless cherries and blackberries could revolutionise the future of food",
            snippet="gene edited blackberry fruit",
            berry="blackberry",
            source_domain="smartcherry.world",
        )
    )
    assert pairwise.qualifying is True


def test_regional_and_berry_balance() -> None:
    catalog = {}
    for berry in BERRIES:
        for geography in GEOGRAPHIES:
            catalog[f"pulse:{berry}:{geography}:7d"] = [
                _hit(
                    title=f"{berry.title()} harvest and export update in {geography}",
                    url=f"https://www.{geography}-{berry}.example/{berry}-export",
                    source_domain=f"{geography}-{berry}.example",
                    origin_publisher_url=f"https://www.{geography}-{berry}.example/{berry}-export",
                    geography=geography,
                    berry=berry,
                    snippet=f"{berry} export acreage harvest {geography}",
                )
            ]
    report = run_pulse(
        provider=MemoryProvider(hits_by_query_id=catalog),
        sources=[],
        published_evidence=[],
        today=TODAY,
    )
    geo = report["windows"]["7d"]["by_geography"]
    berry = report["windows"]["7d"]["by_berry"]
    assert all(geo[name]["qualifying"] >= 1 for name in GEOGRAPHIES)
    assert all(berry[name]["qualifying"] >= 1 for name in BERRIES)
    total = report["windows"]["7d"]["qualifying"]
    assert geo["americas"]["qualifying"] < total
    assert berry["blueberry"]["qualifying"] < total
    query_geo = report["windows"]["7d"]["query_yield_by_geography"]
    assert all(query_geo[name]["qualifying"] >= 1 for name in GEOGRAPHIES)


def test_no_auto_trust(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "data" / "evidence"
    evidence_dir.mkdir(parents=True)
    sources_path = tmp_path / "data" / "configuration" / "sources.json"
    sources_path.parent.mkdir(parents=True)
    sources_path.write_text("[]", encoding="utf-8")
    report = run_pulse(
        provider=MemoryProvider(
            hits_by_query_id={"pulse:strawberry:europe:7d": [_hit()]}
        ),
        sources=[],
        published_evidence=[],
        today=TODAY,
        persist_dir=tmp_path / "inbox",
    )
    assert report["auto_trust"] is False
    assert report["persisted_bodies"] is False
    assert list(evidence_dir.glob("*.json")) == []
    snapshot = (tmp_path / "inbox" / "industry_pulse" / "latest.json").read_text(encoding="utf-8")
    assert "article_body" not in snapshot
    assert "<html" not in snapshot.casefold()


def test_no_static_leakage() -> None:
    source = (REPO / "scripts" / "build_static.py").read_text(encoding="utf-8")
    assert "/industry-pulse" not in source
    assert "industry_pulse.html" not in source
    feed = (REPO / "app" / "templates" / "feed.html").read_text(encoding="utf-8")
    today = (REPO / "app" / "templates" / "today.html").read_text(encoding="utf-8")
    assert "/industry-pulse" not in feed
    assert "/industry-pulse" not in today


def test_recall_taxonomy_reuse() -> None:
    from app.services.industry_pulse.novelty import classify_hit

    hit = classify_hit(
        qualify_hit(_hit(title="Blueberry muffin recipe", snippet="dessert calories")),
        sources=[],
        published_evidence=[],
    )
    assert hit.miss_classification == UNSUPPORTED_NOT_QUALIFYING
    assert hit.miss_classification in MISS_CLASSES
    assert "NOT_QUALIFYING_PULSE" not in MISS_CLASSES


def test_provider_adapter_substitution() -> None:
    seed = {
        "pulse:raspberry:africa:7d": [
            _hit(
                title="South Africa raspberry export prices rise",
                url="https://www.farmersweekly.co.za/raspberry-export",
                source_domain="farmersweekly.co.za",
                origin_publisher_url="https://www.farmersweekly.co.za/raspberry-export",
                geography="africa",
                berry="raspberry",
                snippet="raspberry export prices South Africa growers",
            )
        ]
    }

    class FakeExa:
        name = "exa"

        def discover(self, query):
            return MemoryProvider(name="exa", hits_by_query_id=seed).discover(query)

    memory = run_pulse(
        provider=MemoryProvider(hits_by_query_id=seed),
        sources=[],
        published_evidence=[],
        today=TODAY,
    )
    exa = run_pulse(provider=FakeExa(), sources=[], published_evidence=[], today=TODAY)
    assert memory["windows"]["7d"]["qualifying"] == exa["windows"]["7d"]["qualifying"] == 1
    assert memory["provider"] == "memory"
    assert exa["provider"] == "exa"
    ad_hoc = discover(
        "raspberry South Africa export",
        date_window="7d",
        geography="africa",
        berry="raspberry",
        topic="trade",
        provider=MemoryProvider(hits=seed["pulse:raspberry:africa:7d"]),
    )
    assert ad_hoc[0].provider == "memory"
    assert ad_hoc[0].geography == "africa"


def test_freshness_does_not_use_captured_date_as_publication() -> None:
    report = audit_freshness(
        sources=[],
        published_evidence=[
            {
                "id": "ev-stale-pub",
                "title": "Old story captured today",
                "published_date": "2026-06-01",
                "captured_date": "2026-09-01",
                "status": "published",
                "berry_ids": ["berry-blueberry"],
                "geography_ids": ["geography-united-states"],
            }
        ],
        today=TODAY,
    )
    assert report["newest_trusted_evidence"]["published_date"] == "2026-06-01"
    assert report["newest_captured_date_on_evidence"]["captured_date"] == "2026-09-01"
    assert report["capture_is_not_publication"] is True


def test_industry_pulse_authoring_only(monkeypatch) -> None:
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    page = TestClient(main.app).get("/industry-pulse")
    assert page.status_code == 403
    posted = TestClient(main.app).post("/industry-pulse/run", follow_redirects=False)
    assert posted.status_code == 403


def test_industry_pulse_get_is_read_only(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    inbox = tmp_path / "inbox"
    (data_dir / "configuration").mkdir(parents=True)
    (data_dir / "evidence").mkdir()
    (data_dir / "configuration" / "sources.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "list_drafts_metadata", lambda: [])
    monkeypatch.setattr(main, "list_discovered_items", lambda _inbox: [])
    called = {"run": 0}

    def _boom(*_args, **_kwargs):
        called["run"] += 1
        raise AssertionError("GET must not run the catch-net")

    monkeypatch.setattr(main, "run_pulse", _boom)
    page = TestClient(main.app).get("/industry-pulse")
    assert page.status_code == 200
    assert called["run"] == 0
    assert "Catch-net discovery" in page.text
    assert "never publishes Evidence" in page.text
    assert list((data_dir / "evidence").glob("*.json")) == []


def test_industry_pulse_post_does_not_write_evidence(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    inbox = tmp_path / "inbox"
    (data_dir / "evidence").mkdir(parents=True)
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_entities", lambda: [])
    monkeypatch.setattr(main, "list_drafts_metadata", lambda: [])
    monkeypatch.setattr(main, "list_discovered_items", lambda _inbox: [])
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [], {}))

    def _fake_run(**kwargs):
        assert kwargs.get("persist_dir") == inbox
        return {"auto_trust": False}

    monkeypatch.setattr(main, "run_pulse", _fake_run)
    resp = TestClient(main.app).post("/industry-pulse/run", follow_redirects=False)
    assert resp.status_code == 303
    assert list((data_dir / "evidence").glob("*.json")) == []
    get_run = TestClient(main.app).get("/industry-pulse/run")
    assert get_run.status_code == 405
