"""Perplexity Semantic Pulse Activation V1.

Covers the mission's own 16-item test list: Perplexity disabled -> Google
only; enabled + key -> union; enabled + missing key -> graceful fallback;
timeout; 429; provider failure isolation; cross-provider dedup; provenance
retained; unknown Source stays untrusted; source URL required; no
proprietary marker leakage; no trust mutation; Front Page fresh-item
compatibility; Coverage Assurance compatibility; cost/run telemetry; no
static leak.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.industry_pulse.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.services.industry_pulse.matrix import catch_net_queries, generate_pulse_queries
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider
from app.services.industry_pulse.run import run_pulse

TODAY = date(2026, 9, 1)

# A title with enough real industry-term density to pass qualify_hit's
# deterministic filter without needing to import its internal regex tables.
QUALIFYING_TITLE = "New blueberry variety launch: breeder announces licensing and PBR patent acreage expansion"


def _hit(url: str, *, provider: str, title: str = QUALIFYING_TITLE, geography: str = "americas", berry: str = "blueberry") -> DiscoveryHit:
    return DiscoveryHit(
        title=title,
        url=url,
        source_domain="freshplaza.com",
        published_date="2026-08-30",
        snippet="",
        query_id="q",
        query_text="",
        geography=geography,
        berry=berry,
        topic="industry_pulse",
        provider=provider,
        origin_publisher_url=url,
    )


@dataclass
class _RaisingProvider:
    name: str
    exc: Exception

    def discover(self, query):
        raise self.exc


@dataclass
class _UnavailableProvider:
    name: str = "perplexity"

    def discover(self, query):
        raise ProviderAuthError("PERPLEXITY_API_KEY is not configured")

    def available(self) -> bool:
        return False


def _base_kwargs(**overrides) -> dict:
    kwargs = dict(sources=[], published_evidence=[], today=TODAY)
    kwargs.update(overrides)
    return kwargs


# 1. Perplexity disabled -> Google only.
def test_no_catch_net_provider_reproduces_google_only_behavior() -> None:
    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://freshplaza.com/a", provider="x")])
    report = run_pulse(provider=google, **_base_kwargs())
    assert report["catch_net_provider"] is None
    assert set(report["provider_telemetry"]) == {"google_news_rss"}
    assert report["provider_telemetry"]["google_news_rss"]["queries_issued"] == 32


# 2. Perplexity enabled + key -> union.
def test_catch_net_provider_merges_into_union() -> None:
    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://freshplaza.com/a", provider="x")])
    perplexity = MemoryProvider(name="perplexity", hits=[_hit("https://freshplaza.com/b", provider="x")])
    report = run_pulse(provider=google, catch_net_provider=perplexity, **_base_kwargs())
    assert report["catch_net_provider"] == "perplexity"
    assert report["union_unique_count"] == 2
    assert report["provider_telemetry"]["perplexity"]["queries_issued"] == len(
        catch_net_queries(generate_pulse_queries())
    )


# 3. Enabled + missing key -> graceful fallback (via the .available() pre-check).
def test_missing_credential_falls_back_to_google_only_without_crash() -> None:
    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://freshplaza.com/a", provider="x")])
    report = run_pulse(provider=google, catch_net_provider=_UnavailableProvider(), **_base_kwargs())
    assert report["provider_telemetry"]["perplexity"]["queries_issued"] == 0
    assert any(f["provider"] == "perplexity" for f in report["query_failures"])
    assert report["windows"]["7d"]["discovered"] >= 0  # report still fully built, no crash


# 4. Perplexity timeout.
def test_provider_timeout_is_isolated(monkeypatch) -> None:
    google = MemoryProvider(name="google_news_rss", hits=[])
    failing = _RaisingProvider(name="perplexity", exc=ProviderTimeoutError("timed out"))
    report = run_pulse(provider=google, catch_net_provider=failing, **_base_kwargs())
    errors = report["provider_telemetry"]["perplexity"]["errors"]
    assert errors == len(catch_net_queries(generate_pulse_queries()))
    assert report["as_of"] == TODAY.isoformat()


# 5. Perplexity 429.
def test_provider_rate_limit_is_isolated() -> None:
    google = MemoryProvider(name="google_news_rss", hits=[])
    failing = _RaisingProvider(name="perplexity", exc=ProviderRateLimitError("429"))
    report = run_pulse(provider=google, catch_net_provider=failing, **_base_kwargs())
    assert report["provider_telemetry"]["perplexity"]["errors"] == len(
        catch_net_queries(generate_pulse_queries())
    )
    assert "ProviderRateLimitError" in report["query_failures"][0]["error"]


# 6. Provider failure isolation -- Google results are unaffected by a total
# catch-net failure.
def test_catch_net_failure_never_reduces_primary_provider_results() -> None:
    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://freshplaza.com/a", provider="x")])
    failing = _RaisingProvider(name="perplexity", exc=RuntimeError("boom"))
    without_catch_net = run_pulse(provider=google, **_base_kwargs())
    with_failing_catch_net = run_pulse(provider=google, catch_net_provider=failing, **_base_kwargs())
    assert (
        with_failing_catch_net["windows"]["7d"]["discovered"]
        == without_catch_net["windows"]["7d"]["discovered"]
    )


# 7. Cross-provider dedup.
def test_same_url_from_both_providers_collapses_to_one_item() -> None:
    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://freshplaza.com/shared", provider="x")])
    perplexity = MemoryProvider(name="perplexity", hits=[_hit("https://freshplaza.com/shared", provider="x")])
    report = run_pulse(provider=google, catch_net_provider=perplexity, **_base_kwargs())
    assert report["union_unique_count"] == 1
    assert report["windows"]["7d"]["qualifying"] == 1
    assert report["overlap_qualifying_count"] == 1


# 8. Provenance retained.
def test_provider_provenance_retained_on_hits() -> None:
    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://freshplaza.com/a", provider="x")])
    perplexity = MemoryProvider(name="perplexity", hits=[_hit("https://freshplaza.com/b", provider="x")])
    report = run_pulse(provider=google, catch_net_provider=perplexity, **_base_kwargs())
    providers_seen = {row["provider"] for row in report["hits"]}
    assert providers_seen == {"google_news_rss", "perplexity"}


# 9. Unknown Source stays untrusted.
def test_perplexity_hit_never_becomes_known_or_auto_trusted() -> None:
    google = MemoryProvider(name="google_news_rss", hits=[])
    perplexity = MemoryProvider(name="perplexity", hits=[_hit("https://a-brand-new-outlet.example/x", provider="x")])
    report = run_pulse(provider=google, catch_net_provider=perplexity, **_base_kwargs())
    assert report["auto_trust"] is False
    hit = next(row for row in report["hits"] if row["provider"] == "perplexity")
    assert hit["known_source"] is False


# 10. Source URL required.
def test_hit_without_url_is_not_returned() -> None:
    from app.services.industry_pulse.providers import hits_from_web_rows
    from app.services.industry_pulse.matrix import generate_pulse_queries

    query = generate_pulse_queries()[0].with_window("7d")
    rows = [{"title": "No URL here", "url": "", "published_date": "2026-08-30", "snippet": ""}]
    hits = hits_from_web_rows(rows, query=query, provider_name="perplexity")
    assert hits == []


# 11. No proprietary marker leakage -- applied to the ACTUAL production
# catch-net query subset run_pulse() sends, not just the bake-off's own
# separate slices.py queries.
def test_catch_net_queries_never_contain_proprietary_markers() -> None:
    proprietary_tokens = ("Assessment", "Signal review", "Fact statement", "analyst notes", "private report")
    selected = catch_net_queries([q.with_window("7d") for q in generate_pulse_queries()])
    assert selected, "catch-net routing must select at least one query"
    for query in selected:
        for token in proprietary_tokens:
            assert token.lower() not in query.text.lower()


# 12. No trust mutation.
def test_combined_run_never_writes_evidence_or_sources(tmp_path: Path) -> None:
    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://freshplaza.com/a", provider="x")])
    perplexity = MemoryProvider(name="perplexity", hits=[_hit("https://freshplaza.com/b", provider="x")])
    inbox = tmp_path / "inbox"
    report = run_pulse(
        provider=google, catch_net_provider=perplexity, persist_dir=inbox, **_base_kwargs()
    )
    assert report["auto_trust"] is False
    assert report["persisted_bodies"] is False
    assert not (inbox / "evidence").exists()


# 13. Front Page fresh-item compatibility -- a discovery-derived draft with a
# provider field on its underlying record still classifies the same way
# through the existing, provider-agnostic front-page projection.
def test_front_page_publication_classification_is_provider_agnostic() -> None:
    from app.services.front_page import build_front_page

    draft = {
        "id": "ev-pulse-draft",
        "record_type": "evidence",
        "status": "draft",
        "evidence_role": "publication_artifact",
        "title": "New raspberry variety launch acreage licensing",
        "captured_date": "2026-09-01",
        "source_name": "Discovered via Industry Pulse",
        "source_type": "news_search",
        "source_url": "https://freshplaza.com/discovered-item",
        "berry_ids": ["berry-raspberry"],
    }
    page = build_front_page(
        published=[],
        drafts=[draft],
        signals=[],
        assessments=[],
        sources=[],
        entities=[],
        relationships=[],
        inbox_dir=Path("."),
        data_dir=Path("."),
        now=None,
    )
    matches = [i for i in page["top_stories"] if i["id"] == "ev-pulse-draft"]
    assert matches and matches[0]["trust_label"] == "FRESH / UNREVIEWED"


# 14. Coverage Assurance compatibility -- run_pulse()'s report shape is
# unchanged in the fields Coverage Assurance already reads.
def test_report_still_exposes_novel_source_fields_coverage_assurance_reads() -> None:
    google = MemoryProvider(name="google_news_rss", hits=[])
    report = run_pulse(provider=google, **_base_kwargs())
    assert "novel_source_count" in report
    assert "novel_source_hosts" in report
    assert "known_source_item_missed_count" in report
    assert "known_source_not_collected_count" in report


# 15. Cost/run telemetry -- counts only, no fabricated dollar figure baked
# into runtime output.
def test_provider_telemetry_has_counts_but_no_runtime_cost_field() -> None:
    google = MemoryProvider(name="google_news_rss", hits=[_hit("https://freshplaza.com/a", provider="x")])
    perplexity = MemoryProvider(name="perplexity", hits=[])
    report = run_pulse(provider=google, catch_net_provider=perplexity, **_base_kwargs())
    for stats in report["provider_telemetry"].values():
        assert set(stats) == {"queries_issued", "hits_returned", "errors", "unique_qualifying"}
        assert "cost" not in stats and "estimated_cost_usd" not in stats
    assert "estimated_cost_usd" not in report
    assert "cost" not in report


# 16. No static leak.
def test_build_static_does_not_reference_perplexity_or_catch_net() -> None:
    text = Path(main.BASE_DIR, "scripts", "build_static.py").read_text(encoding="utf-8")
    assert "perplexity" not in text.lower()
    assert "catch_net" not in text.lower()


# Route-level: the ENABLE_PERPLEXITY_PULSE flag controls what /industry-pulse/run does.
def test_route_flag_off_never_constructs_perplexity_provider(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "PERPLEXITY_PULSE_ENABLED", False)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_entities", lambda: [])
    monkeypatch.setattr(main, "list_drafts_metadata", lambda: [])
    monkeypatch.setattr(main, "list_pending_drafts", lambda: [])
    monkeypatch.setattr(main, "list_discovered_items", lambda *_a, **_k: [])
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [], {}))

    captured = {}

    def _stub(**kwargs):
        captured["catch_net_provider"] = kwargs.get("catch_net_provider")
        return {"refused": False, "refusal_reason": ""}

    monkeypatch.setattr(main, "run_newsroom_cycle", _stub)
    client = TestClient(main.app)
    resp = client.post("/industry-pulse/run", follow_redirects=False)
    assert resp.status_code == 303
    assert captured["catch_net_provider"] is None


def test_route_flag_on_without_credential_still_passes_none(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "PERPLEXITY_PULSE_ENABLED", True)
    monkeypatch.setattr(main, "has_perplexity", lambda: False)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_entities", lambda: [])
    monkeypatch.setattr(main, "list_drafts_metadata", lambda: [])
    monkeypatch.setattr(main, "list_pending_drafts", lambda: [])
    monkeypatch.setattr(main, "list_discovered_items", lambda *_a, **_k: [])
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [], {}))

    captured = {}

    def _stub(**kwargs):
        captured["catch_net_provider"] = kwargs.get("catch_net_provider")
        return {"refused": False, "refusal_reason": ""}

    monkeypatch.setattr(main, "run_newsroom_cycle", _stub)
    client = TestClient(main.app)
    resp = client.post("/industry-pulse/run", follow_redirects=False)
    assert resp.status_code == 303
    assert captured["catch_net_provider"] is None


def test_industry_pulse_page_shows_flag_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "PERPLEXITY_PULSE_ENABLED", True)
    monkeypatch.setattr(main, "has_perplexity", lambda: False)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "list_drafts_metadata", lambda: [])
    monkeypatch.setattr(main, "list_discovered_items", lambda *_a, **_k: [])
    page = TestClient(main.app).get("/industry-pulse")
    assert page.status_code == 200
    assert "ENABLE_PERPLEXITY_PULSE" in page.text
    assert "Flag is on but no credential is configured" in page.text
