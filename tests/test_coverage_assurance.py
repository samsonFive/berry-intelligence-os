"""Public Intelligence Coverage Assurance V1.

Proves known vs collected vs cited-not-collected, technical health vs
intelligence yield, miss classification, benchmarks that never become
Evidence, and GET/static privacy. No completeness score. No auto-onboard.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.coverage_assurance import (
    COLLECTED,
    ENTITY_FOUND_IDENTITY_UNRESOLVED,
    FORBIDDEN_COMPLETENESS_CLAIMS,
    FULLY_REPRESENTED,
    INTENTIONALLY_EXCLUDED,
    ITEM_COLLECTED_ENTITY_MISSED,
    KNOWN_NOT_COLLECTED,
    SOURCE_COLLECTED_ITEM_MISSED,
    SOURCE_KNOWN_NOT_COLLECTED,
    SOURCE_UNKNOWN,
    UNKNOWN_SOURCE_IDENTITY,
    UNSUPPORTED_NOT_QUALIFYING,
    build_coverage_report,
    classify_result,
)
from app.services.coverage_assurance.universe import load_universe
from app.services.coverage_assurance.yield_status import (
    TECHNICAL_BROKEN,
    TECHNICAL_HEALTHY,
    YIELD_ACTIVE,
    YIELD_DEGRADED,
)
from app.services.recall_audit.classify import hostname
from app.services.source_lifecycle import is_collection_eligible

UTC = timezone.utc
TODAY = date(2026, 8, 31)
REPO = Path(__file__).resolve().parents[1]


def _source(
    source_id: str,
    *,
    url: str,
    eligible: bool = True,
    entity_types: list[str] | None = None,
    berry_ids: list[str] | None = None,
    region: str = "europe",
) -> dict:
    record = {
        "id": source_id,
        "label": source_id,
        "type": "rss",
        "url": url,
        "value": url,
        "enabled": eligible,
        "entity_types": entity_types or ["trade_press"],
        "berry_ids": berry_ids or ["berry-blueberry"],
        "region_coverage": [region],
        "update_cadence": "weekly",
        "discovery": {"adapter": "article_rss", "feed_url": url} if eligible else {},
    }
    if not eligible:
        record["enabled"] = False
        record["lifecycle"] = {"state": "DISABLED", "reason": "test", "changed_at": "2026-08-01T00:00:00+00:00"}
    return record


def _evidence(
    evidence_id: str,
    url: str,
    *,
    source_id: str | None = None,
    captured: str = "2026-08-20",
    entity_ids: list[str] | None = None,
    berry_ids: list[str] | None = None,
) -> dict:
    return {
        "id": evidence_id,
        "status": "published",
        "title": evidence_id,
        "source_url": url,
        "source_id": source_id,
        "captured_date": captured,
        "published_date": captured,
        "entity_ids": entity_ids or [],
        "berry_ids": berry_ids or ["berry-blueberry"],
        "geography_ids": [],
    }


def _universe_entry(host: str, **extra) -> dict:
    row = {
        "id": f"su-{host.replace('.', '-')}",
        "hostname": host,
        "display_name": host,
        "source_class": "trade_press",
        "berry_scope": ["berry-blueberry"],
        "geography": ["eu"],
        "intentionally_excluded": False,
    }
    row.update(extra)
    return row


def _write_universe(data_dir: Path, entries: list[dict]) -> None:
    path = data_dir / "configuration" / "source_universe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 1, "entries": entries}),
        encoding="utf-8",
    )


def _report(tmp_path: Path, **kwargs) -> dict:
    data_dir = kwargs.pop("data_dir", tmp_path / "data")
    data_dir.mkdir(parents=True, exist_ok=True)
    if not (data_dir / "configuration" / "source_universe.json").is_file():
        _write_universe(data_dir, kwargs.pop("universe_entries", []))
    else:
        kwargs.pop("universe_entries", None)
    return build_coverage_report(
        data_dir=data_dir,
        now=TODAY,
        **kwargs,
    )


def test_trusted_evidence_host_actively_collected(tmp_path: Path) -> None:
    source = _source("source-freshplaza", url="https://www.freshplaza.com/rss")
    evidence = [_evidence("ev-1", "https://www.freshplaza.com/article/1", source_id="source-freshplaza")]
    report = _report(
        tmp_path,
        sources=[source],
        published_evidence=evidence,
        universe_entries=[_universe_entry("freshplaza.com")],
    )
    row = next(item for item in report["rows"] if item["hostname"] == "freshplaza.com")
    assert row["collection_status"] == COLLECTED
    assert "freshplaza.com" not in {item["hostname"] for item in report["cited_not_collected"]}


def test_trusted_evidence_host_not_collected_italian_berry(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        sources=[_source("source-other", url="https://www.freshplaza.com/rss")],
        published_evidence=[
            _evidence(
                "ev-italianberry-peru-varieties-2025",
                "https://italianberry.it/en/news/Peru-Sekoya",
                entity_ids=["variety-sekoya-pop"],
                berry_ids=["berry-blueberry"],
            )
        ],
        universe_entries=[_universe_entry("italianberry.it", variety_dense=True, discovery_basis="cited_in_trusted_evidence")],
    )
    row = next(item for item in report["rows"] if item["hostname"] == "italianberry.it")
    assert row["collection_status"] == KNOWN_NOT_COLLECTED
    assert row["hostname"] in {item["hostname"] for item in report["cited_not_collected"]}
    assert "ev-italianberry-peru-varieties-2025" in row["cited_evidence_ids"]


def test_italian_berry_gap_was_closed_on_canonical_corpus() -> None:
    """Originally documented the live failure that prompted this
    mission (cited, not collected). Source Coverage Gap Closure V1
    (2026-09-01) closed it with a real news_search_rss Source, so this
    now documents the fix, not the gap."""
    report = build_coverage_report(
        data_dir=main.DATA_DIR,
        sources=main.load_sources(),
        published_evidence=main.published_evidence(),
        blocked_domains=main.load_blocked_domains(),
        now=TODAY,
    )
    cited = {item["hostname"] for item in report["cited_not_collected"]}
    assert "italianberry.it" not in cited
    collected_hosts = {item["hostname"] for item in report["rows"] if item["collection_status"] == COLLECTED}
    assert "italianberry.it" in collected_hosts
    eligible = [source for source in main.load_sources() if is_collection_eligible(source)]
    assert any("italianberry.it" in (source.get("url") or "") for source in eligible)


def test_intentionally_excluded_host(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        sources=[_source("source-keyword", url="https://news.google.com/rss/search?q=blueberry")],
        published_evidence=[_evidence("ev-g", "https://news.google.com/articles/abc")],
        universe_entries=[
            _universe_entry(
                "news.google.com",
                intentionally_excluded=True,
                exclusion_reason="Redirect host, not a publisher.",
            )
        ],
        blocked_domains=["news.google.com"],
    )
    row = next(item for item in report["rows"] if item["hostname"] == "news.google.com")
    assert row["collection_status"] == INTENTIONALLY_EXCLUDED
    assert "not a publisher" in (row["exclusion_reason"] or "")
    assert "news.google.com" not in {item["hostname"] for item in report["cited_not_collected"]}


def test_technical_healthy_good_yield(tmp_path: Path) -> None:
    source = _source("source-ok", url="https://yield-good.example/rss")
    report = _report(
        tmp_path,
        sources=[source],
        published_evidence=[_evidence("ev-ok", "https://yield-good.example/a", source_id="source-ok")],
        universe_entries=[],
        discovery_states={
            "source-ok": {
                "status": "ok",
                "last_success_at": "2026-08-30T00:00:00+00:00",
                "last_checked_at": "2026-08-30T00:00:00+00:00",
                "new": 2,
            }
        },
    )
    row = next(item for item in report["rows"] if item["hostname"] == "yield-good.example")
    assert row["technical_health"] == TECHNICAL_HEALTHY
    assert row["yield_state"] == YIELD_ACTIVE


def test_technical_healthy_yield_degraded(tmp_path: Path) -> None:
    source = _source("source-quiet", url="https://yield-gone.example/rss")
    report = _report(
        tmp_path,
        sources=[source],
        published_evidence=[
            _evidence(
                "ev-old",
                "https://yield-gone.example/old",
                source_id="source-quiet",
                captured="2026-01-01",
            )
        ],
        universe_entries=[],
        discovery_states={
            "source-quiet": {
                "status": "ok",
                "last_success_at": "2026-08-30T00:00:00+00:00",
                "last_checked_at": "2026-08-30T00:00:00+00:00",
                "new": 0,
            }
        },
    )
    row = next(item for item in report["rows"] if item["hostname"] == "yield-gone.example")
    assert row["technical_health"] == TECHNICAL_HEALTHY
    assert row["yield_state"] == YIELD_DEGRADED
    assert report["yield_degraded_count"] == 1


def test_broken_collector(tmp_path: Path) -> None:
    source = _source("source-fail", url="https://broken.example/rss")
    report = _report(
        tmp_path,
        sources=[source],
        published_evidence=[],
        universe_entries=[],
        discovery_states={
            "source-fail": {
                "status": "error",
                "error": "connection timed out",
                "last_checked_at": "2026-08-30T00:00:00+00:00",
            }
        },
    )
    row = next(item for item in report["rows"] if item["hostname"] == "broken.example")
    assert row["technical_health"] == TECHNICAL_BROKEN
    assert row["collection_status"] == COLLECTED


def test_source_unknown_benchmark_result(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        sources=[],
        published_evidence=[],
        universe_entries=[],
        benchmarks=[
            {
                "id": "bm-unknown",
                "question": "blackberry cultivars Europe",
                "results": [
                    {
                        "url": "https://unknown-press.example/article",
                        "title": "Unknown press",
                        "domain": "unknown-press.example",
                        "qualification": "qualifying",
                    }
                ],
            }
        ],
    )
    scored = report["benchmarks"][0]
    assert scored["counts"][SOURCE_UNKNOWN] == 1
    assert scored["results"][0]["miss_classification"] == SOURCE_UNKNOWN


def test_source_known_item_missed(tmp_path: Path) -> None:
    source = _source("source-ib", url="https://italianberry.it/en/feed")
    report = _report(
        tmp_path,
        sources=[source],
        published_evidence=[],
        universe_entries=[_universe_entry("italianberry.it")],
        discovery_states={
            "source-ib": {
                "status": "ok",
                "last_success_at": "2026-08-30T00:00:00+00:00",
                "last_checked_at": "2026-08-30T00:00:00+00:00",
                "new": 1,
            }
        },
        benchmarks=[
            {
                "id": "bm-item-miss",
                "results": [
                    {
                        "url": "https://italianberry.it/en/news/fresh-blackberries",
                        "title": "Fresh blackberries",
                        "domain": "italianberry.it",
                        "qualification": "qualifying",
                        "matched_source": "source-ib",
                    }
                ],
            }
        ],
    )
    assert report["benchmarks"][0]["counts"][SOURCE_COLLECTED_ITEM_MISSED] == 1


def test_item_collected_entity_missed() -> None:
    evidence = [{"id": "ev-1", "entity_ids": [], "geography_ids": []}]
    miss = classify_result(
        {
            "qualification": "qualifying",
            "matched_evidence_id": "ev-1",
            "expected_entity_id": "variety-victoria",
        },
        sources=[],
        published_evidence=evidence,
        varieties=[],
    )["miss_classification"]
    assert miss == ITEM_COLLECTED_ENTITY_MISSED


def test_unresolved_candidate() -> None:
    evidence = [{"id": "ev-1", "entity_ids": [], "geography_ids": []}]
    miss = classify_result(
        {
            "qualification": "qualifying",
            "matched_evidence_id": "ev-1",
            "expected_entity_id": "variety-clara",
            "matched_candidate_id": "vcand-1",
        },
        sources=[],
        published_evidence=evidence,
        varieties=[],
        candidates=[{"id": "vcand-1", "identity_state": "unknown"}],
    )["miss_classification"]
    assert miss == ENTITY_FOUND_IDENTITY_UNRESOLVED


def test_fully_represented_result() -> None:
    evidence = [{"id": "ev-1", "entity_ids": ["variety-victoria"], "geography_ids": []}]
    miss = classify_result(
        {
            "qualification": "qualifying",
            "matched_evidence_id": "ev-1",
            "expected_entity_id": "variety-victoria",
        },
        sources=[],
        published_evidence=evidence,
        varieties=[],
    )["miss_classification"]
    assert miss == FULLY_REPRESENTED


def test_benchmark_qualification_exclusion() -> None:
    miss = classify_result(
        {"qualification": "not_qualifying", "url": "https://example.invalid/off-topic"},
        sources=[],
        published_evidence=[],
        varieties=[],
    )["miss_classification"]
    assert miss == UNSUPPORTED_NOT_QUALIFYING


def test_coverage_matrix_raw_counts(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        sources=[_source("source-a", url="https://freshplaza.com/rss", berry_ids=["berry-blueberry"])],
        published_evidence=[
            _evidence("ev-ib", "https://italianberry.it/x", berry_ids=["berry-blackberry"]),
        ],
        universe_entries=[
            _universe_entry("italianberry.it", berry_scope=["berry-blackberry"], geography=["eu"]),
        ],
    )
    matrix = report["matrix"]
    assert "percent" not in json.dumps(matrix).casefold()
    assert matrix["totals"]["known_sources"] >= 2
    blackberry = next(row for row in matrix["by_berry"] if row["id"] == "berry-blackberry")
    assert blackberry["cited_but_not_collected"] >= 1
    eu = next(row for row in matrix["by_geography"] if row["id"] == "eu")
    assert eu["cited_but_not_collected"] >= 1
    trade = next(row for row in matrix["by_source_class"] if row["id"] == "trade_press")
    assert trade["known_sources"] >= 1


def test_no_fake_completeness_score(tmp_path: Path) -> None:
    report = _report(tmp_path, sources=[], published_evidence=[], universe_entries=[])
    blob = json.dumps(report).casefold()
    for phrase in FORBIDDEN_COMPLETENESS_CLAIMS:
        assert phrase not in blob
    assert "coverage score" not in blob
    assert report["matrix"]["totals"]["known_sources"] == 0


def test_no_auto_source_onboarding(tmp_path: Path) -> None:
    sources_file = tmp_path / "data" / "configuration" / "sources.json"
    sources_file.parent.mkdir(parents=True, exist_ok=True)
    sources_file.write_text("[]", encoding="utf-8")
    before = sources_file.read_text(encoding="utf-8")
    _report(
        tmp_path,
        data_dir=tmp_path / "data",
        sources=[],
        published_evidence=[_evidence("ev-ib", "https://italianberry.it/x")],
        universe_entries=[_universe_entry("italianberry.it")],
    )
    assert sources_file.read_text(encoding="utf-8") == before
    assert json.loads(before) == []


def test_get_does_not_mutate_trust(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    inbox = tmp_path / "inbox"
    data_dir.mkdir()
    inbox.mkdir()
    (data_dir / "configuration").mkdir()
    (data_dir / "evidence").mkdir()
    (data_dir / "configuration" / "sources.json").write_text("[]", encoding="utf-8")
    _write_universe(data_dir, [_universe_entry("italianberry.it")])
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "load_blocked_domains", lambda: [])
    monkeypatch.setattr(main, "list_drafts_metadata", lambda: [])
    monkeypatch.setattr(main, "list_discovered_items", lambda _inbox: [])
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [], {}))
    before_sources = (data_dir / "configuration" / "sources.json").read_bytes()
    before_universe = (data_dir / "configuration" / "source_universe.json").read_bytes()
    page = TestClient(main.app).get("/coverage-assurance")
    assert page.status_code == 200
    assert "italianberry.it" in page.text
    assert "not a completeness score" in page.text.casefold()
    assert "65%" not in page.text
    assert "coverage score" not in page.text.casefold()
    assert (data_dir / "configuration" / "sources.json").read_bytes() == before_sources
    assert (data_dir / "configuration" / "source_universe.json").read_bytes() == before_universe
    assert not list((data_dir / "evidence").glob("*.json"))
    assert page.status_code == 200


def test_coverage_assurance_is_authoring_only(monkeypatch) -> None:
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    page = TestClient(main.app).get("/coverage-assurance")
    assert page.status_code == 403


def test_no_static_leakage_of_coverage_diagnostics() -> None:
    """Sentinel is planted in test_build_static; this guards the route itself."""
    assert "private-coverage-assurance-benchmark-miss" not in Path(
        REPO / "app" / "templates" / "coverage_assurance.html"
    ).read_text(encoding="utf-8")


def test_variety_liveness_integration(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        sources=[_source("source-a", url="https://freshplaza.com/rss")],
        published_evidence=[
            _evidence(
                "ev-ib",
                "https://italianberry.it/en/news/fresh-blackberries",
                entity_ids=["variety-victoria"],
                berry_ids=["berry-blackberry"],
            )
        ],
        universe_entries=[_universe_entry("italianberry.it", variety_dense=True)],
        variety_candidates=[{"id": "vcand-clara", "status": "proposed", "identity_state": "unknown", "source_url": "https://italianberry.it/x"}],
    )
    variety = report["variety"]
    assert variety["variety_dense_known"] >= 1
    assert any(row["hostname"] == "italianberry.it" for row in variety["cited_variety_hosts_not_collected"])
    assert variety["unresolved_candidates"] == 1


def test_collection_history_compatibility_missing_new(tmp_path: Path) -> None:
    source = _source("source-legacy", url="https://legacy.example/rss")
    report = _report(
        tmp_path,
        sources=[source],
        published_evidence=[_evidence("ev-l", "https://legacy.example/a", source_id="source-legacy")],
        universe_entries=[],
        discovery_states={
            "source-legacy": {
                "status": "ok",
                "last_success_at": "2026-08-30T00:00:00+00:00",
                "last_checked_at": "2026-08-30T00:00:00+00:00",
                # legacy files omit "new"
            }
        },
    )
    row = next(item for item in report["rows"] if item["hostname"] == "legacy.example")
    assert row["technical_health"] == TECHNICAL_HEALTHY
    assert row["yield_state"] == YIELD_ACTIVE


def test_benchmarks_cannot_create_trusted_evidence(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "data" / "evidence"
    evidence_dir.mkdir(parents=True)
    _report(
        tmp_path,
        data_dir=tmp_path / "data",
        sources=[],
        published_evidence=[],
        universe_entries=[],
        benchmarks=[
            {
                "id": "bm-no-trust",
                "results": [
                    {
                        "url": "https://example.invalid/new",
                        "title": "Should not become evidence",
                        "qualification": "qualifying",
                    }
                ],
            }
        ],
    )
    assert list(evidence_dir.glob("*.json")) == []


def test_hostname_matches_domain_of() -> None:
    assert hostname("https://www.ItalianBerry.it/en/news/x") == "italianberry.it"
    assert hostname("https://italianberry.it/en/news/x") == main.domain_of("https://italianberry.it/en/news/x")


def test_known_not_collected_miss_class() -> None:
    source = {
        "id": "source-italianberry",
        "url": "https://italianberry.it/feed",
        "value": "https://italianberry.it/feed",
        "lifecycle": {"state": "DISABLED", "reason": "test", "changed_at": "2026-08-01T00:00:00+00:00"},
        "discovery": {},
    }
    miss = classify_result(
        {"qualification": "qualifying", "url": "https://italianberry.it/x"},
        sources=[source],
        published_evidence=[],
        varieties=[],
    )["miss_classification"]
    assert miss == SOURCE_KNOWN_NOT_COLLECTED


def test_source_universe_seed_has_no_bodies() -> None:
    payload = json.loads((REPO / "data" / "configuration" / "source_universe.json").read_text(encoding="utf-8"))
    blob = json.dumps(payload)
    assert "italianberry.it" in blob
    for entry in payload["entries"]:
        assert "body" not in entry
        assert "article_body" not in entry
        assert "html" not in entry


def test_load_universe_strips_bodies(tmp_path: Path) -> None:
    _write_universe(
        tmp_path,
        [
            {
                **_universe_entry("example.invalid"),
                "body": "should never be kept",
                "article_body": "<p>nope</p>",
            }
        ],
    )
    loaded = load_universe(tmp_path)
    assert "body" not in loaded["entries"][0]
    assert "article_body" not in loaded["entries"][0]


def test_benchmarks_load_from_both_inbox_and_committed_imports(tmp_path: Path) -> None:
    """A committed data/imports/<mission>/benchmark.json (e.g. Independent
    Missed Intelligence Discovery + Recall Audit V1's output) is picked up
    automatically alongside private inbox benchmarks -- this is the
    ingestion path the mission asked for, with no code change needed once
    such a file lands."""
    from app.services.coverage_assurance.benchmarks import load_benchmarks

    inbox_dir = tmp_path / "inbox"
    data_dir = tmp_path / "data"
    (inbox_dir / "coverage_assurance" / "benchmarks").mkdir(parents=True)
    (inbox_dir / "coverage_assurance" / "benchmarks" / "bm-private.json").write_text(
        json.dumps({"id": "bm-private", "results": []}), encoding="utf-8"
    )
    (data_dir / "imports" / "some-mission-v1").mkdir(parents=True)
    (data_dir / "imports" / "some-mission-v1" / "benchmark.json").write_text(
        json.dumps({"id": "bm-committed", "results": [{"reasoning": "should be stripped", "url": "https://example.invalid/x", "qualification": "qualifying"}]}),
        encoding="utf-8",
    )
    loaded = load_benchmarks(inbox_dir, data_dir=data_dir)
    ids = {row["id"] for row in loaded}
    assert ids == {"bm-private", "bm-committed"}
    committed = next(row for row in loaded if row["id"] == "bm-committed")
    assert "reasoning" not in committed["results"][0]


def test_coverage_assurance_route_not_registered_in_build_static() -> None:
    source = Path("scripts/build_static.py").read_text(encoding="utf-8")
    assert "/coverage-assurance" not in source
    assert "coverage_assurance.html" not in source
